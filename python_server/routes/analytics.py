# FILE: python_server/routes/analytics.py
# Analytics, Forecast, Stockout, Cache, and Health endpoints.

import os
import asyncio
from typing import Optional
from fastapi import APIRouter

from core import state
from core.time_utils import now as tz_now
from core.startup import run_analytics_pipeline
from scripts.backend_logging import get_logger
from models.stockout.predictor import StockoutPredictor
from models.churn.churn_predictor import ChurnPredictor
from models.forecast.forecaster import RevenueForecaster

# MLOps (optional)
try:
    from mlops.model_manager import ModelManager

    MODEL_MANAGER_AVAILABLE = True
except ImportError:
    MODEL_MANAGER_AVAILABLE = False

router = APIRouter()
logger = get_logger("NexusAI_Backend")


# --- ANALYTICS & STOCKOUT ENDPOINTS ---


@router.get("/analytics/dashboard")
async def get_dashboard_analytics():
    if not state.raw_engine:
        return {"status": "error", "message": "DB not initialized"}
    with state._cache_lock:
        return dict(state.ANALYTICS_CACHE)


@router.get("/forecast")
async def get_sales_forecast():
    try:
        if not state.raw_engine:
            return {"history": [], "forecast": [], "trend": "flat"}
        loop = asyncio.get_running_loop()

        def _forecast_sync():
            forecaster = RevenueForecaster(state.raw_engine, base_dir=state.BASE_DIR)
            data = forecaster.get_cached_forecast()
            if not data:
                data = forecaster.generate_forecast()
            return data

        return await loop.run_in_executor(None, _forecast_sync)
    except Exception as e:
        logger.error(f"Forecast failed: {e}")
        return {"history": [], "forecast": [], "trend": "flat"}


@router.get("/analytics/churn")
async def churn_analysis(limit: int = 50, risk_level: str = None):
    try:
        if not state.raw_engine:
            return {"success": False, "error": "Database not initialized"}
        loop = asyncio.get_running_loop()

        def _churn_sync():
            predictor = ChurnPredictor(state.raw_engine, base_dir=state.BASE_DIR)
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


@router.post("/analytics/cache/refresh")
async def force_refresh_analytics():
    """Full clean slate refresh — clears all caches and reruns all 4 models."""
    try:
        import sqlite3

        # Step 1 — Reset in-memory cache immediately so frontend sees processing state
        with state._cache_lock:
            state.ANALYTICS_CACHE["status"] = "processing"
            state.ANALYTICS_CACHE["data"] = {}

        # Step 2 — Clear analytics_snapshot table so stale data is not served on next startup
        try:
            conn = sqlite3.connect(state.DB_PATH)
            conn.execute("DELETE FROM analytics_snapshot")
            conn.commit()
            conn.close()
            logger.info("🗑️ analytics_snapshot table cleared for force refresh.")
        except Exception as e:
            logger.error(f"Failed to clear analytics_snapshot: {e}")

        # Step 3 — Delete all ml_store files except chroma (same as force_refresh_all)
        try:
            import shutil
            ml_store_path = os.path.join(state.BASE_DIR, "ml_store")
            if os.path.exists(ml_store_path):
                for item in os.listdir(ml_store_path):
                    item_path = os.path.join(ml_store_path, item)
                    if item == "chroma":
                        continue
                    if os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    else:
                        os.remove(item_path)
                os.makedirs(ml_store_path, exist_ok=True)
                logger.info("🗑️ ml_store cleared for force refresh.")
        except Exception as e:
            logger.error(f"Failed to clear ml_store: {e}")

        # Step 4 — Start fresh pipeline in background thread
        import threading
        threading.Thread(target=run_analytics_pipeline, daemon=True).start()
        logger.info("🚀 Force refresh pipeline started in background.")

        return {
            "status": "refresh_started",
            "message": "Full reset initiated. All 4 models recomputing in background."
        }

    except Exception as e:
        logger.error(f"Force refresh failed: {e}")
        return {"status": "error", "message": str(e)}


# --- STOCKOUT ENDPOINTS ---


@router.get("/api/stockout/predictions")
async def get_stockout_predictions(limit: int = 20, risk_level: Optional[str] = None):
    try:
        if not state.raw_engine:
            return {"success": False, "error": "Database not initialized"}
        loop = asyncio.get_running_loop()

        def _stockout_sync():
            predictor = StockoutPredictor(
                db_engine=state.raw_engine,
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


@router.get("/api/stockout/predictions/critical")
async def get_critical_stockouts():
    try:
        if not state.raw_engine:
            return {"success": False, "error": "Database not initialized"}
        loop = asyncio.get_running_loop()

        def _critical_sync():
            predictor = StockoutPredictor(
                db_engine=state.raw_engine,
                config={"n_simulations": 10000, "forecast_days": 30},
            )
            critical = predictor.get_critical_stockouts()
            return {"success": True, "data": critical, "count": len(critical)}

        return await loop.run_in_executor(None, _critical_sync)
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/api/stockout/predictions/{variant_id}")
async def get_single_prediction(variant_id: int):
    try:
        if not state.raw_engine:
            return {"success": False, "error": "Database not initialized"}
        loop = asyncio.get_running_loop()

        def _single_sync():
            predictor = StockoutPredictor(
                db_engine=state.raw_engine,
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


# --- CACHE ENDPOINTS ---


@router.get("/analytics/cache/stats")
async def get_cache_stats():
    try:
        if not state.raw_engine:
            return {"success": False, "error": "Database not initialized"}
        predictor = StockoutPredictor(
            db_engine=state.raw_engine,
            config={"use_cache": True, "n_simulations": 10000},
        )
        return {"success": True, "cache_stats": predictor.cache.get_stats()}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/analytics/cache/clear")
async def clear_cache(variant_id: int = None):
    try:
        if not state.raw_engine:
            return {"success": False, "error": "Database not initialized"}
        predictor = StockoutPredictor(
            db_engine=state.raw_engine, config={"use_cache": True}
        )
        predictor.cache.invalidate(variant_id)
        return {
            "success": True,
            "cleared": "all" if not variant_id else f"var_{variant_id}",
            "message": "Cache cleared.",
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/analytics/cache/cleanup")
async def cleanup_expired_cache():
    try:
        if not state.raw_engine:
            return {"success": False, "error": "Database not initialized"}
        predictor = StockoutPredictor(
            db_engine=state.raw_engine, config={"use_cache": True}
        )
        return {
            "success": True,
            "expired_entries_removed": predictor.cache.cleanup_expired(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# --- HEALTH ENDPOINTS ---


@router.get("/health")
async def health_check():
    from core import state
    search_status = "offline"
    if hasattr(state, 'search_engine') and state.search_engine:
        if state.search_engine.is_loading:
            search_status = "warming_up"
        elif state.search_engine.load_error:
            search_status = "error"
        elif not state.search_engine.is_ready:
            search_status = "offline"
            
    return {
        "status": "Active" if state.safety_guard else "Missing Keys",
        "search_engine": search_status,
        "ai_failed": state.AI_INIT_FAILED
    }


@router.get("/api/model/health")
async def get_model_health():
    """
    Get live model health status from the DB registry.
    Replaces static model_health_report.json.
    """
    try:
        if not state.raw_engine:
            return {"status": "error", "msg": "Database not initialized"}

        if not MODEL_MANAGER_AVAILABLE:
            return {"status": "error", "msg": "ModelManager not available"}

        manager = ModelManager(state.raw_engine)

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
