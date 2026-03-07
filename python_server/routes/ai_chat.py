# FILE: python_server/routes/ai_chat.py
# AI Chat endpoint: POST /ask
# Contains AmbiguityInterceptor, _safe_agent_invoke, and ask_agent.

import re
import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from langchain_core.callbacks import BaseCallbackHandler

from core import state
from scripts.backend_logging import get_logger

router = APIRouter()
logger = get_logger("NexusAI_Backend")

AI_TIMEOUT = 30  # seconds


class AskRequest(BaseModel):
    text: str


class AmbiguityInterceptor(BaseCallbackHandler):
    """
    LangChain callback that captures tool outputs BEFORE the LLM gets a chance
    to paraphrase them. If any tool returns an AMBIGUOUS message, we catch it
    here and short-circuit — no extra LLM call needed.
    """
    def __init__(self):
        self.ambiguous_output = None

    def on_tool_end(self, output: str, **kwargs) -> None:
        if "AMBIGUOUS" in str(output) and self.ambiguous_output is None:
            self.ambiguous_output = str(output)


async def _safe_agent_invoke(prompt):
    """Invoke agent with timeout and rate-limit detection.

    Includes retry logic for Groq's intermittent 'failed_generation' errors
    where Llama models emit malformed tool calls that the API rejects.
    """
    MAX_RETRIES = 2
    is_confirmed = prompt.startswith("CONFIRMED by user")

    # Strip internal prefixes so original_action is the clean user intent
    clean_action = prompt
    for prefix in ["CONFIRMED by user. Execute this action NOW: ", "CONFIRMED: "]:
        if clean_action.startswith(prefix):
            clean_action = clean_action[len(prefix):]

    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        interceptor = AmbiguityInterceptor()
        try:
            res = await asyncio.wait_for(
                state.agent_executor.ainvoke(
                    {"input": prompt}, config={"callbacks": [interceptor]}
                ),
                timeout=AI_TIMEOUT,
            )

            # Check interceptor FIRST — catches AMBIGUOUS from raw tool output
            # before the LLM paraphrases it into something like "The user needs to specify..."
            # SKIP when is_confirmed — prevents infinite disambiguation loop.
            if interceptor.ambiguous_output and not is_confirmed:
                options = re.findall(r'\d+\.\s+(.+)', interceptor.ambiguous_output)
                if options:
                    return {
                        "type": "disambiguation",
                        "message": "Multiple matches found. Which one did you mean?",
                        "options": options,
                        "original_action": clean_action,
                    }

            output = str(res["output"])

            # Fallback: LLM did forward AMBIGUOUS verbatim (respecting system prompt rule 2)
            if "AMBIGUOUS" in output and not is_confirmed:
                options = re.findall(r'\d+\.\s+(.+)', output)
                if options:
                    return {
                        "type": "disambiguation",
                        "message": "Multiple matches found. Which one did you mean?",
                        "options": options,
                        "original_action": clean_action,
                    }

            return {"answer": output}

        except asyncio.TimeoutError:
            return {"answer": "⏱️ Request timed out. The AI took too long — please try a simpler query.", "error_type": "timeout"}

        except Exception as e:
            last_error = e
            err_str = str(e).lower()

            # Groq BadRequestError: Llama emitted a malformed tool call — retry
            if "failed_generation" in err_str or "failed to call a function" in err_str:
                if attempt < MAX_RETRIES:
                    logger.warning(f"Groq tool-call failed (attempt {attempt+1}/{1+MAX_RETRIES}), retrying...")
                    await asyncio.sleep(0.5)
                    continue
                # Fall through to error handling after all retries exhausted

            # If the LLM crashed AFTER a tool returned AMBIGUOUS, use interceptor output
            if interceptor.ambiguous_output and not is_confirmed:
                options = re.findall(r'\d+\.\s+(.+)', interceptor.ambiguous_output)
                if options:
                    return {
                        "type": "disambiguation",
                        "message": "Multiple matches found. Which one did you mean?",
                        "options": options,
                        "original_action": clean_action,
                    }

            if "rate_limit" in err_str or "429" in err_str or "rate limit" in err_str:
                return {"answer": "⏳ API rate limit reached. Please wait about a minute before trying again.", "error_type": "rate_limit"}

            logger.error(f"Agent invocation failed: {e}")
            logger.error(f"  Prompt was: {prompt[:200]}")
            return {"answer": f"❌ Error: {str(e)}", "error_type": "error"}

    # Should not reach here, but safety net
    logger.error(f"All {1+MAX_RETRIES} attempts failed: {last_error}")
    return {"answer": f"❌ Error: {str(last_error)}", "error_type": "error"}


@router.post("/ask")
async def ask_agent(q: AskRequest):
    """Delegate to Agent Executor & Safety Guard"""
    if not state.agent_executor or not state.safety_guard:
        return {"answer": "AI not configured. Please set your Groq API key in Settings.", "error_type": "not_configured"}
    user_text = q.text.strip()

    greetings = ["hi", "hello", "hey", "hola", "greetings", "test", "ping"]
    if user_text.lower() in greetings:
        return {
            "answer": "Hello! I am NexusRetail OS AI. Ask me about sales, inventory, or customers."
        }

    # DISAMBIGUATION BYPASS: Messages from DisambiguationCard start with "CONFIRMED:"
    # Route directly to agent — bypassing the safety guard keyword filter entirely.
    # Without this, "CONFIRMED: delete rahul — specifically '...'" gets caught by the
    # DANGER keyword scanner and loops into another YES/NO confirmation instead of executing.
    if user_text.startswith("CONFIRMED:"):
        # Extract the clean action text after "CONFIRMED: " prefix
        action_text = user_text[len("CONFIRMED:"):].strip()
        return await _safe_agent_invoke(f"CONFIRMED by user. Execute this action NOW: {action_text}")

    # 1. Check for Pending Confirmation (YES/NO) via Safety Guard
    confirm_status = state.safety_guard.check_confirmation(user_text)

    if confirm_status == "CONFIRM":
        action = state.safety_guard.get_pending()
        state.safety_guard.clear_pending()
        return await _safe_agent_invoke(f"CONFIRMED by user. Execute this action NOW: {action}")

    elif confirm_status == "CANCEL":
        state.safety_guard.clear_pending()
        return {"answer": "🚫 Action cancelled."}

    elif confirm_status == "UNCLEAR" and state.safety_guard.get_pending():
        return {
            "answer": f"⚠️ Please type **YES** to confirm or **NO** to cancel:\n\n\"{state.safety_guard.get_pending()}\""
        }

    # 2. New Request - Classify Intent
    intent = state.safety_guard.classify_intent(user_text)

    if intent == "DANGER":
        state.safety_guard.set_pending(user_text)
        return {
            "answer": f'⚠️ **Confirmation Required**\n\nCommand: "{user_text}"\n\nReply **YES** to proceed.'
        }

    elif intent == "CHAT":
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: state.safety_guard.llm.invoke(f"User: {user_text}. Reply helpfully.").content
                ),
                timeout=AI_TIMEOUT,
            )
            return {"answer": result}
        except asyncio.TimeoutError:
            return {"answer": "⏱️ Chat response timed out. Please try again.", "error_type": "timeout"}
        except Exception as e:
            err_str = str(e).lower()
            if "rate_limit" in err_str or "429" in err_str or "rate limit" in err_str:
                return {"answer": "⏳ API rate limit reached. Please wait about a minute.", "error_type": "rate_limit"}
            logger.error(f"Chat fallback failed: {e}")
            return {"answer": "I'm online. Ask me about your data!"}

    else:  # QUERY / SAFE ACTION
        return await _safe_agent_invoke(user_text)
