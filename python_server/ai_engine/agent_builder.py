# FILE: python_server/ai_engine/agent_builder.py

from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import create_sql_agent
from langchain_core.messages import SystemMessage

# Import the Safety Guard
from .safety import SafetyGuard

# Import ALL tools from your tools.py
from .tools import (
    search_catalog_tool,
    search_supplier_tool,
    check_churn_risk_tool,
    get_market_insights_tool,
    add_customer_tool,
    delete_customer_tool,
    update_customer_details_tool,
    add_product_tool,
    update_product_tool,
    delete_product_tool,
    record_sale_tool,
    delete_last_sale_tool,
    record_purchase_tool,
    delete_last_purchase_tool,
)


def build_nexus_agent(raw_engine, groq_key):
    """
    Initializes LLMs, Safety Layer, and the SQL Agent.
    Returns: (agent_executor, safety_guard)
    """
    if not groq_key:
        return None, None

    # 1. Initialize LLMs (Preserving exact model names)
    # Router: Fast model for Safety Checks & Intent Classification
    router_llm = ChatGroq(
        groq_api_key=groq_key, model_name="llama-3.1-8b-instant", temperature=0
    )

    # Agent: Smart model for Tool Execution
    agent_llm = ChatGroq(
        groq_api_key=groq_key, model_name="llama-3.3-70b-versatile", temperature=0
    )

    # 2. Initialize Safety Guard
    safety = SafetyGuard(router_llm)

    # 3. Setup LangChain Database wrapper
    db = SQLDatabase(raw_engine)

    # 4. Define System Instructions
    system_instructions = """
    You are 'NexusRetail OS AI'. You are an ADMINISTRATOR.
    1. You HAVE PERMISSION to modify the database.
    2. If user confirms 'YES', EXECUTE the action.
    3. Use tools. Do not guess.
    4. Interpret 'ad' as 'add', 'del' as 'delete', 'cust' as 'customer'.
    """

    # 5. Create the Agent
    agent_executor = create_sql_agent(
        llm=agent_llm,
        db=db,
        agent_type="openai-tools",
        verbose=False,
        extra_tools=[
            # Search & Analytics
            search_catalog_tool,
            search_supplier_tool,
            check_churn_risk_tool,
            get_market_insights_tool,
            # Customer CRUD
            add_customer_tool,
            delete_customer_tool,
            update_customer_details_tool,
            # Product CRUD
            add_product_tool,
            update_product_tool,
            delete_product_tool,
            # Transactions
            record_sale_tool,
            delete_last_sale_tool,
            record_purchase_tool,
            delete_last_purchase_tool,
        ],
        agent_kwargs={"system_message": SystemMessage(content=system_instructions)},
    )

    return agent_executor, safety
