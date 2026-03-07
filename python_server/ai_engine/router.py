# FILE: python_server/ai_engine/router.py
# Pure Python pattern matching. Zero LLM. Zero cost.

import re

# Filler words to strip from extracted search terms
_FILLER_WORDS = {"any", "some", "the", "a", "an", "all", "our", "my", "their", "about", "like"}


def _clean_search_term(raw: str) -> str:
    """Clean a raw regex-extracted search term into a usable query."""
    # 1. Truncate at question mark (removes trailing questions)
    term = raw.split("?")[0].strip()
    # 2. Remove trailing "product(s)" / "item(s)" / "stock"
    term = re.sub(r'\s*(products?|items?|stock)\s*$', '', term, flags=re.IGNORECASE).strip()
    # 3. Strip filler words
    words = [w for w in term.split() if w.lower() not in _FILLER_WORDS]
    return " ".join(words).strip()

# ─────────────────────────────────────────
# PATTERN → FUNCTION NAME MAPPING
# Add new patterns here as your app grows
# ─────────────────────────────────────────

QUERY_PATTERNS = [
    # Sales
    (r"top\s*(\d+)?\s*customer",                "top_customers"),
    (r"best\s*(\d+)?\s*customer",               "top_customers"),
    (r"today.{0,10}sale|sale.{0,10}today",      "today_sales"),
    (r"today.{0,10}revenue|today.{0,10}earn",   "today_sales"),
    (r"this\s*month.{0,10}revenue|monthly",     "monthly_revenue"),
    (r"this\s*week.{0,10}revenue|weekly",       "weekly_revenue"),
    (r"recent.{0,10}sale|last.{0,10}sale",      "recent_sales"),
    (r"top\s*(\d+)?\s*product|best.{0,10}sell|top\s*sell", "top_products"),

    # Inventory
    (r"low\s*stock|running\s*(?:out|low)|almost\s*out|items?\s*low", "low_stock"),
    (r"out\s*of\s*stock|zero\s*stock",          "out_of_stock"),
    (r"all\s*product|list\s*product|show\s*product|inventory", "all_products"),

    # Customers
    (r"all\s*customer|list\s*customer|show\s*customer", "all_customers"),
    (r"summary|dashboard|overview|quick\s*stats",       "summary"),

    # Purchases
    (r"all\s*supplier|list\s*supplier",         "all_suppliers"),
    (r"recent\s*purchase|last\s*purchase",      "recent_purchases"),

    # Analytics (served from cache — already Python)
    (r"churn|at\s*risk|losing\s*customer",      "churn_risk"),
    (r"market\s*basket|buying\s*pattern|goes\s*with", "market_basket"),
]

# Patterns that need a search term extracted
# NOTE: Customer-specific patterns MUST come before generic search to prevent
# "find customer X" from matching search_product.
SEARCH_PATTERNS = [
    (r"(?:search|find|look for)\s+customer\s+(.+)$",                               "search_customer"),
    (r"(?:history|purchases?)\s+(?:of|for)\s+(.+)$",                              "customer_history"),
    (r"(.+?)(?:'s)?\s+(?:purchase\s+history|orders|transactions)$",               "customer_history"),
    (r"(?:search|find|do we have|check|look for|show me)\s+(.+?)(?:\s+product)?$", "search_product"),
]


def route_query(user_text: str):
    """
    Returns (function_name, arg) or (None, None) if LLM needed.

    function_name: string key matched to handler in /ask endpoint
    arg: extracted parameter (limit number, search term) or None
    """
    lower = user_text.lower().strip()

    # 0. Skip router for complex/analytical queries → let LLM handle
    COMPLEX_SIGNALS = [
        r"\bcompare\b", r"\bvs\b", r"\bversus\b", r"\bdifference\b",
        r"\bbetter\b", r"\banalyze\b", r"\bstrategy\b", r"\badvice\b",
        r"\bsuggest\b", r"\bhow\s+can\b", r"\bshould\s+i\b", r"\bwhy\b",
        r"\bwhich\s+(?:customer|product|item)\b", r"\bhelp\s+me\b",
        r"\bincrease\b", r"\breduce\b", r"\bimprove\b", r"\boptimize\b",
    ]
    if any(re.search(sig, lower) for sig in COMPLEX_SIGNALS):
        return None, None

    # 1. Try simple query patterns
    for pattern, fn_name in QUERY_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            # Extract number if present (e.g. "top 10 customers")
            try:
                arg = int(match.group(1)) if match.lastindex and match.group(1) else None
            except (IndexError, TypeError):
                arg = None
            return fn_name, arg

    # 2. Try search patterns (need term extraction)
    for pattern, fn_name in SEARCH_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            search_term = _clean_search_term(match.group(1))
            if len(search_term) >= 2:  # Ignore too-short terms
                return fn_name, search_term

    # 3. No match — LLM needed
    return None, None
