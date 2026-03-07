# FILE: python_server/ai_engine/safety.py
# Intent classifier: QUERY vs CHAT. Zero CRUD, zero confirmation.

import re
import logging

_logger = logging.getLogger("NexusAI_Backend")


class SafetyGuard:
    def __init__(self, llm):
        self.llm = llm

        # --- Query keywords (bypasses LLM classification) ---
        self.query_keywords = [
            "show",
            "list",
            "get",
            "find",
            "search",
            "how many",
            "what is",
            "what are",
            "which",
            "total",
            "sales",
            "stock",
            "revenue",
            "report",
            "top",
            "best",
            "low",
            "inventory",
            "customer",
            "supplier",
            "product",
            "purchase",
            "history",
            "summary",
            "dashboard",
            "overview",
            "churn",
            "market",
            "basket",
            "pattern",
            "forecast",
        ]
        self._query_re = re.compile(
            r"\b(" + "|".join(re.escape(w) for w in self.query_keywords) + r")\b",
            re.IGNORECASE,
        )

    def classify_intent(self, user_text: str) -> str:
        """
        Returns: QUERY | CHAT
        LLM only called for ambiguous cases (~5% of traffic).
        """
        # 1. Query check (regex — instant)
        if self._query_re.search(user_text):
            return "QUERY"

        # 2. Truly ambiguous — call LLM (rare)
        try:
            prompt = f"Classify this user message as CHAT or QUERY. One word only. Message: '{user_text}'"
            result = self.llm.invoke(prompt).content.strip().upper()
            return result if result in ("CHAT", "QUERY") else "CHAT"
        except Exception as e:
            _logger.error(f"Intent classification failed: {e}")
            return "CHAT"
