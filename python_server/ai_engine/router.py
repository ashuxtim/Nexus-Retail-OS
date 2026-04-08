# FILE: python_server/ai_engine/router.py
# Pure Python pattern matching. Zero LLM. Zero cost.

import re

# Strips leading question/command phrases before the noun
_LEADING_RE = re.compile(
    r"^(?:"
    r"what(?:'s|\s+is|\s+are)?\s+(?:(?:the|a|an)\s+)?(?:stock\s+(?:of\s+)?|level\s+of\s+|supplier\s+(?:for|of)\s+)?"
    r"|how\s+(?:much|many)\s+"
    r"|do\s+(?:we|you)\s+have\s+"
    r"|show\s+me\s+"
    r"|search\s+for\s+"
    r"|look\s+for\s+"
    r"|find\s+(?:supplier\s+(?:for|of)\s+|product\s+(?:for|of)\s+)?"
    r"|check\s+"
    r"|any\s+"
    r"|which\s+"
    r"|stock\s+(?:level\s+)?(?:of|for)\s+"
    r")",
    re.IGNORECASE,
)

# Strips trailing stock/status words after the noun
_TRAILING_RE = re.compile(
    r"\s+(?:stock|level|status|available|left|remaining|in\s+stock|products?|items?)\s*$",
    re.IGNORECASE,
)


def _extract_search_noun(text: str) -> str | None:
    """Extract the core search noun by stripping question words and trailing status words."""
    term = text.strip().rstrip("?").strip()
    term = _LEADING_RE.sub("", term).strip()
    term = _TRAILING_RE.sub("", term).strip()
    return term if len(term) >= 2 else None


# ─────────────────────────────────────────
# PATTERN → FUNCTION NAME MAPPING
# Add new patterns here as your app grows
# ─────────────────────────────────────────

QUERY_PATTERNS = [
    # Sales
    (r"top\s*(\d+)?\s*customer", "top_customers"),
    (r"best\s*(\d+)?\s*customer", "top_customers"),
    (r"today.{0,10}sale|sale.{0,10}today", "today_sales"),
    (r"today.{0,10}revenue|today.{0,10}earn", "today_sales"),
    (r"this\s*month.{0,10}revenue|monthly", "monthly_revenue"),
    (r"this\s*week.{0,10}revenue|weekly", "weekly_revenue"),
    (r"recent.{0,10}sale|last.{0,10}sale", "recent_sales"),
    (r"top\s*(\d+)?\s*product|best.{0,10}sell|top\s*sell", "top_products"),
    # Inventory
    (r"low\s*stock|running\s*(?:out|low)|almost\s*out|items?\s*low", "low_stock"),
    (r"out\s*of\s*stock|zero\s*stock", "out_of_stock"),
    (r"all\s*product|list\s*product|show\s*product|inventory", "all_products"),
    # Customers
    (r"all\s*customer|list\s*customer|show\s*customer", "all_customers"),
    (r"summary|dashboard|overview|quick\s*stats", "summary"),
    # Purchases
    (r"all\s*supplier|list\s*supplier", "all_suppliers"),
    (r"recent\s*purchase|last\s*purchase", "recent_purchases"),
    # Analytics (served from cache — already Python)
    (r"churn|at\s*risk|losing\s*customer", "churn_risk"),
    (r"market\s*basket|buying\s*pattern|goes\s*with", "market_basket"),
]

def route_query(user_text: str):
    """
    Returns (function_name, arg) or (None, None) if LLM needed.

    function_name: string key matched to handler in /ask endpoint
    arg: extracted parameter (limit number, search term) or None
    """
    lower = user_text.lower().strip()

    # 0. Skip router for genuinely complex/analytical queries → let LLM handle
    COMPLEX_SIGNALS = [
        r"\bcompare\b",
        r"\bvs\b",
        r"\bversus\b",
        r"\bdifference\b",
        r"\bbetter\b",
        r"\banalyze\b",
        r"\bstrategy\b",
        r"\badvice\b",
        r"\bsuggest\b",
        r"\bhow\s+can\b",
        r"\bshould\s+i\b",
        r"\bwhy\b",
        r"\bhelp\s+me\b",
        r"\bincrease\b",
        r"\breduce\b",
        r"\bimprove\b",
        r"\boptimize\b",
    ]
    if any(re.search(sig, lower) for sig in COMPLEX_SIGNALS):
        return None, None

    # 1. Try simple query patterns
    for pattern, fn_name in QUERY_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            # Extract number if present (e.g. "top 10 customers")
            try:
                arg = (
                    int(match.group(1)) if match.lastindex and match.group(1) else None
                )
            except (IndexError, TypeError):
                arg = None
            return fn_name, arg

    # 2. Noun extractor → SQL-first lookup, agent-fallback if SQL is empty
    noun = _extract_search_noun(lower)
    if noun:
        return "sql_first_search", noun

    # 3. No match — LLM needed
    return None, None
