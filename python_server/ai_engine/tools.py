# FILE: python_server/ai_engine/tools.py

from sqlalchemy import text
from langchain_core.tools import tool

# --- GLOBAL CONTEXT (Injected from main.py) ---
SEARCH_ENGINE = None
ANALYTICS_CACHE = {}


def set_context(engine, search_engine_ref, analytics_cache_ref):
    """
    Injects dependencies so tools can access DB, Vector Store, and Cache.
    Call this from main.py during startup.
    """
    global SEARCH_ENGINE, ANALYTICS_CACHE
    SEARCH_ENGINE = search_engine_ref
    ANALYTICS_CACHE = analytics_cache_ref
    print("✅ AI Tools Context Loaded.")


# --- SEARCH & ANALYTICS TOOLS ---


@tool
def search_catalog_tool(search_term: str, category: str = "product"):
    """
    SEARCH ENGINE. Use this FIRST when user asks 'Do we have X?' or 'Find X' or 'Who supplies X'.
    category: 'product', 'customer', or 'supplier'.
    For deep analysis (stockout, churn, basket), use the specialized tools instead.
    """
    if not SEARCH_ENGINE:
        return "Search Engine is still loading..."
    
    return SEARCH_ENGINE.search_display(category, search_term, limit=10)


@tool
def search_supplier_tool(search_term: str):
    """
    Searches for suppliers by name. Use this before recording purchases.
    """
    try:
        from core import state as _state
        if not _state.raw_engine:
            return "Database not connected."
        with _state.raw_engine.connect() as c:
            res = c.execute(
                text(
                    "SELECT name, mobile FROM supplier WHERE LOWER(name) LIKE LOWER(:name) LIMIT 5"
                ),
                {"name": f"%{search_term}%"},
            ).fetchall()
            if not res:
                return "No suppliers found."
            return "\n".join([f"- {r[0]} (Mobile: {r[1]})" for r in res])
    except Exception as e:
        return f"Error: {e}"


@tool
def check_churn_risk_tool():
    """Identifies customers at risk of leaving using cached ML predictions."""
    try:
        from analytics import AnalyticsEngine
        from core import state as _state

        analytics = AnalyticsEngine(_state.raw_engine, base_dir=_state.BASE_DIR)
        dashboard = analytics.get_dashboard_metrics()
        dash_data = dashboard.get("data", dashboard)
        risks = dash_data.get("churn_risk", [])
    except Exception:
        risks = ANALYTICS_CACHE.get("churn_risk", [])

    if not risks:
        return "✨ No immediate churn risks detected."

    sorted_risks = sorted(risks, key=lambda x: x.get("risk_score", 0), reverse=True)
    report = f"🤖 **AI Churn Report (Total At-Risk: {len(sorted_risks)}):**\n\n"
    for r in sorted_risks[:15]:
        report += (
            f"🔴 **{r.get('name', 'Unknown')}** (Risk: {r.get('risk_score', 0)}%)\n"
        )
        report += f"   Reason: {r.get('trend', 'N/A')} • Inactive: {r.get('days_inactive', 0)} days\n\n"
    return report


@tool
def get_market_insights_tool():
    """Returns 'Market Basket' patterns (e.g. Bread goes with Milk)."""
    try:
        from analytics import AnalyticsEngine
        from core import state as _state

        analytics = AnalyticsEngine(_state.raw_engine, base_dir=_state.BASE_DIR)
        dashboard = analytics.get_dashboard_metrics()
        dash_data = dashboard.get("data", dashboard)
        mb = dash_data.get("market_basket", {})
        if isinstance(mb, dict) and mb.get("rules"):
            rules = mb["rules"][:10]
            lines = []
            for i, r in enumerate(rules, 1):
                ant = r.get("antecedent", ["?"])
                con = r.get("consequent", ["?"])
                ant_str = ant[0] if isinstance(ant, list) else str(ant).strip("[]'")
                con_str = con[0] if isinstance(con, list) else str(con).strip("[]'")
                lines.append(
                    f"{i}. Customers who buy **{ant_str}** often also buy **{con_str}**"
                )
            return (
                f"🛒 **Shopping Patterns — What sells together:**\n\n"
                + "\n".join(lines)
                + "\n\n💡 *Place these products near each other to boost sales!*"
            )
        return "🛒 Market basket analysis pending..."
    except Exception:
        return f"🛒 **Shopping Patterns:**\n{ANALYTICS_CACHE.get('market_basket', 'Analysis pending...')}"


# --- NEW PRODUCT-SPECIFIC ML TOOLS (Phase 2) ---

@tool
def get_product_stockout_tool(product_name: str) -> str:
    """
    Finds all variants matching a product name/category and returns Monte Carlo
    stockout predictions for each. Use this when the user asks about when a 
    product will run out, stock finishing, or restocking urgency.
    
    Examples: "when will chips finish", "cold drinks running low", 
              "which biscuits need restock", "dairy stock status"
    """
    if not SEARCH_ENGINE or not getattr(SEARCH_ENGINE, "is_ready", True):
        return "⏳ Search engine warming up. Try again in 30 seconds."

    # Step 1: Resolve entity name → variant IDs via ChromaDB
    # If search() returns dict, great. If it returns text, Phase 1 is missing, but let's assume Phase 1 is done.
    search_result = SEARCH_ENGINE.search("product", product_name, limit=10)
    
    # Handle both new dictionary format and fallback text format
    if isinstance(search_result, str):
        return f"Warning: Search engine returned text. Ensure Phase 1 ChromaDB migration is active. Result: {search_result}"

    if "error" in search_result:
        return search_result["message"]

    if not search_result.get("matches"):
        return f"No products found matching '{product_name}'."

    variant_ids = [m["variant_id"] for m in search_result["matches"] if "variant_id" in m]
    
    if not variant_ids:
         return f"Resolved '{product_name}' but could not extract variant IDs. Check vector store format."

    # Step 2: Get Monte Carlo predictions
    try:
        from models.stockout.predictor import StockoutPredictor
        from core import state as _state
        import concurrent.futures

        predictor = StockoutPredictor(
            db_engine=_state.raw_engine,
            config={"n_simulations": 10000, "forecast_days": 30}
        )
        
        # Execute with 30-second timeout guard
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(predictor.predict_stockouts, limit=500)
            try:
                all_predictions = future.result(timeout=30)
            except concurrent.futures.TimeoutError:
                return (f"⏳ Stockout predictions are being calculated (Monte Carlo simulation running). "
                        f"Basic stock info:\n" + 
                        "\n".join([f"• {m.get('product_name', '')} {m.get('variant_name', '')}: {m.get('current_stock', 0)} units" 
                                   for m in search_result["matches"]]))

        # Filter to only the variants we found
        relevant = [p for p in all_predictions if p["variant_id"] in variant_ids]

    except Exception as e:
        return f"❌ Could not fetch stockout predictions: {e}"

    if not relevant:
        # Fallback: return basic stock info from search results
        report = f"📦 **{product_name.title()} — Stock Status:**\n\n"
        for m in search_result["matches"]:
            report += f"• **{m.get('product_name', '')} {m.get('variant_name', '')}** — {m.get('current_stock', 0)} units in stock\n"
        report += "\n⚠️ Stockout prediction not available for these items yet."
        return report

    # Step 3: Format enriched answer
    report = f"📦 **{product_name.title()} — Stockout Forecast ({len(relevant)} variants):**\n\n"
    
    # Sort by urgency
    relevant.sort(key=lambda x: x.get("metrics", {}).get("days_until_stockout", 999))
    
    for p in relevant:
        name = p.get("product_name", f"Variant {p['variant_id']}")
        days = p.get("metrics", {}).get("days_until_stockout", "N/A")
        stock = p.get("current_stock", "?")
        risk = p.get("risk_level", "unknown").upper()
        rec = p.get("recommendation", "")
        
        risk_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk, "⚪")
        
        report += f"{risk_emoji} **{name}** — {stock} units left\n"
        if isinstance(days, (int, float)):
            report += f"   Runs out in: **{days:.0f} days** | Risk: {risk}\n"
        if rec:
            report += f"   Recommendation: {rec}\n"
        report += "\n"

    return report


@tool
def get_product_basket_tool(product_name: str) -> str:
    """
    Finds what products are frequently bought together with the given product.
    Uses FP-Growth market basket analysis results.
    
    Examples: "what sells with Maggi", "cross-sell for Lays", 
              "what goes with bread", "combo suggestions for milk"
    """
    if not SEARCH_ENGINE or not getattr(SEARCH_ENGINE, "is_ready", True):
        return "⏳ Search engine warming up."

    # Step 1: Resolve product name
    search_result = SEARCH_ENGINE.search("product", product_name, limit=5)
    
    if isinstance(search_result, str):
        return f"Warning: Search engine returned text. Ensure Phase 1 ChromaDB migration is active. Result: {search_result}"

    if "error" in search_result:
        return search_result["message"]

    if not search_result.get("matches"):
        return f"No products found matching '{product_name}'."

    # Get the canonical product name from the best match
    best_match = search_result["matches"][0]
    canonical_name = best_match.get("product_name", product_name)
    variant_name = best_match.get("variant_name", "")

    # Step 2: Get FP-Growth rules from analytics cache
    try:
        from analytics import AnalyticsEngine
        from core import state as _state

        analytics = AnalyticsEngine(_state.raw_engine, base_dir=_state.BASE_DIR)
        dashboard = analytics.get_dashboard_metrics()
        dash_data = dashboard.get("data", dashboard)
        mb = dash_data.get("market_basket", {})
        rules = mb.get("rules", []) if isinstance(mb, dict) else []

    except Exception as e:
        return f"❌ Could not fetch market basket data: {e}"

    if not rules:
        return f"🛒 Market basket analysis not ready yet. Check back after the analytics pipeline runs."

    # Step 3: Filter rules where this product appears as antecedent
    search_term = canonical_name.lower()
    matching_rules = []
    
    for rule in rules:
        ant = rule.get("antecedent", [])
        ant_str = ant[0] if isinstance(ant, list) and ant else str(ant)
        if search_term in ant_str.lower():
            matching_rules.append(rule)

    if not matching_rules:
        return (f"🛒 No frequent buying patterns found for **{canonical_name}** yet.\n"
                f"This may mean it hasn't been sold enough times to establish patterns, "
                f"or the market basket cache needs to refresh.")

    # Step 4: Format results
    report = f"🛒 **What sells with {canonical_name} {variant_name}:**\n\n"
    for i, rule in enumerate(matching_rules[:8], 1):
        ant = rule.get("antecedent", ["?"])
        con = rule.get("consequent", ["?"])
        conf = rule.get("confidence", 0)
        lift = rule.get("lift", 0)
        ant_str = ant[0] if isinstance(ant, list) else str(ant).strip("[]'")
        con_str = con[0] if isinstance(con, list) else str(con).strip("[]'")
        report += f"{i}. **{ant_str}** → **{con_str}** | Confidence: {conf:.0%} | Lift: {lift:.2f}\n"

    report += f"\n💡 *Place these products near {canonical_name} to boost sales.*"
    return report


@tool
def get_customer_churn_for_product_tool(product_name: str) -> str:
    """
    Finds customers who have bought a specific product and checks their churn risk.
    Cross-references product buyers with XGBoost churn predictions.
    
    Examples: "are Lays buyers at churn risk", "which chips customers are leaving",
              "churn risk for customers who buy bread", "loyal buyers of Maggi"
    """
    if not SEARCH_ENGINE or not getattr(SEARCH_ENGINE, "is_ready", True):
        return "⏳ Search engine warming up."

    # Step 1: Resolve product to variant IDs
    search_result = SEARCH_ENGINE.search("product", product_name, limit=10)
    
    if isinstance(search_result, str):
        return f"Warning: Search engine returned text. Ensure Phase 1 ChromaDB migration is active. Result: {search_result}"

    if "error" in search_result:
        return search_result["message"]

    if not search_result.get("matches"):
        return f"No products found matching '{product_name}'."

    variant_ids = [m["variant_id"] for m in search_result["matches"] if "variant_id" in m]
    if not variant_ids:
        return "Could not extract variant IDs from search results."
    
    canonical = search_result["matches"][0].get("product_name", product_name)

    # Step 2: Find customers who have bought these variants
    try:
        from sqlalchemy import text
        from core import state as _state

        placeholders = ",".join([str(vid) for vid in variant_ids])
        with _state.raw_engine.connect() as conn:
            buyer_rows = conn.execute(text(f"""
                SELECT DISTINCT c.id, c.name
                FROM customer c
                JOIN credit_sale cs ON c.id = cs.customer_id
                JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE csi.variant_id IN ({placeholders})
            """)).fetchall()

    except Exception as e:
        return f"❌ Could not fetch buyer data: {e}"

    if not buyer_rows:
        return f"No customer purchase history found for '{canonical}'."

    buyer_ids = {row.id for row in buyer_rows}

    # Step 3: Get XGBoost churn predictions and filter to these buyers
    try:
        from analytics import AnalyticsEngine
        from core import state as _state

        analytics = AnalyticsEngine(_state.raw_engine, base_dir=_state.BASE_DIR)
        dashboard = analytics.get_dashboard_metrics()
        dash_data = dashboard.get("data", dashboard)
        all_churn = dash_data.get("churn_risk", [])

    except Exception as e:
        return f"❌ Could not fetch churn predictions: {e}"

    # Filter churn results to only buyers of this product
    at_risk = [
        c for c in all_churn
        if c.get("customer_id") in buyer_ids and c.get("risk_score", 0) >= 50
    ]
    safe = [
        c for c in all_churn
        if c.get("customer_id") in buyer_ids and c.get("risk_score", 0) < 50
    ]

    report = f"👥 **Churn Risk — Buyers of {canonical} ({len(buyer_ids)} customers total):**\n\n"
    
    if at_risk:
        at_risk.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
        report += f"🔴 **At Risk ({len(at_risk)} customers):**\n"
        for c in at_risk[:10]:
            report += (f"• **{c.get('name')}** — Risk: {c.get('risk_score', 0)}% | "
                      f"Inactive: {c.get('days_inactive', 0)} days | {c.get('trend', '')}\n")
    else:
        report += "✅ No high-risk churn detected among these buyers.\n"

    report += f"\n✅ **Loyal Buyers ({len(safe)} customers):** Regularly purchasing, low churn risk.\n"
    report += f"\n💡 *Consider a loyalty offer for at-risk {canonical} buyers to retain them.*"
    return report


@tool
def resolve_entity_tool(name: str, entity_type: str = "product") -> str:
    """
    Resolves a fuzzy name to exact database records using semantic search.
    Returns IDs and metadata. Use this when you need to find the exact ID 
    of a product, customer, or supplier before running a SQL query or analysis.
    
    entity_type: 'product', 'customer', or 'supplier'
    
    Examples: "resolve Maggi to product ID", "find supplier ID for Haldiram",
              "get customer ID for Ramesh Sharma"
    """
    if not SEARCH_ENGINE or not getattr(SEARCH_ENGINE, "is_ready", True):
        return "⏳ Search engine warming up."

    result = SEARCH_ENGINE.search(entity_type, name, limit=5)
    
    if isinstance(result, str):
        return f"Warning: Search engine returned text. Ensure Phase 1 ChromaDB migration is active. Result: {result}"

    if "error" in result:
        return result["message"]

    if not result.get("matches"):
        return f"No {entity_type} found matching '{name}'."

    lines = [f"🔍 **Resolved '{name}' → {entity_type} matches:**\n"]
    for m in result["matches"]:
        sim = m.get('similarity', '?')
        if entity_type == "product":
            lines.append(f"- ID: {m.get('variant_id')} | {m.get('product_name')} {m.get('variant_name')} "
                        f"| Category: {m.get('category')} | Stock: {m.get('current_stock')} | Match: {sim}%")
        elif entity_type == "customer":
            lines.append(f"- ID: {m.get('customer_id')} | {m.get('name')} | Mobile: {m.get('mobile')} | Match: {sim}%")
        elif entity_type == "supplier":
            lines.append(f"- ID: {m.get('supplier_id')} | {m.get('name')} | Mobile: {m.get('mobile')} | Match: {sim}%")

    return "\n".join(lines)


# --- COMBINED BUSINESS OVERVIEW (Single tool for strategic questions) ---



@tool
def get_business_overview_tool():
    """Returns a COMPREHENSIVE business overview in one call: revenue trends, top sellers,
    dead stock, customer segments, inventory alerts, and shopping patterns.
    USE THIS for broad strategic questions like 'how to increase sales', 'business summary',
    'give me insights', 'how are we doing'. This is faster than calling multiple tools.
    """
    try:
        from core import state as _state
        if not _state.raw_engine:
            return "Database not connected."

        report = ""
        with _state.raw_engine.connect() as c:
            # --- 1. REVENUE COMPARISON ---
            this_week = c.execute(text("""
                SELECT ROUND(COALESCE(SUM(csi.quantity * csi.price_at_sale), 0), 2)
                FROM credit_sale cs JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE date(cs.sale_date) >= date('now', 'localtime', '-7 days')
            """)).fetchone()[0] or 0

            last_week = c.execute(text("""
                SELECT ROUND(COALESCE(SUM(csi.quantity * csi.price_at_sale), 0), 2)
                FROM credit_sale cs JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE date(cs.sale_date) BETWEEN date('now', 'localtime', '-14 days') AND date('now', 'localtime', '-8 days')
            """)).fetchone()[0] or 0

            this_month = c.execute(text("""
                SELECT ROUND(COALESCE(SUM(csi.quantity * csi.price_at_sale), 0), 2)
                FROM credit_sale cs JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE strftime('%Y-%m', cs.sale_date) = strftime('%Y-%m', 'now', 'localtime')
            """)).fetchone()[0] or 0

            last_month = c.execute(text("""
                SELECT ROUND(COALESCE(SUM(csi.quantity * csi.price_at_sale), 0), 2)
                FROM credit_sale cs JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE strftime('%Y-%m', cs.sale_date) = strftime('%Y-%m', 'now', 'localtime', '-1 month')
            """)).fetchone()[0] or 0

            def pct(curr, prev):
                if prev == 0:
                    return "+∞%" if curr > 0 else "0%"
                return f"{((curr - prev) / prev) * 100:+.1f}%"

            w_arrow = "📈" if this_week >= last_week else "📉"
            m_arrow = "📈" if this_month >= last_month else "📉"
            report += f"## 📊 Revenue Overview\n"
            report += f"**This Week:** ₹{this_week:,.0f} vs Last: ₹{last_week:,.0f} {w_arrow} **{pct(this_week, last_week)}**\n"
            report += f"**This Month:** ₹{this_month:,.0f} vs Last: ₹{last_month:,.0f} {m_arrow} **{pct(this_month, last_month)}**\n\n"

            # --- 2. TOP 5 SELLERS ---
            top = c.execute(text("""
                SELECT p.name, pv.name as variant, SUM(csi.quantity) as qty,
                       ROUND(SUM(csi.quantity * csi.price_at_sale), 2) as rev
                FROM credit_sale_item csi
                JOIN credit_sale cs ON csi.sale_id = cs.id
                JOIN product_variant pv ON csi.variant_id = pv.id
                JOIN product p ON pv.product_id = p.id
                WHERE cs.sale_date >= date('now', 'localtime', '-30 days')
                GROUP BY pv.id ORDER BY rev DESC LIMIT 5
            """)).fetchall()

            if top:
                report += "## 🏆 Top Sellers (30 days)\n"
                for i, r in enumerate(top, 1):
                    report += f"{i}. **{r[0]} - {r[1]}** — {r[2]} units, ₹{r[3]:,.0f}\n"
                report += "\n"

            # --- 3. DEAD STOCK ---
            dead = c.execute(text("""
                SELECT p.name, pv.name, pv.current_stock
                FROM product_variant pv JOIN product p ON pv.product_id = p.id
                WHERE pv.current_stock > 0 AND pv.id NOT IN (
                    SELECT DISTINCT csi.variant_id FROM credit_sale_item csi
                    JOIN credit_sale cs ON csi.sale_id = cs.id
                    WHERE cs.sale_date >= date('now', 'localtime', '-30 days')
                ) LIMIT 5
            """)).fetchall()

            if dead:
                report += "## 💀 Dead Stock (No sales, 30 days)\n"
                for r in dead:
                    report += f"• {r[0]} - {r[1]} — **{r[2]} units** idle\n"
                report += "\n"

            # --- 4. URGENT RESTOCKING ---
            urgent = c.execute(text("""
                SELECT p.name, pv.name, pv.current_stock
                FROM product_variant pv JOIN product p ON pv.product_id = p.id
                WHERE pv.current_stock <= 5 AND pv.current_stock > 0
                ORDER BY pv.current_stock ASC LIMIT 5
            """)).fetchall()

            out_count = c.execute(
                text("SELECT COUNT(*) FROM product_variant WHERE current_stock <= 0")
            ).fetchone()[0]

            if out_count > 0 or urgent:
                report += "## 📦 Inventory Alerts\n"
                if out_count:
                    report += f"❌ **{out_count} item(s) out of stock**\n"
                for r in urgent:
                    report += f"⚠️ {r[0]} - {r[1]} — only **{r[2]} left**\n"
                report += "\n"

            # --- 5. TOP CUSTOMERS ---
            top_cust = c.execute(text("""
                SELECT c.name, ROUND(SUM(csi.quantity * csi.price_at_sale), 2) as spent,
                       COUNT(DISTINCT cs.id) as orders
                FROM customer c
                JOIN credit_sale cs ON c.id = cs.customer_id
                JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE cs.sale_date >= date('now', 'localtime', '-30 days')
                GROUP BY c.id ORDER BY spent DESC LIMIT 5
            """)).fetchall()

            if top_cust:
                report += "## 👥 Top Customers (30 days)\n"
                for i, r in enumerate(top_cust, 1):
                    report += f"{i}. **{r[0]}** — ₹{r[1]:,.0f} ({r[2]} orders)\n"
                report += "\n"

            # --- 6. CATEGORY BREAKDOWN ---
            cats = c.execute(text("""
                SELECT p.category, ROUND(SUM(csi.quantity * csi.price_at_sale), 2) as rev
                FROM credit_sale cs
                JOIN credit_sale_item csi ON cs.id = csi.sale_id
                JOIN product_variant pv ON csi.variant_id = pv.id
                JOIN product p ON pv.product_id = p.id
                WHERE strftime('%Y-%m', cs.sale_date) = strftime('%Y-%m', 'now', 'localtime')
                GROUP BY p.category ORDER BY rev DESC LIMIT 5
            """)).fetchall()

            if cats:
                report += "## 📂 Top Categories (This Month)\n"
                total = sum(r[1] for r in cats)
                for r in cats:
                    share = (r[1] / total * 100) if total else 0
                    report += f"• **{r[0]}**: ₹{r[1]:,.0f} ({share:.0f}%)\n"

        return report if report else "No data available yet."
    except Exception as e:
        return f"Error: {e}"


# --- BUSINESS INTELLIGENCE TOOLS ---


@tool
def get_sales_trends_tool(period: str = "daily"):
    """Returns sales revenue trends with growth percentages.
    Use for questions about sales trends, revenue direction, growth, or performance over time.
    period: 'daily' (last 14 days), 'weekly' (last 8 weeks), or 'monthly' (last 6 months).
    """
    try:
        from core import state as _state
        if not _state.raw_engine:
            return "Database not connected."

        if period == "weekly":
            query = """
                SELECT strftime('%Y-W%W', cs.sale_date) as period,
                       ROUND(SUM(csi.quantity * csi.price_at_sale), 2) as revenue,
                       COUNT(DISTINCT cs.id) as transactions
                FROM credit_sale cs
                JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE cs.sale_date >= date('now', 'localtime', '-56 days')
                GROUP BY period ORDER BY period DESC LIMIT 8
            """
        elif period == "monthly":
            query = """
                SELECT strftime('%Y-%m', cs.sale_date) as period,
                       ROUND(SUM(csi.quantity * csi.price_at_sale), 2) as revenue,
                       COUNT(DISTINCT cs.id) as transactions
                FROM credit_sale cs
                JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE cs.sale_date >= date('now', 'localtime', '-180 days')
                GROUP BY period ORDER BY period DESC LIMIT 6
            """
        else:  # daily
            query = """
                SELECT date(cs.sale_date) as period,
                       ROUND(SUM(csi.quantity * csi.price_at_sale), 2) as revenue,
                       COUNT(DISTINCT cs.id) as transactions
                FROM credit_sale cs
                JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE cs.sale_date >= date('now', 'localtime', '-14 days')
                GROUP BY period ORDER BY period DESC LIMIT 14
            """

        with _state.raw_engine.connect() as c:
            rows = c.execute(text(query)).fetchall()

        if not rows:
            return "No sales data available for this period."

        lines = []
        for i, r in enumerate(rows):
            line = f"• **{r[0]}**: ₹{r[1]:,.0f} ({r[2]} txns)"
            if i < len(rows) - 1:
                prev_rev = rows[i + 1][1] or 1
                growth = ((r[1] - prev_rev) / prev_rev) * 100
                arrow = "📈" if growth > 0 else "📉" if growth < 0 else "➡️"
                line += f" {arrow} {growth:+.1f}%"
            lines.append(line)

        return f"📊 **Sales Trends ({period.title()}):**\n\n" + "\n".join(lines)
    except Exception as e:
        return f"Error fetching trends: {e}"


@tool
def get_top_performers_tool(metric: str = "revenue", limit: int = 10):
    """Returns best AND worst performing products.
    Use for questions about top sellers, slow movers, dead stock, or product performance.
    metric: 'revenue' or 'quantity'. limit: number of items (default 10).
    """
    try:
        from core import state as _state
        if not _state.raw_engine:
            return "Database not connected."

        with _state.raw_engine.connect() as c:
            top = c.execute(
                text("""
                SELECT p.name, pv.name as variant, p.category,
                       SUM(csi.quantity) as qty_sold,
                       ROUND(SUM(csi.quantity * csi.price_at_sale), 2) as total_revenue
                FROM credit_sale_item csi
                JOIN credit_sale cs ON csi.sale_id = cs.id
                JOIN product_variant pv ON csi.variant_id = pv.id
                JOIN product p ON pv.product_id = p.id
                WHERE cs.sale_date >= date('now', 'localtime', '-30 days')
                GROUP BY pv.id
                ORDER BY total_revenue DESC
                LIMIT :limit
            """),
                {"limit": limit},
            ).fetchall()

            dead = c.execute(
                text("""
                SELECT p.name, pv.name as variant, pv.current_stock, p.category
                FROM product_variant pv
                JOIN product p ON pv.product_id = p.id
                WHERE pv.current_stock > 0
                AND pv.id NOT IN (
                    SELECT DISTINCT csi.variant_id
                    FROM credit_sale_item csi
                    JOIN credit_sale cs ON csi.sale_id = cs.id
                    WHERE cs.sale_date >= date('now', 'localtime', '-30 days')
                )
                ORDER BY pv.current_stock DESC
                LIMIT :limit
            """),
                {"limit": limit},
            ).fetchall()

        report = "🏆 **Top Sellers (Last 30 Days):**\n\n"
        if top:
            for i, r in enumerate(top, 1):
                report += (
                    f"{i}. **{r[0]} - {r[1]}** [{r[2]}] — {r[3]} units, ₹{r[4]:,.0f}\n"
                )
        else:
            report += "No sales data in last 30 days.\n"

        report += f"\n💀 **Dead Stock (No sales in 30 days, still in stock):**\n\n"
        if dead:
            for r in dead:
                report += (
                    f"• {r[0]} - {r[1]} [{r[3]}] — **{r[2]} units** sitting idle\n"
                )
        else:
            report += "No dead stock detected — all products are selling!\n"

        return report
    except Exception as e:
        return f"Error: {e}"


@tool
def get_customer_segments_tool():
    """Returns customer segments: high-value, frequent, declining, and inactive.
    Use for questions about customer behavior, loyalty, who buys most, or customer strategy.
    """
    try:
        from core import state as _state
        if not _state.raw_engine:
            return "Database not connected."

        with _state.raw_engine.connect() as c:
            top_spenders = c.execute(text("""
                SELECT c.name, ROUND(SUM(csi.quantity * csi.price_at_sale), 2) as total_spent,
                       COUNT(DISTINCT cs.id) as total_orders,
                       MAX(cs.sale_date) as last_visit
                FROM customer c
                JOIN credit_sale cs ON c.id = cs.customer_id
                JOIN credit_sale_item csi ON cs.id = csi.sale_id
                GROUP BY c.id
                ORDER BY total_spent DESC LIMIT 10
            """)).fetchall()

            inactive = c.execute(text("""
                SELECT c.name, MAX(cs.sale_date) as last_visit,
                       CAST(julianday('now', 'localtime') - julianday(MAX(cs.sale_date)) AS INTEGER) as days_inactive,
                       COUNT(DISTINCT cs.id) as total_orders
                FROM customer c
                JOIN credit_sale cs ON c.id = cs.customer_id
                GROUP BY c.id
                HAVING days_inactive > 30
                ORDER BY days_inactive DESC LIMIT 10
            """)).fetchall()

            new_custs = c.execute(text("""
                SELECT c.name, MIN(cs.sale_date) as first_visit,
                       ROUND(SUM(csi.quantity * csi.price_at_sale), 2) as first_spend
                FROM customer c
                JOIN credit_sale cs ON c.id = cs.customer_id
                JOIN credit_sale_item csi ON cs.id = csi.sale_id
                GROUP BY c.id
                HAVING date(first_visit) >= date('now', 'localtime', '-14 days')
                ORDER BY first_visit DESC LIMIT 10
            """)).fetchall()

            avg_basket = c.execute(text("""
                SELECT ROUND(AVG(basket), 2) FROM (
                    SELECT SUM(csi.quantity * csi.price_at_sale) as basket
                    FROM credit_sale cs
                    JOIN credit_sale_item csi ON cs.id = csi.sale_id
                    WHERE cs.sale_date >= date('now', 'localtime', '-30 days')
                    GROUP BY cs.id
                )
            """)).fetchone()

        report = f"👥 **Customer Intelligence Report:**\n\n"
        report += (
            f"🧺 Average Basket Size (30 days): **₹{avg_basket[0] or 0:,.0f}**\n\n"
        )

        report += "💎 **Top 10 Customers by Spend:**\n"
        for i, r in enumerate(top_spenders, 1):
            report += f"{i}. **{r[0]}** — ₹{r[1]:,.0f} ({r[2]} orders, last: {r[3]})\n"

        if inactive:
            report += f"\n⚠️ **Inactive Customers (30+ days):**\n"
            for r in inactive:
                report += f"• **{r[0]}** — {r[2]} days since last visit ({r[3]} past orders)\n"

        if new_custs:
            report += f"\n🆕 **New Customers (Last 14 Days):**\n"
            for r in new_custs:
                report += f"• **{r[0]}** — First visit: {r[1]}, spent ₹{r[2]:,.0f}\n"

        return report
    except Exception as e:
        return f"Error: {e}"


@tool
def get_inventory_velocity_tool():
    """Returns inventory velocity: fast movers, slow movers, and days-of-stock remaining.
    Use for questions about inventory health, what to restock, stock running out, or reorder.
    """
    try:
        from core import state as _state
        if not _state.raw_engine:
            return "Database not connected."

        with _state.raw_engine.connect() as c:
            velocity = c.execute(text("""
                SELECT p.name, pv.name as variant, pv.current_stock,
                       ROUND(COALESCE(SUM(csi.quantity), 0) / 30.0, 2) as daily_velocity,
                       CASE
                           WHEN COALESCE(SUM(csi.quantity), 0) > 0 THEN ROUND(pv.current_stock / (SUM(csi.quantity) / 30.0), 1)
                           ELSE 999
                       END as days_of_stock
                FROM product_variant pv
                JOIN product p ON pv.product_id = p.id
                LEFT JOIN credit_sale_item csi ON pv.id = csi.variant_id
                LEFT JOIN credit_sale cs ON csi.sale_id = cs.id
                    AND cs.sale_date >= date('now', 'localtime', '-30 days')
                GROUP BY pv.id
                HAVING pv.current_stock > 0
                ORDER BY days_of_stock ASC
                LIMIT 30
            """)).fetchall()

            out_of_stock = c.execute(text("""
                SELECT p.name, pv.name as variant, p.category
                FROM product_variant pv
                JOIN product p ON pv.product_id = p.id
                WHERE pv.current_stock <= 0
            """)).fetchall()

        report = "📦 **Inventory Velocity Report:**\n\n"

        if out_of_stock:
            report += f"❌ **Out of Stock ({len(out_of_stock)} items):**\n"
            for r in out_of_stock[:10]:
                report += f"• {r[0]} - {r[1]} [{r[2]}]\n"
            report += "\n"

        urgent = [r for r in velocity if r[4] < 7 and r[4] != 999]
        if urgent:
            report += "🔴 **Restock Urgently (< 7 days of stock):**\n"
            for r in urgent:
                report += f"• **{r[0]} - {r[1]}** — {r[2]} units left, sells {r[3]}/day → **{r[4]} days**\n"
            report += "\n"

        fast = sorted(
            [r for r in velocity if r[3] > 0], key=lambda x: x[3], reverse=True
        )[:10]
        if fast:
            report += "🚀 **Fast Movers (Highest daily sales):**\n"
            for r in fast:
                report += f"• {r[0]} - {r[1]} — **{r[3]} units/day**, {r[2]} in stock\n"

        return report
    except Exception as e:
        return f"Error: {e}"


@tool
def get_revenue_comparison_tool():
    """Compares revenue across periods: this week vs last, this month vs last, with category breakdown.
    Use for questions about revenue growth, performance comparison, or 'how are we doing'.
    """
    try:
        from core import state as _state
        if not _state.raw_engine:
            return "Database not connected."

        with _state.raw_engine.connect() as c:
            this_week = c.execute(text("""
                SELECT ROUND(COALESCE(SUM(csi.quantity * csi.price_at_sale), 0), 2)
                FROM credit_sale cs JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE date(cs.sale_date) >= date('now', 'localtime', '-7 days')
            """)).fetchone()[0] or 0

            last_week = c.execute(text("""
                SELECT ROUND(COALESCE(SUM(csi.quantity * csi.price_at_sale), 0), 2)
                FROM credit_sale cs JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE date(cs.sale_date) BETWEEN date('now', 'localtime', '-14 days') AND date('now', 'localtime', '-8 days')
            """)).fetchone()[0] or 0

            this_month = c.execute(text("""
                SELECT ROUND(COALESCE(SUM(csi.quantity * csi.price_at_sale), 0), 2)
                FROM credit_sale cs JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE strftime('%Y-%m', cs.sale_date) = strftime('%Y-%m', 'now', 'localtime')
            """)).fetchone()[0] or 0

            last_month = c.execute(text("""
                SELECT ROUND(COALESCE(SUM(csi.quantity * csi.price_at_sale), 0), 2)
                FROM credit_sale cs JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE strftime('%Y-%m', cs.sale_date) = strftime('%Y-%m', 'now', 'localtime', '-1 month')
            """)).fetchone()[0] or 0

            categories = c.execute(text("""
                SELECT p.category, ROUND(SUM(csi.quantity * csi.price_at_sale), 2) as revenue
                FROM credit_sale cs
                JOIN credit_sale_item csi ON cs.id = csi.sale_id
                JOIN product_variant pv ON csi.variant_id = pv.id
                JOIN product p ON pv.product_id = p.id
                WHERE strftime('%Y-%m', cs.sale_date) = strftime('%Y-%m', 'now', 'localtime')
                GROUP BY p.category
                ORDER BY revenue DESC LIMIT 10
            """)).fetchall()

        def pct(curr, prev):
            if prev == 0:
                return "+∞%" if curr > 0 else "0%"
            return f"{((curr - prev) / prev) * 100:+.1f}%"

        week_arrow = "📈" if this_week >= last_week else "📉"
        month_arrow = "📈" if this_month >= last_month else "📉"

        report = f"📊 **Revenue Comparison:**\n\n"
        report += f"**This Week:** ₹{this_week:,.0f} vs Last Week: ₹{last_week:,.0f} {week_arrow} **{pct(this_week, last_week)}**\n"
        report += f"**This Month:** ₹{this_month:,.0f} vs Last Month: ₹{last_month:,.0f} {month_arrow} **{pct(this_month, last_month)}**\n\n"

        if categories:
            report += "📂 **Revenue by Category (This Month):**\n"
            total_cat = sum(r[1] for r in categories)
            for r in categories:
                share = (r[1] / total_cat * 100) if total_cat > 0 else 0
                report += f"• **{r[0]}**: ₹{r[1]:,.0f} ({share:.1f}%)\n"

        return report
    except Exception as e:
        return f"Error: {e}"
