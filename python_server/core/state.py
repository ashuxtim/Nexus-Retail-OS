# FILE: python_server/core/state.py
# Centralised shared state — imported by routes and startup.

import os
import sys
import threading

# --- Path Setup ---
if "NEXUS_USER_DATA" in os.environ:
    BASE_DIR = os.environ["NEXUS_USER_DATA"]
elif sys.platform == "win32":
    BASE_DIR = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
else:
    BASE_DIR = os.path.join(os.path.expanduser("~"), ".config", "NexusRetailOS")

os.makedirs(BASE_DIR, exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, "nexus.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# --- Mutable Singletons (set by startup.py, read by routes) ---
raw_engine = None
agent_executor = None
analytics_engine = None
search_engine = None
safety_guard = None
AI_INIT_FAILED = False

# Thread-safe lock for ANALYTICS_CACHE mutations
_cache_lock = threading.Lock()

ANALYTICS_CACHE = {"status": "processing", "data": {}}
