import sys
import os
import multiprocessing

# 1. CRITICAL FIX: Force UTF-8 encoding immediately
if os.name == "nt":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# 2. LOGGING: Redirect output to file (Persistent Logs)
try:
    # Always write to file in Production
    if "NEXUS_USER_DATA" in os.environ:
        _base = os.environ["NEXUS_USER_DATA"]
    elif sys.platform == "win32":
        _base = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
    else:
        _base = os.path.join(os.path.expanduser("~"), ".config", "NexusRetailOS")
    log_dir = os.path.join(_base, "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_path = os.path.join(log_dir, "console_output.log")

    # Open file with explicit UTF-8 encoding
    sys.stdout = open(log_path, "a", buffering=1, encoding="utf-8")
    sys.stderr = sys.stdout

except Exception as e:
    # If logging fails, silence output to prevent crash
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")

# ==============================================================================
# 3. IMPORTS
# ==============================================================================

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Ensure stdout/stderr are not None (safety net for frozen/packaged apps)
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

# --- Route Modules ---
from core.startup import initialize_ai
from routes.settings import router as settings_router
from routes.ai_chat import router as ai_chat_router
from routes.media import router as media_router
from routes.analytics import router as analytics_router

# ==============================================================================
# 4. APP SETUP
# ==============================================================================

app = FastAPI(title="NexusRetail OS AI Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register Routers ---
app.include_router(settings_router)
app.include_router(ai_chat_router)
app.include_router(media_router)
app.include_router(analytics_router)

# --- Startup ---
initialize_ai()

if __name__ == "__main__":
    # This prevents Prophet/Torch from spawning infinite copies of the app.
    multiprocessing.freeze_support()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None, use_colors=False)
