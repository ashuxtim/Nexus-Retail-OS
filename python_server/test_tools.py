import os
import sys

sys.path.append("/home/ashuxtim/Documents/Projects/Nexus-Retail-OS/python_server")

from core import state
from sqlalchemy import create_engine
from ai_engine.tools import (
    set_context, 
    search_catalog_tool, 
    get_product_stockout_tool, 
    get_customer_churn_for_product_tool, 
    get_product_basket_tool, 
    resolve_entity_tool
)
from vector_store import SmartSearchEngine
from analytics import AnalyticsEngine
import time

base_dir = state.BASE_DIR
db_path = state.DB_PATH

engine = create_engine(f"sqlite:///{db_path}")
state.raw_engine = engine

# Init search engine
search_engine = SmartSearchEngine(db_path, base_dir)
search_engine.initialize()
print("Warming up search engine...")
while not search_engine.is_ready:
    time.sleep(1)

state.search_engine = search_engine

# Init analytics engine
analytics = AnalyticsEngine(engine, base_dir=base_dir)
state.analytics_engine = analytics

set_context(engine, search_engine, {})

print("\n--- Test 1: get_product_stockout_tool ---")
print(get_product_stockout_tool.invoke("chips"))

print("\n--- Test 2: get_product_stockout_tool 'cold drinks' ---")
print(get_product_stockout_tool.invoke("cold drinks"))

print("\n--- Test 3: get_customer_churn_for_product_tool 'Lays' ---")
print(get_customer_churn_for_product_tool.invoke("Lays"))

print("\n--- Test 4: get_product_basket_tool 'Maggi' ---")
print(get_product_basket_tool.invoke("Maggi"))

print("\n--- Test 5: search_catalog_tool 'haldiram' 'supplier' ---")
# Langchain tools might need kwargs if multiple args
try:
    print(search_catalog_tool.invoke({"search_term": "haldiram", "category": "supplier"}))
except Exception as e:
    print(e)
    
print("\n--- Test 6: resolve_entity_tool 'Ramesh Sharma' 'customer' ---")
try:
    print(resolve_entity_tool.invoke({"name": "Ramesh Sharma", "entity_type": "customer"}))
except Exception as e:
    print(e)
