# FILE: python_server/ai_engine/agent_builder.py
# Lean agent using langgraph — only analytics/search tools, no CRUD.

from langchain_groq import ChatGroq
from langchain_core.tools import tool as lc_tool
from sqlalchemy import text

from langgraph.prebuilt import create_react_agent

from .tools import (
    search_catalog_tool,
    search_supplier_tool,
    check_churn_risk_tool,
    get_market_insights_tool,
    get_business_overview_tool,
    get_sales_trends_tool,
    get_top_performers_tool,
    get_customer_segments_tool,
    get_inventory_velocity_tool,
    get_revenue_comparison_tool,
)

# Module-level engine ref, set during build
_RAW_ENGINE = None


def build_nexus_agent(raw_engine, groq_key):
    """
    Initializes LLMs and the LEAN ReAct Agent (analytics only).
    Returns: (agent, router_llm)
    """
    global _RAW_ENGINE
    _RAW_ENGINE = raw_engine

    if not groq_key:
        return None, None

    # 1. LLMs
    router_llm = ChatGroq(
        groq_api_key=groq_key, model_name="llama-3.1-8b-instant", temperature=0
    )
    agent_llm = ChatGroq(
        groq_api_key=groq_key,
        model_name="meta-llama/llama-4-scout-17b-16e-instruct",
        temperature=0,
    )

    # 2. Custom SQL query tool for ad-hoc analytical questions
    @lc_tool
    def run_sql_query(query: str) -> str:
        """Run a READ-ONLY SQL query against the retail database.
        Use this for analytical questions like 'sales by category' or 'revenue trends'.
        Only SELECT queries are allowed.

        Available tables: customer, product, product_variant, credit_sale, credit_sale_item,
        supplier, purchase_invoice, purchase_item.

        Key columns:
        - customer: id, name, mobile, address
        - product: id, name, category
        - product_variant: id, product_id, name, price, current_stock, unit
        - credit_sale: id, customer_id, sale_date
        - credit_sale_item: id, sale_id, variant_id, quantity, price_at_sale
        - supplier: id, name, mobile
        - purchase_invoice: id, supplier_id, invoice_date
        - purchase_item: id, invoice_id, variant_id, quantity, unit_cost
        """
        sql = query.strip()
        if not sql.upper().startswith("SELECT"):
            return "❌ Only SELECT queries are allowed."
        try:
            with _RAW_ENGINE.connect() as c:
                rows = c.execute(text(sql)).fetchall()
                if not rows:
                    return "No results found."
                # Limit output size
                result_lines = [str(dict(row._mapping)) for row in rows[:30]]
                output = "\n".join(result_lines)
                if len(rows) > 30:
                    output += f"\n... ({len(rows)} total rows, showing first 30)"
                return output
        except Exception as e:
            return f"❌ SQL Error: {str(e)}"

    # 3. Build tool list — 11 tools total
    all_tools = [
        search_catalog_tool,
        search_supplier_tool,
        get_business_overview_tool,
        check_churn_risk_tool,
        get_market_insights_tool,
        get_sales_trends_tool,
        get_top_performers_tool,
        get_customer_segments_tool,
        get_inventory_velocity_tool,
        get_revenue_comparison_tool,
        run_sql_query,
    ]

    # 4. System prompt
    system_prompt = """You are 'NexusRetail OS AI', a retail business intelligence assistant for an Indian retail store.

CRITICAL RULES:
1. GIVE DIRECT, CONCLUSIVE ANSWERS. NEVER ask follow-up questions like "Would you like..." or "Should I...". Just answer fully.
2. ALWAYS use tools. NEVER say "I don't know" — call a tool instead.
3. You are READ-ONLY. You CANNOT add, delete, or update any records.
4. Use Indian Rupees (₹) for all currency.
5. Be concise. Use markdown headers, bullet points and bold for key numbers.
6. PREFER calling ONE comprehensive tool over calling many small ones.

TOOL SELECTION GUIDE (IMPORTANT — pick the RIGHT tool):
- "How to increase sales?" / "Business summary" / "Give me insights" / "How are we doing?" → **get_business_overview_tool** (ONE call, returns everything)
- Product/customer search → search_catalog_tool / search_supplier_tool
- "Revenue this week vs last" → get_revenue_comparison_tool
- "Sales trends" / "Daily/weekly sales" → get_sales_trends_tool
- "Top sellers" / "Dead stock" → get_top_performers_tool
- "Inventory status" / "What to restock" → get_inventory_velocity_tool
- "Customer insights" / "Who buys most" → get_customer_segments_tool
- "Churn risk" / "Losing customers" → check_churn_risk_tool
- "Shopping patterns" / "What goes together" → get_market_insights_tool
- Any other data question → run_sql_query with SELECT query

When answering, structure your response with markdown:
1. **Current Situation** (numbers and trends)
2. **Key Insights** (what the data tells us)
3. **Action Items** (specific, actionable next steps)

DATABASE SCHEMA (SQLite):
- customer(id, name, mobile, address, balance)
- product(id, name, category)
- product_variant(id, product_id, name, price, current_stock)
- credit_sale(id, customer_id, sale_date)
- credit_sale_item(id, sale_id, variant_id, quantity, price_at_sale)
- payment(id, customer_id, payment_date, amount)
- supplier(id, name, mobile)
- purchase_invoice(id, supplier_id, invoice_date, total_amount)
- purchase_item(id, invoice_id, variant_id, quantity, unit_cost)

IMPORTANT: sale_date and invoice_date store full datetime strings. Use date(sale_date) for date comparisons.
Example: WHERE date(cs.sale_date) = date('now', 'localtime')"""

    # 5. Create lean ReAct agent (11 tools)
    agent = create_react_agent(agent_llm, all_tools, prompt=system_prompt)

    return agent, router_llm
