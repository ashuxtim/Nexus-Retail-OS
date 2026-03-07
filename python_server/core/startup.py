# FILE: python_server/core/startup.py
# Initialization, settings loading, and background workers.

import os
import re
import json
import threading
import asyncio
from datetime import datetime

from sqlalchemy import text, create_engine, event

from core import state
from core.time_utils import now as tz_now, sqlite_connect_args
from core.key_store import (
    save_keys as save_encrypted_keys,
    load_keys as load_encrypted_keys,
)
from scripts.backend_logging import get_logger

from ai_engine.agent_builder import build_nexus_agent
from ai_engine.tools import set_context
from analytics import AnalyticsEngine
from vector_store import SmartSearchEngine
from models.churn.churn_predictor import ChurnPredictor

# Model Validation Import (optional)
try:
    from eval.model_performance import evaluate_churn_model, evaluate_forecast_model
    from mlops.model_manager import ModelManager

    MODEL_VALIDATION_AVAILABLE = True
except ImportError:
    MODEL_VALIDATION_AVAILABLE = False

logger = get_logger("NexusAI_Backend")


# --- HELPER ---


def clean_number(val):
    if isinstance(val, (int, float)):
        return float(val)
    clean = re.sub(r"[^0-9.]", "", str(val))
    try:
        return float(clean)
    except:
        return 1.0


# --- SETTINGS ---


def load_settings():
    """
    Load settings with priority:
      1. Environment variables (set by POST /settings or Electron injection)
      2. Encrypted key file (persists across restarts/reloads)
      3. config.json (non-sensitive settings only)
    """
    config = {}

    # 1. Check environment variables FIRST (injected by Electron or POST /settings)
    if "GROQ_API_KEY" in os.environ:
        config["GROQ_API_KEY"] = os.environ["GROQ_API_KEY"]
    if "GOOGLE_API_KEY" in os.environ:
        config["GOOGLE_API_KEY"] = os.environ["GOOGLE_API_KEY"]

    # 2. Fallback: Load from encrypted key file (survives process restarts)
    if "GROQ_API_KEY" not in config or "GOOGLE_API_KEY" not in config:
        stored_keys = load_encrypted_keys(state.BASE_DIR)
        for key_name in ["GROQ_API_KEY", "GOOGLE_API_KEY"]:
            if key_name not in config and key_name in stored_keys:
                config[key_name] = stored_keys[key_name]
                # Also inject into env so subsequent calls don't need disk I/O
                os.environ[key_name] = stored_keys[key_name]

    # 3. Load non-sensitive settings from config.json (if exists)
    if os.path.exists(state.CONFIG_PATH):
        try:
            with open(state.CONFIG_PATH, "r") as f:
                disk_config = json.load(f)
                # Merge non-sensitive settings
                for key, value in disk_config.items():
                    if key not in ["GROQ_API_KEY", "GOOGLE_API_KEY"]:
                        config[key] = value
        except:
            pass

    return config


# --- BACKGROUND WORKERS ---


def run_daily_model_validation():
    if not MODEL_VALIDATION_AVAILABLE:
        return
    try:
        logger.info("📈 Running Daily Forecast Validation...")
        evaluate_forecast_model()
        logger.info("✅ Daily Forecast Validation Complete")
    except Exception as e:
        logger.error(f"Daily Forecast Validation Failed: {e}")


def run_analytics_pipeline():
    """Runs heavy math in background thread and updates memory/disk."""
    if not state.analytics_engine:
        return

    logger.info("Running background analytics pipeline...")
    with state._cache_lock:
        state.ANALYTICS_CACHE["status"] = "processing"

    result = state.analytics_engine.compute_and_cache_dashboard()

    with state._cache_lock:
        if result:
            for key, value in result.items():
                state.ANALYTICS_CACHE[key] = value
            state.ANALYTICS_CACHE["status"] = "ready"
        else:
            state.ANALYTICS_CACHE["status"] = "error"


def run_analytics_thread():
    run_analytics_pipeline()


def ensure_churn_model_trained():
    if not state.raw_engine:
        return
    try:
        logger.info("🔍 Checking churn model status...")
        with state.raw_engine.connect() as conn:
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
                predictor = ChurnPredictor(state.raw_engine, state.BASE_DIR)
                predictor.train_and_register()
                logger.info("✅ Churn model training complete!")
    except Exception as e:
        logger.error(f"⚠️ Churn model training failed: {e}")


# --- MAIN INITIALIZATION ---


def initialize_ai():
    try:
        # 1. SQL Engine
        state.raw_engine = create_engine(
            f"sqlite:///{state.DB_PATH}", connect_args=sqlite_connect_args()
        )

        @event.listens_for(state.raw_engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        # 1b. Ensure DB indexes for fast name lookups
        from core.indexes import ensure_indexes

        ensure_indexes(state.raw_engine)

        # 2. Analytics & Vector Store
        try:
            state.analytics_engine = AnalyticsEngine(state.raw_engine, state.BASE_DIR)
            state.search_engine = SmartSearchEngine(state.DB_PATH)
            state.search_engine.initialize()

            # Inject dependencies into tools
            set_context(state.raw_engine, state.search_engine, state.ANALYTICS_CACHE)

            # Auto-Warmup
            def warm_up_cache():
                logger.info("🔥 Warming up AI Cache...")
                try:
                    state.analytics_engine.get_dashboard_metrics()
                    logger.info("✅ AI Cache Warm-up Complete.")
                except Exception as e:
                    logger.error(f"Warm-up failed: {e}")

            threading.Thread(target=warm_up_cache, daemon=True).start()

        except Exception as e:
            logger.error(f"Subsystem Init Failed: {e}")

        # 3. Build Agent & Safety Guard
        config = load_settings()
        groq_key = config.get("GROQ_API_KEY")

        if groq_key:
            try:
                from ai_engine.safety import SafetyGuard

                agent, router_llm = build_nexus_agent(state.raw_engine, groq_key)
                state.agent_executor = agent
                state.safety_guard = SafetyGuard(router_llm) if router_llm else None
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
            asyncio.get_event_loop().run_in_executor(None, run_daily_model_validation)
        except Exception as e:
            logger.error(f"Model validation scheduling failed: {e}")

        state.AI_INIT_FAILED = False

    except Exception as e:
        state.AI_INIT_FAILED = True
        logger.critical(f"Global AI Initialization Failed: {e}")
