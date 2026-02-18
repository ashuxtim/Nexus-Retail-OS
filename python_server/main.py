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
import io
import json
import base64
import re
import asyncio
import uvicorn
import threading
from datetime import datetime, timedelta
from typing import List, Optional

from core.time_utils import now as tz_now, sqlite_connect_args

# FastAPI & Core
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Database
from sqlalchemy import text, create_engine, event
import pandas as pd
import numpy as np

# --- NEW AI ENGINE IMPORTS ---
from ai_engine.agent_builder import build_nexus_agent
from ai_engine.tools import set_context
from ai_engine.vision import scan_receipt_engine
from ai_engine.voice import transcribe_audio_engine

# Local Modules (Preserved)
from scripts.backend_logging import get_logger, log_critical_error
from analytics import AnalyticsEngine
from vector_store import SmartSearchEngine
from models.stockout.predictor import StockoutPredictor
from models.churn.churn_predictor import ChurnPredictor
from models.market_basket.analyzer import MarketBasketAnalyzer
from models.forecast.forecaster import RevenueForecaster

# --- CONFIGURATION & LOGGING ---
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

logger = get_logger("NexusAI_Backend")

# Path Setup
if "NEXUS_USER_DATA" in os.environ:
    BASE_DIR = os.environ["NEXUS_USER_DATA"]
elif sys.platform == "win32":
    BASE_DIR = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
else:
    BASE_DIR = os.path.join(os.path.expanduser("~"), ".config", "NexusRetailOS")

os.makedirs(BASE_DIR, exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, "nexus.db")
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


# Model Validation Import
try:
    from eval.model_performance import evaluate_churn_model, evaluate_forecast_model
    from mlops.model_manager import ModelManager

    MODEL_VALIDATION_AVAILABLE = True
except ImportError:
    MODEL_VALIDATION_AVAILABLE = False
    logger.warning("Model Validation module not found. Auto-training disabled.")

app = FastAPI(title="NexusRetail OS AI Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- GLOBAL STATE ---
raw_engine = None
db = None
agent_executor = None
analytics_engine = None
search_engine = None

# ✅ NEW: Replaces router_llm and SAFETY_CONTEXT
safety_guard = None

# Initialization failure flag — checked by endpoints
AI_INIT_FAILED = False

# Thread-safe lock for ANALYTICS_CACHE mutations
_cache_lock = threading.Lock()

# Initialize with safe defaults
ANALYTICS_CACHE = {
    "churn_risk": [],
    "market_basket": "Initializing...",
    "segments": "",
    "stockouts": [],
    "forecast": {"history": [], "forecast": [], "trend": "flat"},
    "status": "processing",
}

# --- HELPER FUNCTIONS ---


def load_settings():
    """
    Load settings from environment variables (injected by Electron on startup).
    Fallback to config.json for non-sensitive settings only.
    """
    config = {}

    # 1. Check environment variables FIRST (injected by Electron)
    if "GROQ_API_KEY" in os.environ:
        config["GROQ_API_KEY"] = os.environ["GROQ_API_KEY"]
    if "GOOGLE_API_KEY" in os.environ:
        config["GOOGLE_API_KEY"] = os.environ["GOOGLE_API_KEY"]

    # 2. Load non-sensitive settings from disk (if exists)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r") as f:
                disk_config = json.load(f)
                # Merge non-sensitive settings
                for key, value in disk_config.items():
                    if key not in ["GROQ_API_KEY", "GOOGLE_API_KEY"]:
                        config[key] = value
        except:
            pass

    return config


def save_settings(settings):
    """
    DEPRECATED: API keys are now managed by Electron's encrypted database.
    This function is kept for backwards compatibility but no longer saves keys to disk.
    Keys are injected via POST /settings on startup and kept in memory only.
    """
    pass  # Keys stored in Electron's encrypted DB, not here


def clean_number(val):
    if isinstance(val, (int, float)):
        return float(val)
    clean = re.sub(r"[^0-9.]", "", str(val))
    try:
        return float(clean)
    except:
        return 1.0


def run_daily_model_validation():
    if not MODEL_VALIDATION_AVAILABLE:
        return

    # Only run Forecast Validation here (Churn is handled by ensure_churn_model_trained)
    try:
        logger.info("📈 Running Daily Forecast Validation...")
        evaluate_forecast_model()  # Saves result to DB directly
        logger.info("✅ Daily Forecast Validation Complete")
    except Exception as e:
        logger.error(f"Daily Forecast Validation Failed: {e}")


# --- BACKGROUND WORKER & INITIALIZATION ---


def run_analytics_pipeline():
    """Runs heavy math in background thread and updates memory/disk."""
    global ANALYTICS_CACHE
    if not analytics_engine:
        return

    logger.info("Running background analytics pipeline...")
    with _cache_lock:
        ANALYTICS_CACHE["status"] = "processing"

    result = analytics_engine.compute_and_cache_dashboard()

    with _cache_lock:
        if result:
            # Key-by-key update preserves the dict reference held by tools.py
            for key, value in result.items():
                ANALYTICS_CACHE[key] = value
            ANALYTICS_CACHE["status"] = "ready"
        else:
            ANALYTICS_CACHE["status"] = "error"


def run_analytics_thread():
    run_analytics_pipeline()


def ensure_churn_model_trained():
    if not raw_engine:
        return
    try:
        logger.info("🔍 Checking churn model status...")
        with raw_engine.connect() as conn:
            result = conn.execute(
                text(
                    "SELECT trained_at FROM model_registry WHERE task_type = 'churn' AND is_active = 1 ORDER BY trained_at DESC LIMIT 1"
                )
            ).fetchone()
            needs_training = True
            if result:
                trained_at = (
                    result[0]
                    if isinstance(result[0], datetime)
                    else datetime.fromisoformat(result[0])
                )
                if trained_at.tzinfo is None:
                    trained_at = trained_at.replace(tzinfo=tz_now().tzinfo)
                if (tz_now() - trained_at).total_seconds() / 3600 < 24:
                    needs_training = False

            if needs_training:
                predictor = ChurnPredictor(raw_engine, BASE_DIR)
                predictor.train_and_register()
                logger.info("✅ Churn model training complete!")
    except Exception as e:
        logger.error(f"⚠️ Churn model training failed: {e}")


def initialize_ai():
    global raw_engine, analytics_engine, search_engine, agent_executor, AI_INIT_FAILED

    try:
        # 1. SQL Engine
        raw_engine = create_engine(
            f"sqlite:///{DB_PATH}", connect_args=sqlite_connect_args()
        )

        @event.listens_for(raw_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        # 2. Analytics & Vector Store
        try:
            analytics_engine = AnalyticsEngine(raw_engine, BASE_DIR)
            search_engine = SmartSearchEngine(DB_PATH)
            search_engine.initialize()

            # 🔥 CRITICAL: Inject dependencies into tools
            # This allows tools.py to access DB, Search, and Cache without circular imports
            set_context(raw_engine, search_engine, ANALYTICS_CACHE)

            # Auto-Warmup
            def warm_up_cache():
                logger.info("🔥 Warming up AI Cache...")
                try:
                    analytics_engine.get_dashboard_metrics()
                    logger.info("✅ AI Cache Warm-up Complete.")
                except Exception as e:
                    logger.error(f"Warm-up failed: {e}")

            threading.Thread(target=warm_up_cache, daemon=True).start()

        except Exception as e:
            logger.error(f"Subsystem Init Failed: {e}")

        # 3. Build Agent & Safety Guard (Replaces old manual setup)
        config = load_settings()
        groq_key = config.get("GROQ_API_KEY")

        if groq_key:
            try:
                # Uses the new builder from ai_engine
                agent_executor, safety_guard = build_nexus_agent(raw_engine, groq_key)
                logger.info("✅ AI Agent Online")
            except Exception as e:
                logger.error(f"Agent Build Failed: {e}")
        else:
            logger.warning("No Groq API Key found.")

        # 4. MLOps Checks
        try:
            ensure_churn_model_trained()
        except Exception as e:
            logger.error(f"Churn model check failed: {e}")
        try:
            # Run in background to not block startup (Prophet backtest is slow)
            # Since we use DB now, there is no race condition for a file write.
            asyncio.get_event_loop().run_in_executor(None, run_daily_model_validation)
        except Exception as e:
            logger.error(f"Model validation scheduling failed: {e}")

        AI_INIT_FAILED = False

    except Exception as e:
        AI_INIT_FAILED = True
        logger.critical(f"Global AI Initialization Failed: {e}")


# --- ENDPOINTS ---


class SettingsModel(BaseModel):
    google_api_key: str
    groq_api_key: str


class AskRequest(BaseModel):
    text: str


@app.post("/settings")
async def update_settings(settings: SettingsModel, background_tasks: BackgroundTasks):
    """
    Receive API keys from Electron and store in memory (os.environ) ONLY.
    Keys are NOT written to disk - they come from encrypted DB on startup.
    """
    # Inject into process environment (RAM only)
    if settings.groq_api_key:
        os.environ["GROQ_API_KEY"] = settings.groq_api_key
        logger.info("✅ GROQ API Key received and loaded into memory")

    if settings.google_api_key:
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key
        logger.info("✅ Google API Key received and loaded into memory")

    # Reinitialize AI with new keys
    background_tasks.add_task(initialize_ai)

    return {
        "status": "updated",
        "message": "Keys loaded into memory. AI initializing...",
    }


@app.get("/settings")
async def get_settings():
    return load_settings()


@app.post("/scan_receipt")
async def scan_receipt(file: UploadFile = File(...)):
    """Delegate to AI Engine Vision Module with API Key Injection"""
    logger.info("Scanning Receipt...")

    # 1. Get the content
    content = await file.read()

    # 2. Load the key using main.py's existing logic
    settings = load_settings()
    api_key = settings.get("GROQ_API_KEY")

    # 3. Pass both to the engine
    return await scan_receipt_engine(content, api_key=api_key)


# In python_server/main.py


@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Delegate to AI Engine Voice Module with API Key Injection"""
    content = await file.read()

    # 1. Load the key explicitly
    settings = load_settings()
    api_key = settings.get("GROQ_API_KEY")

    if not api_key:
        logger.error("Attempted transcription but GROQ_API_KEY is missing in config.")

    # 2. Pass it to the engine (offload sync work from event loop)
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, lambda: transcribe_audio_engine(content, file.filename, api_key=api_key)
    )


@app.post("/ask")
async def ask_agent(q: AskRequest):
    """Delegate to Agent Executor & Safety Guard"""
    if not agent_executor or not safety_guard:
        return {"answer": "AI not configured."}
    user_text = q.text.strip()

    greetings = ["hi", "hello", "hey", "hola", "greetings", "test", "ping"]
    if user_text.lower() in greetings:
        return {
            "answer": "Hello! I am NexusRetail OS AI. Ask me about sales, inventory, or customers."
        }

    # 1. Check for Pending Confirmation (YES/NO) via Safety Guard
    confirm_status = safety_guard.check_confirmation(user_text)

    if confirm_status == "CONFIRM":
        action = safety_guard.get_pending()
        safety_guard.clear_pending()
        try:
            res = await agent_executor.ainvoke(action)
            return {"answer": f"✅ Confirmed. {str(res['output'])}"}
        except Exception as e:
            return {"answer": f"❌ Execution failed: {str(e)}"}

    elif confirm_status == "CANCEL":
        safety_guard.clear_pending()
        return {"answer": "🚫 Action cancelled."}

    elif confirm_status == "UNCLEAR" and safety_guard.get_pending():
        return {
            "answer": f"⚠️ Please type 'YES' to confirm action: '{safety_guard.get_pending()}'."
        }

    # 2. New Request - Classify Intent
    intent = safety_guard.classify_intent(user_text)

    if intent == "DANGER":
        safety_guard.set_pending(user_text)
        return {
            "answer": f'⚠️ **Confirmation Required**\n\nCommand: "{user_text}"\n\nReply **YES** to proceed.'
        }

    elif intent == "CHAT":
        try:
            return {
                "answer": safety_guard.llm.invoke(
                    f"User: {user_text}. Reply helpfully."
                ).content
            }
        except Exception as e:
            logger.error(f"Chat fallback failed: {e}")
            return {"answer": "I'm online. Ask me about your data!"}

    else:  # QUERY / SAFE ACTION
        try:
            res = await agent_executor.ainvoke(user_text)
            return {"answer": str(res["output"])}
        except Exception as e:
            return {"answer": f"Processing Error: {str(e)}"}


# --- ANALYTICS & STOCKOUT ENDPOINTS (PRESERVED) ---


@app.get("/analytics/dashboard")
async def get_dashboard_analytics(background_tasks: BackgroundTasks):
    try:
        if not raw_engine:
            return {"status": "error", "message": "DB not initialized"}
        loop = asyncio.get_running_loop()
        analytics = AnalyticsEngine(raw_engine, base_dir=BASE_DIR)
        return await loop.run_in_executor(None, analytics.get_dashboard_metrics)
    except Exception as e:
        logger.error(f"Dashboard Endpoint Failed: {e}")
        return {"status": "error", "message": str(e), "data": {}}


@app.get("/forecast")
async def get_sales_forecast():
    try:
        if not raw_engine:
            return {"history": [], "forecast": [], "trend": "flat"}
        loop = asyncio.get_running_loop()

        def _forecast_sync():
            forecaster = RevenueForecaster(raw_engine, base_dir=BASE_DIR)
            data = forecaster.get_cached_forecast()
            if not data:
                data = forecaster.generate_forecast()
            return data

        return await loop.run_in_executor(None, _forecast_sync)
    except Exception as e:
        logger.error(f"Forecast failed: {e}")
        return {"history": [], "forecast": [], "trend": "flat"}


@app.get("/analytics/churn")
async def churn_analysis(limit: int = 50, risk_level: str = None):
    try:
        if not raw_engine:
            return {"success": False, "error": "Database not initialized"}
        loop = asyncio.get_running_loop()

        def _churn_sync():
            predictor = ChurnPredictor(raw_engine, base_dir=BASE_DIR)
            predictions = predictor.predict_all_customers()
            if risk_level:
                predictions = [
                    p for p in predictions if p["risk_level"] == risk_level.lower()
                ]
            return {
                "success": True,
                "data": predictions[:limit],
                "model_info": predictor.get_model_info(),
            }

        return await loop.run_in_executor(None, _churn_sync)
    except Exception as e:
        logger.error(f"Churn analysis failed: {e}")
        return {"success": False, "error": str(e)}


@app.post("/analytics/cache/refresh")
async def force_refresh_analytics(background_tasks: BackgroundTasks):
    def run_refresh():
        try:
            analytics = AnalyticsEngine(raw_engine, base_dir=BASE_DIR)
            analytics.force_refresh_all()
        except Exception as e:
            logger.error(f"Background refresh failed: {e}")

    background_tasks.add_task(run_refresh)
    return {
        "status": "refresh_started",
        "message": "AI models updating in background...",
    }


# Stockout Endpoints (Preserved)
@app.get("/api/stockout/predictions")
async def get_stockout_predictions(limit: int = 20, risk_level: Optional[str] = None):
    try:
        if not raw_engine:
            return {"success": False, "error": "Database not initialized"}
        loop = asyncio.get_running_loop()

        def _stockout_sync():
            predictor = StockoutPredictor(
                db_engine=raw_engine,
                config={"n_simulations": 10000, "forecast_days": 30},
            )
            predictions = predictor.predict_stockouts(limit=limit)
            if risk_level:
                predictions = [
                    p for p in predictions if p["risk_level"] == risk_level.lower()
                ]
            return {"success": True, "data": predictions, "count": len(predictions)}

        return await loop.run_in_executor(None, _stockout_sync)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/stockout/predictions/critical")
async def get_critical_stockouts():
    try:
        if not raw_engine:
            return {"success": False, "error": "Database not initialized"}
        loop = asyncio.get_running_loop()

        def _critical_sync():
            predictor = StockoutPredictor(
                db_engine=raw_engine,
                config={"n_simulations": 10000, "forecast_days": 30},
            )
            critical = predictor.get_critical_stockouts()
            return {"success": True, "data": critical, "count": len(critical)}

        return await loop.run_in_executor(None, _critical_sync)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/stockout/predictions/{variant_id}")
async def get_single_prediction(variant_id: int):
    try:
        if not raw_engine:
            return {"success": False, "error": "Database not initialized"}
        loop = asyncio.get_running_loop()

        def _single_sync():
            predictor = StockoutPredictor(
                db_engine=raw_engine,
                config={"n_simulations": 10000, "forecast_days": 30},
            )
            predictions = predictor.predict_stockouts(limit=500)
            for pred in predictions:
                if pred["variant_id"] == variant_id:
                    return {"success": True, "data": pred}
            return {
                "success": False,
                "error": f"No prediction available for variant {variant_id}.",
            }

        return await loop.run_in_executor(None, _single_sync)
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/analytics/cache/stats")
async def get_cache_stats():
    try:
        if not raw_engine:
            return {"success": False, "error": "Database not initialized"}
        predictor = StockoutPredictor(
            db_engine=raw_engine, config={"use_cache": True, "n_simulations": 10000}
        )
        return {"success": True, "cache_stats": predictor.cache.get_stats()}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/analytics/cache/clear")
async def clear_cache(variant_id: int = None):
    try:
        if not raw_engine:
            return {"success": False, "error": "Database not initialized"}
        predictor = StockoutPredictor(db_engine=raw_engine, config={"use_cache": True})
        predictor.cache.invalidate(variant_id)
        return {
            "success": True,
            "cleared": "all" if not variant_id else f"var_{variant_id}",
            "message": "Cache cleared.",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/analytics/cache/cleanup")
async def cleanup_expired_cache():
    try:
        if not raw_engine:
            return {"success": False, "error": "Database not initialized"}
        predictor = StockoutPredictor(db_engine=raw_engine, config={"use_cache": True})
        return {
            "success": True,
            "expired_entries_removed": predictor.cache.cleanup_expired(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/health")
async def health_check():
    if AI_INIT_FAILED:
        return {"status": "Init Failed"}
    return {"status": "Active" if safety_guard else "Missing Keys"}


@app.get("/api/model/health")
async def get_model_health():
    """
    Get live model health status from the DB registry.
    Replaces static model_health_report.json.
    """
    try:
        if not raw_engine:
            return {"status": "error", "msg": "Database not initialized"}

        manager = ModelManager(raw_engine)

        # Get latest active models
        churn = manager.get_active_model("churn")
        forecast = manager.get_active_model("forecast")

        report = {
            "timestamp": tz_now().isoformat(),
            "churn_model": (
                churn["metrics"]
                if churn
                else {"status": "pending", "msg": "No active model"}
            ),
            "forecast_model": (
                forecast["metrics"]
                if forecast
                else {"status": "pending", "msg": "Training/Validating..."}
            ),
        }

        # Inject metadata if available
        if churn:
            report["churn_model"].update(
                {
                    "model_id": churn.get("model_id"),
                    "trained_at": churn.get("trained_at"),
                    "version": churn.get("model_version"),
                }
            )

        if forecast:
            report["forecast_model"].update(
                {
                    "model_id": forecast.get("model_id"),
                    "trained_at": forecast.get("trained_at"),
                }
            )

        return report
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "error", "msg": str(e)}


initialize_ai()

if __name__ == "__main__":
    # This prevents Prophet/Torch from spawning infinite copies of the app.
    multiprocessing.freeze_support()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_config=None, use_colors=False)
