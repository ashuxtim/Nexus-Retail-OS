import os
import sys

sys.path.append("/home/ashuxtim/Documents/Projects/Nexus-Retail-OS/python_server")
from core import state
from sqlalchemy import create_engine
from ai_engine.agent_builder import build_nexus_agent
from vector_store import SmartSearchEngine
from ai_engine.tools import set_context
from analytics import AnalyticsEngine
import time
from dotenv import load_dotenv

load_dotenv("/home/ashuxtim/Documents/Projects/Nexus-Retail-OS/python_server/.env")

base_dir = state.BASE_DIR
db_path = state.DB_PATH

engine = create_engine(f"sqlite:///{db_path}")
state.raw_engine = engine

search_engine = SmartSearchEngine(db_path, base_dir)
search_engine.initialize()
print("Warming up search engine...")
while not search_engine.is_ready:
    time.sleep(1)
state.search_engine = search_engine

analytics = AnalyticsEngine(engine, base_dir=base_dir)
state.analytics_engine = analytics
set_context(engine, search_engine, getattr(state, "ANALYTICS_CACHE", {}))

import json
config_path = state.CONFIG_PATH
try:
    with open(config_path, "r") as f:
        config = json.load(f)
    groq_key = config.get("GROQ_API_KEY")
except Exception:
    groq_key = None

if not groq_key:
    print("WARNING: GROQ_API_KEY not found in config.json.")

agent, _ = build_nexus_agent(engine, groq_key)

queries = [
    "how many types of chips and when will stock finish",
    "which cold drinks are running low",
    "customers who buy Lays, are any of them at churn risk",
    "what do people buy with Maggi",
    "find supplier for haldiram",
    "get ID for Ramesh Sharma"
]

for q in queries:
    print(f"\n========== QUERY: {q} ==========\n")
    try:
        res = agent.invoke({"messages": [("user", q)]})
        print(f"Final Response:\n{res['messages'][-1].content}")
        print("\n--- Tool Calls Made By Agent ---")
        for m in res["messages"]:
            if hasattr(m, "tool_calls") and m.tool_calls:
                for t in m.tool_calls:
                    print(f"Called: {t['name']} with args {t['args']}")
    except Exception as e:
        print(f"Error during query: {e}")
