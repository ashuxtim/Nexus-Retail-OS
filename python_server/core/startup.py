# FILE: python_server/core/startup.py
# Initialization, settings loading, and background workers.

import os
import re
import json
import threading
import asyncio
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def load_snapshots_from_db():
    """On startup, load previously saved model results from analytics_snapshot table.
    Allows the dashboard to show data instantly without waiting for models to rerun."""
    try:
        import sqlite3

        db_path = state.DB_PATH
        if not db_path or not os.path.exists(db_path):
            logger.warning("DB path not found, skipping snapshot load.")
            return

        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT model_name, data FROM analytics_snapshot"
        ).fetchall()
        conn.close()

        if not rows:
            logger.info("No snapshots found in DB. Fresh start.")
            return

        loaded = {}
        for model_name, data_json in rows:
            try:
                loaded[model_name] = json.loads(data_json)
            except Exception as e:
                logger.warning(f"Failed to parse snapshot for {model_name}: {e}")

        if loaded:
            with state._cache_lock:
                if "churn" in loaded:
                    state.ANALYTICS_CACHE["data"]["churn_risk"] = loaded["churn"].get(
                        "churn_risk", []
                    )
                    state.ANALYTICS_CACHE["data"]["churn_risk_model_info"] = loaded[
                        "churn"
                    ].get("churn_risk_model_info", {})
                if "stockouts" in loaded:
                    state.ANALYTICS_CACHE["data"]["stockouts"] = loaded["stockouts"]
                if "forecast" in loaded:
                    state.ANALYTICS_CACHE["data"]["forecast"] = loaded["forecast"]
                if "market_basket" in loaded:
                    state.ANALYTICS_CACHE["data"]["market_basket"] = loaded[
                        "market_basket"
                    ]

                all_four = all(
                    k in loaded
                    for k in ["churn", "stockouts", "forecast", "market_basket"]
                )
                state.ANALYTICS_CACHE["status"] = "ready" if all_four else "processing"

            logger.info(
                f"⚡ Loaded {len(loaded)}/4 snapshots from DB. Dashboard ready instantly."
            )

    except Exception as e:
        logger.error(f"Failed to load snapshots from DB: {e}")


def _save_snapshot_to_db(model_name: str, data):
    """Persist a single completed model result to analytics_snapshot table."""
    try:
        import sqlite3

        db_path = state.DB_PATH
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            INSERT INTO analytics_snapshot (model_name, data, saved_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(model_name) DO UPDATE SET
                data = excluded.data,
                saved_at = excluded.saved_at
            """,
            (model_name, json.dumps(data, default=str)),
        )
        conn.commit()
        conn.close()
        logger.info(f"💾 Snapshot saved: {model_name}")
    except Exception as e:
        logger.error(f"Failed to save snapshot for {model_name}: {e}")


def run_analytics_pipeline():
    """Runs heavy math in background thread and updates memory/disk."""
    if not state.analytics_engine:
        return

    logger.info("Running background analytics pipeline...")
    with state._cache_lock:
        state.ANALYTICS_CACHE["status"] = "processing"
        state.ANALYTICS_CACHE["data"] = {}

    try:
        state.analytics_engine._check_and_expire_cache(
            state.analytics_engine.churn_ai._get_cache_path(), valid_hours=24
        )
        state.analytics_engine._check_and_expire_cache(
            state.analytics_engine.forecast_ai._get_cache_path(), valid_hours=24
        )
        state.analytics_engine._check_and_expire_cache(
            state.analytics_engine.basket_ai._get_cache_path(), valid_hours=720
        )

        # --- Define each model as an isolated callable ---

        def run_stockout():
            try:
                stockout_raw = state.analytics_engine.stockout_ai.predict_stockouts(limit=20)
                formatted_stockouts = []
                for item in stockout_raw:
                    formatted_stockouts.append({
                        "name": item.get("product_name", f"Item {item['variant_id']}"),
                        "variant_id": item["variant_id"],
                        "stock": item["current_stock"],
                        "days_left": item["metrics"]["days_until_stockout"],
                        "status": item["risk_level"].title(),
                        "metrics": item["metrics"],
                        "recommendation": item["recommendation"],
                    })
                with state._cache_lock:
                    state.ANALYTICS_CACHE["data"]["stockouts"] = formatted_stockouts
                logger.info("✅ Stockout model complete.")
                _save_snapshot_to_db("stockouts", formatted_stockouts)
            except Exception as e:
                logger.error(f"Stockout model failed: {e}")
                with state._cache_lock:
                    state.ANALYTICS_CACHE["data"]["stockouts"] = []

        def run_churn():
            try:
                churn_raw = state.analytics_engine.churn_ai.get_cached_predictions()
                if not churn_raw:
                    churn_raw = state.analytics_engine.churn_ai.predict_all_customers()
                formatted_churn = []
                if churn_raw:
                    for p in churn_raw:
                        formatted_churn.append({
                            "customer_id": p.get("customer_id"),
                            "name": p.get("customer_name", "Unknown"),
                            "risk_score": int(p.get("churn_score", 0) * 100),
                            "days_inactive": p.get("features", {}).get("recency", 0),
                            "velocity": p.get("features", {}).get("velocity", 0),
                            "trend": p.get("risk_label", "Unknown"),
                            "balance": p.get("balance", 0),
                        })
                with state._cache_lock:
                    state.ANALYTICS_CACHE["data"]["churn_risk"] = formatted_churn[:50]
                    state.ANALYTICS_CACHE["data"]["churn_risk_model_info"] = state.analytics_engine.churn_ai.get_model_info()
                logger.info("✅ Churn model complete.")
                _save_snapshot_to_db("churn", {
                    "churn_risk": formatted_churn[:50],
                    "churn_risk_model_info": state.analytics_engine.churn_ai.get_model_info(),
                })
            except Exception as e:
                logger.error(f"Churn model failed: {e}")
                with state._cache_lock:
                    state.ANALYTICS_CACHE["data"]["churn_risk"] = []
                    state.ANALYTICS_CACHE["data"]["churn_risk_model_info"] = {}

        def run_forecast():
            try:
                forecast_data = state.analytics_engine.forecast_ai.get_cached_forecast()
                if not forecast_data:
                    forecast_data = state.analytics_engine.forecast_ai.generate_forecast(days_ahead=30)
                with state._cache_lock:
                    state.ANALYTICS_CACHE["data"]["forecast"] = forecast_data
                logger.info("✅ Forecast model complete.")
                _save_snapshot_to_db("forecast", forecast_data)
            except Exception as e:
                logger.error(f"Forecast model failed: {e}")
                with state._cache_lock:
                    state.ANALYTICS_CACHE["data"]["forecast"] = None

        def run_market_basket():
            try:
                basket_rules = state.analytics_engine.basket_ai.get_cached_rules()
                if basket_rules is None:
                    if state.analytics_engine._basket_lock.acquire(blocking=False):
                        try:
                            basket_rules = state.analytics_engine.basket_ai.generate_rules()
                        finally:
                            state.analytics_engine._basket_lock.release()
                    else:
                        basket_rules = []
                basket_metadata = None
                if basket_rules:
                    basket_metadata = {"algorithm": "FP-Growth", "count": len(basket_rules)}
                with state._cache_lock:
                    state.ANALYTICS_CACHE["data"]["market_basket"] = {
                        "rules": basket_rules or [],
                        "model_metadata": basket_metadata,
                    }
                logger.info("✅ Market Basket model complete.")
                _save_snapshot_to_db("market_basket", {
                    "rules": basket_rules or [],
                    "model_metadata": basket_metadata,
                })
            except Exception as e:
                logger.error(f"Market Basket model failed: {e}")
                with state._cache_lock:
                    state.ANALYTICS_CACHE["data"]["market_basket"] = {
                        "rules": [],
                        "model_metadata": None,
                    }

        # --- Run all 4 models in parallel ---
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(run_stockout): "Stockout",
                executor.submit(run_churn): "Churn",
                executor.submit(run_forecast): "Forecast",
                executor.submit(run_market_basket): "Market Basket",
            }
            for future in as_completed(futures):
                model_name = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"{model_name} thread raised unhandled exception: {e}")

        # FINAL RESOLUTION
        with state._cache_lock:
            state.ANALYTICS_CACHE["status"] = "ready"
        logger.info("✅ Analytics pipeline complete.")

    except Exception as e:
        logger.error(f"Analytics pipeline failed: {e}")
        with state._cache_lock:
            state.ANALYTICS_CACHE["status"] = "error"


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
            load_snapshots_from_db()
            threading.Thread(target=run_analytics_pipeline, daemon=True).start()

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
