# FILE: python_server/routes/ai_chat.py
# AI Chat endpoint: POST /ask
# Flow: Greetings → Python Router → Intent classify (CHAT vs QUERY) → LLM Agent

import asyncio
from fastapi import APIRouter
from pydantic import BaseModel
from langchain_core.messages import HumanMessage

from core import state
from scripts.backend_logging import get_logger

# Pattern router + pre-built queries (zero LLM)
from ai_engine.router import route_query
from ai_engine.queries import (
    get_top_customers,
    get_today_sales,
    get_monthly_revenue,
    get_weekly_revenue,
    get_recent_sales,
    get_top_products,
    get_low_stock,
    get_out_of_stock,
    get_all_products,
    get_all_customers,
    search_product,
    search_customer,
    get_customer_purchase_history,
    get_all_suppliers,
    get_recent_purchases,
    get_quick_summary,
)

router = APIRouter()
logger = get_logger("NexusAI_Backend")

AI_TIMEOUT = 60  # seconds (multi-tool queries need more time)


class AskRequest(BaseModel):
    text: str


# ─────────────────────────────────────────
# LLM Agent Invocation (langgraph)
# ─────────────────────────────────────────


async def _safe_agent_invoke(prompt: str):
    """Invoke lean agent with timeout and error handling."""
    MAX_RETRIES = 2

    last_error = None
    for attempt in range(1 + MAX_RETRIES):
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: state.agent_executor.invoke(
                        {"messages": [HumanMessage(content=prompt)]}
                    )
                ),
                timeout=AI_TIMEOUT,
            )

            messages = result.get("messages", [])

            final_msg = messages[-1] if messages else None
            if final_msg and hasattr(final_msg, "content") and final_msg.content:
                return {"answer": str(final_msg.content)}

            return {"answer": "⚠️ No response from the AI agent. Please try again."}

        except asyncio.TimeoutError:
            return {
                "answer": "⏱️ Request timed out. Please try a simpler query.",
                "error_type": "timeout",
            }

        except Exception as e:
            last_error = e
            err_str = str(e).lower()

            # Retry on transient Groq errors
            if "failed_generation" in err_str or "failed to call a function" in err_str:
                if attempt < MAX_RETRIES:
                    logger.warning(f"Groq error (attempt {attempt+1}), retrying...")
                    await asyncio.sleep(0.5)
                    continue

            if "rate_limit" in err_str or "429" in err_str:
                return {
                    "answer": "⏳ API rate limit reached. Please wait about a minute.",
                    "error_type": "rate_limit",
                }

            logger.error(f"Agent invocation failed: {e}")
            return {"answer": f"❌ Error: {str(e)}", "error_type": "error"}

    logger.error(f"All retries failed: {last_error}")
    return {"answer": f"❌ Error: {str(last_error)}", "error_type": "error"}


# ─────────────────────────────────────────
# Python query handler (zero LLM)
# ─────────────────────────────────────────


def _handle_python_query(fn_name, arg):
    """Execute a pre-built Python query. Returns dict or None (→ LLM fallback)."""
    engine = state.raw_engine

    # ── Sales ──
    if fn_name == "top_customers":
        limit = arg or 5
        rows = get_top_customers(engine, limit=limit)
        if not rows:
            return {"answer": "No sales data found yet."}
        lines = "\n".join([f"{i+1}. {r[0]}: ₹{r[1]:,.2f}" for i, r in enumerate(rows)])
        return {"answer": f"🏆 **Top {limit} Customers by Sales:**\n\n{lines}"}

    elif fn_name == "today_sales":
        count, total = get_today_sales(engine)
        total = total or 0
        return {
            "answer": f"📊 **Today's Sales:**\n\n• Transactions: {count}\n• Revenue: ₹{total:,.2f}"
        }

    elif fn_name == "monthly_revenue":
        total = get_monthly_revenue(engine)
        return {"answer": f"📈 **This Month's Revenue:** ₹{total:,.2f}"}

    elif fn_name == "weekly_revenue":
        total = get_weekly_revenue(engine)
        return {"answer": f"📅 **This Week's Revenue:** ₹{total:,.2f}"}

    elif fn_name == "recent_sales":
        rows = get_recent_sales(engine, limit=30)
        if not rows:
            return {"answer": "No recent sales found."}
        lines = "\n".join(
            [f"• {r[0]} → {r[1]} {r[2]} x{r[3]} @ ₹{r[4]} ({r[5]})" for r in rows]
        )
        return {"answer": f"🧾 **Recent Sales:**\n\n{lines}"}

    elif fn_name == "top_products":
        limit = arg or 5
        rows = get_top_products(engine, limit=limit)
        if not rows:
            return {"answer": "No sales data yet."}
        lines = "\n".join(
            [f"{i+1}. {r[0]} - {r[1]}: {r[2]} units sold" for i, r in enumerate(rows)]
        )
        return {"answer": f"🛒 **Top {limit} Products:**\n\n{lines}"}

    # ── Inventory ──
    elif fn_name == "low_stock":
        threshold = arg if isinstance(arg, int) else 10
        rows = get_low_stock(engine, threshold=threshold)
        if not rows:
            return {
                "answer": f"✅ No products below {threshold} units. Stock is healthy!"
            }
        lines = "\n".join(
            [f"⚠️ {r[0]} - {r[1]}: **{r[2]} units** [{r[3]}]" for r in rows[:30]]
        )
        return {"answer": f"⚠️ **Low Stock Alert ({len(rows)} items):**\n\n{lines}"}

    elif fn_name == "out_of_stock":
        rows = get_out_of_stock(engine)
        if not rows:
            return {"answer": "✅ No products are out of stock!"}
        lines = "\n".join([f"❌ {r[0]} - {r[1]} [{r[2]}]" for r in rows[:30]])
        return {"answer": f"❌ **Out of Stock ({len(rows)} items):**\n\n{lines}"}

    elif fn_name == "all_products":
        rows = get_all_products(engine)
        if not rows:
            return {"answer": "No products found."}
        lines = "\n".join(
            [f"• {r[0]} - {r[1]}: ₹{r[2]} | Stock: {r[3]}" for r in rows[:30]]
        )
        return {
            "answer": f"📦 **Products ({len(rows)} total, showing first 30):**\n\n{lines}"
        }

    elif fn_name == "search_product":
        rows = search_product(engine, arg)
        if not rows:
            return None  # LLM fallback — let agent answer intelligently
        lines = "\n".join([f"• {r[0]} - {r[1]}: ₹{r[2]} | Stock: {r[3]}" for r in rows])
        return {"answer": f"🔍 **Search results for '{arg}':**\n\n{lines}"}

    # ── Customers ──
    elif fn_name == "all_customers":
        rows = get_all_customers(engine)
        if not rows:
            return {"answer": "No customers found."}
        lines = "\n".join([f"• {r[0]} ({r[1]})" for r in rows[:30]])
        return {
            "answer": f"👥 **Customers ({len(rows)} total, showing first 30):**\n\n{lines}"
        }

    elif fn_name == "search_customer":
        rows = search_customer(engine, arg)
        if not rows:
            return None  # LLM fallback — let agent answer intelligently
        lines = "\n".join([f"• {r[0]} | 📱 {r[1]} | {r[2]}" for r in rows])
        return {"answer": f"🔍 **Customer Search:**\n\n{lines}"}

    elif fn_name == "customer_history":
        rows = get_customer_purchase_history(engine, arg)
        if not rows:
            return {"answer": f"No purchase history for '{arg}'."}
        lines = "\n".join([f"• {r[0]} {r[1]} x{r[2]} @ ₹{r[3]} ({r[4]})" for r in rows])
        return {"answer": f"🧾 **Purchase History — {arg}:**\n\n{lines}"}

    # ── Suppliers ──
    elif fn_name == "all_suppliers":
        rows = get_all_suppliers(engine)
        if not rows:
            return {"answer": "No suppliers found."}
        lines = "\n".join([f"• {r[0]} ({r[1]})" for r in rows])
        return {"answer": f"🏭 **Suppliers:**\n\n{lines}"}

    elif fn_name == "recent_purchases":
        rows = get_recent_purchases(engine)
        if not rows:
            return {"answer": "No recent purchases."}
        lines = "\n".join(
            [f"• {r[0]} → {r[1]} {r[2]} x{r[3]} @ ₹{r[4]} ({r[5]})" for r in rows]
        )
        return {"answer": f"📥 **Recent Purchases:**\n\n{lines}"}

    # ── Analytics (from cache) ──
    elif fn_name == "churn_risk":
        # Use live AnalyticsEngine (same as dashboard endpoint)
        risks = []
        try:
            from analytics import AnalyticsEngine

            analytics = AnalyticsEngine(state.raw_engine, base_dir=state.BASE_DIR)
            dashboard = analytics.get_dashboard_metrics()
            dash_data = dashboard.get("data", dashboard)  # handle nested or flat
            risks = dash_data.get("churn_risk", [])
        except Exception as e:
            logger.error(f"Live churn failed, falling back to cache: {e}")
            risks = state.ANALYTICS_CACHE.get("churn_risk", [])

        if not risks:
            return {"answer": "✨ No immediate churn risks detected."}
        sorted_risks = sorted(risks, key=lambda x: x.get("risk_score", 0), reverse=True)
        report = f"🤖 **AI Churn Report (Total At-Risk: {len(sorted_risks)}):**\n\n"
        for r in sorted_risks[:15]:
            report += (
                f"🔴 **{r.get('name', 'Unknown')}** (Risk: {r.get('risk_score', 0)}%)\n"
            )
            report += f"   Reason: {r.get('trend', 'N/A')} • Inactive: {r.get('days_inactive', 0)} days\n\n"
        return {"answer": report}

    elif fn_name == "market_basket":
        try:
            from analytics import AnalyticsEngine

            analytics = AnalyticsEngine(state.raw_engine, base_dir=state.BASE_DIR)
            dashboard = analytics.get_dashboard_metrics()
            dash_data = dashboard.get("data", dashboard)
            mb = dash_data.get("market_basket", {})
            if isinstance(mb, dict) and mb.get("rules"):
                rules = mb["rules"][:10]  # Top 10 only
                lines = []
                for i, r in enumerate(rules, 1):
                    ant = r.get("antecedent", ["?"])
                    con = r.get("consequent", ["?"])
                    # Clean up list brackets if present
                    ant_str = ant[0] if isinstance(ant, list) else str(ant).strip("[]'")
                    con_str = con[0] if isinstance(con, list) else str(con).strip("[]'")
                    lines.append(
                        f"{i}. Customers who buy **{ant_str}** often also buy **{con_str}**"
                    )
                return {
                    "answer": f"🛒 **Shopping Patterns — What sells together:**\n\n"
                    + "\n".join(lines)
                    + "\n\n💡 *Place these products near each other to boost sales!*"
                }
            elif isinstance(mb, str):
                return {"answer": f"🛒 **Shopping Patterns:**\n{mb}"}
            else:
                return {"answer": "🛒 Market basket analysis pending..."}
        except Exception as e:
            logger.error(f"Market basket failed: {e}")
            mb = state.ANALYTICS_CACHE.get("market_basket", "Analysis pending...")
            return {"answer": f"🛒 **Shopping Patterns:**\n{mb}"}

    # ── Dashboard ──
    elif fn_name == "summary":
        s = get_quick_summary(engine)
        return {
            "answer": (
                f"📊 **Quick Summary:**\n\n"
                f"• Today's Sales: {s['today_sales_count']} transactions — ₹{s['today_revenue']:,.2f}\n"
                f"• Low Stock Items: {s['low_stock_items']}\n"
                f"• Total Customers: {s['total_customers']}\n"
                f"• Total Products: {s['total_products']}"
            )
        }

    return None  # Unknown fn → LLM fallback


# ─────────────────────────────────────────
# Main endpoint
# ─────────────────────────────────────────


@router.post("/ask")
async def ask_agent(q: AskRequest):
    """Greetings → Python Router → Intent classify → LLM Agent fallback."""
    if not state.agent_executor or not state.safety_guard:
        return {
            "answer": "AI not configured. Please set your Groq API key in Settings.",
            "error_type": "not_configured",
        }
    user_text = q.text.strip()

    # ── 0. Greetings (zero LLM) ──
    greetings = {"hi", "hello", "hey", "hola", "greetings", "test", "ping", "yo"}
    if user_text.lower() in greetings:
        return {
            "answer": "👋 Hello! I am NexusRetail OS AI. Ask me about sales, inventory, or customers."
        }

    # ── 1. Pattern Router (zero LLM) ──
    fn_name, arg = route_query(user_text)
    print(f"[DEBUG] route_query result: {fn_name}, {arg}")
    if fn_name:
        try:
            result = await asyncio.to_thread(_handle_python_query, fn_name, arg)
            if result:
                return result
        except Exception as e:
            logger.error(f"Python query handler failed for '{fn_name}': {e}")

    # ── 2. Intent check (LLM only for truly ambiguous) ──
    intent = state.safety_guard.classify_intent(user_text)

    if intent == "CHAT":
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: state.safety_guard.llm.invoke(
                        f"User: {user_text}. Reply helpfully."
                    ).content
                ),
                timeout=AI_TIMEOUT,
            )
            return {"answer": result}
        except asyncio.TimeoutError:
            return {"answer": "⏱️ Chat response timed out.", "error_type": "timeout"}
        except Exception as e:
            err_str = str(e).lower()
            if "rate_limit" in err_str or "429" in err_str:
                return {
                    "answer": "⏳ API rate limit reached.",
                    "error_type": "rate_limit",
                }
            logger.error(f"Chat fallback failed: {e}")
            return {"answer": "I'm online. Ask me about your data!"}

    # ── 3. LLM Agent (complex queries, ~10% of traffic) ──
    logger.info(f"Routing to LLM agent: '{user_text}'")
    return await _safe_agent_invoke(user_text)
