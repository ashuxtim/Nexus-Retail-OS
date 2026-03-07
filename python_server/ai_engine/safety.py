# FILE: python_server/ai_engine/safety.py
import logging
import re

_logger = logging.getLogger("NexusAI_Backend")


class SafetyGuard:
    def __init__(self, llm):
        self.llm = llm
        self.pending_action = None
        self.unsafe_keywords = [
            "delete",
            "remove",
            "drop",
            "erase",
            "update",
            "change",
            "modify",
            "insert",
            "add",
            "create",
        ]
        # Whole-word regex — "add" matches "add customer" but NOT "address"
        self._unsafe_re = re.compile(
            r'\b(' + '|'.join(re.escape(w) for w in self.unsafe_keywords) + r')\b',
            re.IGNORECASE
        )

    def classify_intent(self, user_text):
        """
        Decides if the user wants to CHAT, QUERY data, or perform a DANGEROUS action.
        """
        # 1. Heuristic Check (Fast) — whole-word matching
        if self._unsafe_re.search(user_text):
            return "DANGER"

        # 2. LLM Check (Accurate)
        try:
            router_prompt = f"Classify query: '{user_text}'. Categories: CHAT, QUERY. Reply one word."
            intent = self.llm.invoke(router_prompt).content.strip().upper()
            return intent
        except Exception as e:
            _logger.error(f"Intent classification LLM call failed: {e}")
            return "CHAT"

    def check_confirmation(self, user_text):
        """
        If an action is pending, checks if the user said YES or NO.
        Returns: 'CONFIRM', 'CANCEL', or 'UNCLEAR'
        """
        if not self.pending_action:
            return "NO_ACTION"

        try:
            prompt = f"User said: '{user_text}'. Pending Action: '{self.pending_action}'. Classify as CONFIRM or CANCEL. Reply 1 word."
            classification = self.llm.invoke(prompt).content.strip().upper()

            if "CONFIRM" in classification or "YES" in user_text.upper():
                return "CONFIRM"
            elif "CANCEL" in classification or "NO" in user_text.upper():
                return "CANCEL"
            else:
                return "UNCLEAR"
        except Exception as e:
            _logger.error(f"Confirmation check LLM call failed: {e}")
            return "UNCLEAR"

    def set_pending(self, action_description):
        self.pending_action = action_description

    def clear_pending(self):
        self.pending_action = None

    def get_pending(self):
        return self.pending_action
