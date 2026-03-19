import os
import shutil
import logging
from datetime import datetime, timedelta
from core.time_utils import now as tz_now
from typing import Dict, Any
import threading

# --- ORM & DB Imports ---
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import declarative_base, relationship

# --- Import the 4 Specialized Brains ---
from models.stockout.predictor import StockoutPredictor
from models.churn.churn_predictor import ChurnPredictor
from models.market_basket.analyzer import MarketBasketAnalyzer
from models.forecast.forecaster import RevenueForecaster

from scripts.backend_logging import get_logger

logger = get_logger("NexusAI_Analytics")

# --- ORM MODELS ---
Base = declarative_base()


class Product(Base):
    __tablename__ = "product"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    variants = relationship("ProductVariant", back_populates="product")


class ProductVariant(Base):
    __tablename__ = "product_variant"
    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("product.id"))
    name = Column(String)
    current_stock = Column(Float)
    product = relationship("Product", back_populates="variants")


class AnalyticsEngine:
    """
    The 'Stitching Layer'.
    Coordinates specialized modules and manages Time-To-Live (TTL) logic.
    """

    def __init__(self, engine, base_dir=None):
        self.engine = engine

        # Initialize the 4 Brains
        self.stockout_ai = StockoutPredictor(engine, base_dir=base_dir)
        self.churn_ai = ChurnPredictor(engine, base_dir=base_dir)
        self.basket_ai = MarketBasketAnalyzer(engine, base_dir=base_dir)
        self.forecast_ai = RevenueForecaster(engine, base_dir=base_dir)

        # Threading lock for Market Basket Analyzer
        self._basket_lock = threading.Lock()

        print("🔗 AnalyticsEngine: Coordinator initialized.")

    def _check_and_expire_cache(self, cache_path: str, valid_hours: int):
        """
        Smart Timer: Checks if a file is older than 'valid_hours'.
        If it is, deletes it so the AI knows to regenerate it.
        """
        if not cache_path or not os.path.exists(cache_path):
            return

        try:
            # Get file modification time
            mtime = os.path.getmtime(cache_path)
            file_time = datetime.fromtimestamp(mtime, tz=tz_now().tzinfo)
            age = tz_now() - file_time

            # If older than limit, NUKE IT
            if age > timedelta(hours=valid_hours):
                os.remove(cache_path)
                print(
                    f"   ⏰ Expired Cache ({age.total_seconds()/3600:.1f} hrs old): {os.path.basename(cache_path)}"
                )
        except Exception as e:
            print(f"   ⚠️ Error checking cache expiry: {e}")

    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """
        Main endpoint.
        1. Checks expiration timers (4h, 24h, 30days).
        2. Regenerates data if expired or missing.
        3. Returns transformed JSON.
        """
        response = {
            "version": "3.1",
            "timestamp": tz_now().isoformat(),
            "status": "success",
            "data": {},
        }

        try:
            print("📊 Dashboard Access: Checking Freshness...")

            # --- STEP 1: APPLY TIME RULES (The "Automatic Schedule") ---

            # Rule 1: Stockout is fresh for 4 HOURS
            # (Note: StockoutPredictor has internal logic, but we can enforce it here too if needed)

            # Rule 2: Churn & Forecast are fresh for 24 HOURS
            self._check_and_expire_cache(
                self.churn_ai._get_cache_path(), valid_hours=24
            )
            self._check_and_expire_cache(
                self.forecast_ai._get_cache_path(), valid_hours=24
            )

            # Rule 3: Market Basket is fresh for 720 HOURS (30 Days)
            self._check_and_expire_cache(
                self.basket_ai._get_cache_path(), valid_hours=720
            )

            # --- STEP 2: FETCH OR GENERATE DATA ---

            # A. STOCKOUTS
            # Note: StockoutPredictor manages its own cache internally (default 4h),
            # so we just call it.
            stockout_raw = self.stockout_ai.predict_stockouts(limit=20)

            formatted_stockouts = []
            for item in stockout_raw:
                formatted_stockouts.append(
                    {
                        "name": item.get("product_name", f"Item {item['variant_id']}"),
                        "variant_id": item["variant_id"],
                        "stock": item["current_stock"],
                        "days_left": item["metrics"]["days_until_stockout"],
                        "status": item["risk_level"].title(),
                        "metrics": item["metrics"],
                        "recommendation": item["recommendation"],
                    }
                )

            # B. CHURN RISK
            churn_raw = self.churn_ai.get_cached_predictions()
            if not churn_raw:
                print(
                    "   ⏳ Churn cache miss (Expired or Missing). Running inference..."
                )
                churn_raw = self.churn_ai.predict_all_customers()

            formatted_churn = []
            if churn_raw:
                for p in churn_raw:
                    formatted_churn.append(
                        {
                            "customer_id": p.get("customer_id"),
                            "name": p.get("customer_name", "Unknown"),
                            "risk_score": int(p.get("churn_score", 0) * 100),
                            "days_inactive": p.get("features", {}).get("recency", 0),
                            "velocity": p.get("features", {}).get("velocity", 0),
                            "trend": p.get("risk_label", "Unknown"),
                            "balance": p.get("balance", 0),
                        }
                    )

            # C. REVENUE FORECAST
            forecast_data = self.forecast_ai.get_cached_forecast()
            if not forecast_data:
                print("   ⏳ Forecast cache miss. Generating new forecast...")
                forecast_data = self.forecast_ai.generate_forecast(days_ahead=30)

            # D. MARKET BASKET (The Slow One)
            basket_rules = self.basket_ai.get_cached_rules()
            basket_metadata = None

            if basket_rules is None:
                if self._basket_lock.acquire(blocking=False):
                    try:
                        print("   ⏳ Market Basket cache miss. Analyzing patterns...")
                        basket_rules = self.basket_ai.generate_rules()
                    finally:
                        self._basket_lock.release()
                else:
                    print("   ⏳ Market Basket generation already in progress. Skipping...")
                    basket_rules = [] # Return empty while waiting for the background thread

            if basket_rules:
                basket_metadata = {"algorithm": "FP-Growth", "count": len(basket_rules)}

            # --- STEP 3: ASSEMBLE ---
            response["data"] = {
                "stockouts": formatted_stockouts,
                "churn_risk": formatted_churn[:50],
                "forecast": forecast_data,
                "market_basket": {
                    "rules": basket_rules or [],
                    "model_metadata": basket_metadata,
                },
                "churn_risk_model_info": self.churn_ai.get_model_info(),
            }

        except Exception as e:
            logger.error(f"Error generating dashboard metrics: {e}")
            import traceback

            traceback.print_exc()
            response["status"] = "error"
            response["error"] = str(e)

        return response

    def force_refresh_all(self):
        """
        Admin endpoint to force re-calculation.
        Strategy: NUKE the entire 'ml_store' folder and rebuild from scratch.
        """
        print("\n" + "=" * 50)
        print("☢️  FORCE REFRESH: NUKING ML_STORE")
        print("=" * 50)

        try:
            # --- STEP 1: DEFINE THE PATH ---
            # Using Stockout AI's base_dir to locate the central store
            ml_store_path = os.path.join(self.stockout_ai.base_dir, "ml_store")
            print(f"🎯 Target Directory: {ml_store_path}")

            # --- STEP 2: THE NUCLEAR OPTION (Delete Everything Except Chroma) ---
            if os.path.exists(ml_store_path):
                try:
                    for item in os.listdir(ml_store_path):
                        item_path = os.path.join(ml_store_path, item)
                        if item == "chroma":
                            print("   ⏭️  Skipping ChromaDB directory (vector store preserved).")
                            continue
                        if os.path.isdir(item_path):
                            shutil.rmtree(item_path)
                        else:
                            os.remove(item_path)
                    print(f"   🗑️  SUCCESS: Cleared 'ml_store' folder (preserved chroma).")
                except Exception as e:
                    print(f"   ❌ Error clearing folder: {e}")
            else:
                print(f"   ⚠️  'ml_store' folder not found (Clean start).")

            # --- STEP 3: FORECAST/CACHE FOLDERS (Will recreate dynamically) ---
            os.makedirs(ml_store_path, exist_ok=True)
            print(f"   ✨ Ensured 'ml_store' directory exists.")

            # Invalidate in-memory Python objects
            if hasattr(self.stockout_ai, "cache") and hasattr(
                self.stockout_ai.cache, "invalidate"
            ):
                self.stockout_ai.cache.invalidate()

            print("\n" + "-" * 30)
            print("   ✅ PURGE COMPLETE. STARTING CALCULATIONS...")
            print("-" * 30)

            # --- STEP 4: THE RE-CALCULATION ---

            print("🚀 1/4: Running Stockout Prediction (Monte Carlo)...")
            self.stockout_ai.predict_stockouts(limit=20)
            print("   ✅ Stockout Complete.")

            print("🚀 2/4: Running Churn Prediction (XGBoost)...")
            self.churn_ai.predict_all_customers()
            print("   ✅ Churn Complete.")

            print("🚀 3/4: Running Revenue Forecast (Prophet)...")
            self.forecast_ai.generate_forecast()
            print("   ✅ Forecast Complete.")

            print("🚀 4/4: Running Market Basket (FP-Growth)...")
            self.basket_ai.generate_rules()
            print("   ✅ Market Basket Complete.")

            print("\n" + "=" * 50)
            print("✅ FORCE REFRESH COMPLETE")
            print("=" * 50 + "\n")

            return {
                "status": "success",
                "message": "Refreshed all AI models (Full Reset)",
            }

        except Exception as e:
            print(f"❌ Force Refresh Failed: {e}")
            import traceback

            traceback.print_exc()
            return {"status": "error", "error": str(e)}
