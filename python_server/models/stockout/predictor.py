import logging
import os
import json
import numpy as np
from datetime import datetime, timedelta
from core.time_utils import now as tz_now
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from sqlalchemy import text
import pandas as pd

from models.stockout.monte_carlo_simulator import MonteCarloSimulator
from features.inventory.demand_analyzer import DemandAnalyzer

logger = logging.getLogger(__name__)


class StockoutPredictor:
    """
    High-level orchestrator for stockout prediction using Monte Carlo.

    For each product:
    1. Analyze historical demand
    2. Run Monte Carlo simulation
    3. Classify risk level
    4. Generate recommendations
    """

    def __init__(self, db_engine, config: Dict = None, base_dir: str = None):
        """
        Initialize StockoutPredictor with caching support.

        Args:
            db_engine: SQLAlchemy database engine
            config: Configuration dict with keys:
                - n_simulations: Monte Carlo iterations (default 10000)
                - forecast_days: Prediction horizon (default 30)
                - use_cache: Enable file-based caching (default True)
                - cache_ttl_hours: Cache time-to-live in hours (default 4)
                - high_risk_threshold: Threshold for critical risk (default 0.7)
                - medium_risk_threshold: Threshold for warning risk (default 0.3)
            base_dir: Optional override for data directory
        """
        self.engine = db_engine
        self.config = config or {}

        self.analyzer = DemandAnalyzer(db_engine)
        self.simulator = MonteCarloSimulator(
            n_simulations=self.config.get("n_simulations", 1000),
            forecast_days=self.config.get("forecast_days", 30),
        )

        # --- SAFE CACHE SETUP (Replaces StockoutCache) ---
        # 1. Resolve Base Directory
        if base_dir:
            self.base_dir = base_dir
        else:
            import sys

            # Fallback to standard AppData location if not provided
            if "NEXUS_USER_DATA" in os.environ:
                self.base_dir = os.environ["NEXUS_USER_DATA"]
            elif sys.platform == "win32":
                self.base_dir = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
            else:
                self.base_dir = os.path.join(
                    os.path.expanduser("~"), ".config", "NexusRetailOS"
                )

        # 2. ✅ CRITICAL FIX: Use 'ml_store' to prevent Electron deletion
        self.cache_dir = Path(self.base_dir) / "ml_store" / "stockout_simulations"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 3. Cache Settings
        self.use_cache = self.config.get("use_cache", True)
        # Default to 4 hours as requested for freshness check
        self.ttl = timedelta(hours=self.config.get("cache_ttl_hours", 4))

        # Risk thresholds
        self.thresholds = {
            "high_risk": self.config.get("high_risk_threshold", 0.7),  # 70%+ = high
            "medium_risk": self.config.get(
                "medium_risk_threshold", 0.3
            ),  # 30-70% = medium
        }

    def _get_cache_path(self, variant_id: int) -> Path:
        return self.cache_dir / f"sim_v{variant_id}.json"

    def _load_from_cache(self, variant_id: int, current_stock: float) -> Optional[Dict]:
        """Try to load valid, non-expired cache for this stock level."""
        if not self.use_cache:
            return None

        path = self._get_cache_path(variant_id)
        if not path.exists():
            return None

        try:
            with open(path, "r") as f:
                data = json.load(f)

            # Validate TTL and Stock Consistency
            cached_at = datetime.fromisoformat(data["metadata"]["cached_at"])
            # Handle old caches that stored naive timestamps
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=tz_now().tzinfo)
            if tz_now() - cached_at > self.ttl:
                return None
            if data["metadata"]["cached_stock"] != current_stock:
                return None

            data["metadata"]["source"] = "cache"
            return data
        except Exception:
            return None

    def _save_to_cache(self, variant_id: int, current_stock: float, result: Dict):
        """Save simulation result to safe ml_store."""
        if not self.use_cache:
            return
        try:
            result["metadata"]["cached_at"] = tz_now().isoformat()
            result["metadata"]["cached_stock"] = current_stock
            with open(self._get_cache_path(variant_id), "w") as f:
                json.dump(result, f, indent=2)
        except Exception as e:
            logger.error(f"Cache write error: {e}")

    def prune_cache(self):
        """Public method to clean old files."""
        if not self.cache_dir.exists():
            return 0
        count = 0
        now = tz_now()
        for f in self.cache_dir.glob("sim_v*.json"):
            try:
                if (
                    now - datetime.fromtimestamp(f.stat().st_mtime, tz=now.tzinfo)
                    > self.ttl
                ):
                    f.unlink()
                    count += 1
            except:
                pass
        return count

    def predict_stockouts(self, limit: int = 50) -> List[Dict]:
        """
        Predict stockout risk for all active products.

        Returns:
            List of dicts with stockout predictions, sorted by risk (highest first)
        """
        logger.info(f"Starting stockout prediction for up to {limit} products")

        # Get all products with stock - FIXED QUERY for your schema
        query = text("""
            SELECT 
                v.id as variant_id,
                p.name as product_name,
                v.name as variant_name,
                v.current_stock as quantity_in_stock,
                p.category as category
            FROM product_variant v
            JOIN product p ON v.product_id = p.id
            WHERE v.current_stock >= 0
            ORDER BY v.current_stock ASC
            LIMIT 200
        """)

        with self.engine.connect() as conn:
            products = pd.read_sql(query, conn)

        logger.info(f"Found {len(products)} products to analyze")

        results = []
        cache_hits = 0
        cache_misses = 0
        total = len(products)
        progress_interval = max(1, total // 4)  # Log every 25%

        logger.info(
            f"Stockout simulation started: {total} products, {self.config.get('n_simulations', 10000)} iterations each"
        )

        for idx, (_, product) in enumerate(products.iterrows(), 1):
            try:
                # Log progress at 25% intervals
                if idx == 1 or idx % progress_interval == 0 or idx == total:
                    logger.info(f"Stockout progress: {idx}/{total} products analyzed")

                # ✅ UPDATE: Call the new singular method (which handles Safe Caching & Metrics)
                prediction = self.predict_stockout(
                    variant_id=product["variant_id"],
                    current_stock=product["quantity_in_stock"],
                )

                # ✅ ENRICH: Add names (predict_stockout only knows IDs)
                prediction["product_name"] = product["product_name"]
                prediction["variant_name"] = product["variant_name"]
                prediction["category"] = product["category"]

                # Check cache status using new metadata format
                is_cached = prediction.get("metadata", {}).get("source") == "cache"

                if is_cached:
                    cache_hits += 1
                else:
                    cache_misses += 1

                # Only include products with risk > 10% (filter noise)
                if prediction["stockout_probability"] > 0.1:
                    results.append(prediction)

            except Exception as e:
                logger.error(
                    f"Failed to predict stockout for variant {product['variant_id']}: {e}"
                )
                continue

        # Sort by risk (highest first)
        results.sort(key=lambda x: x["stockout_probability"], reverse=True)

        logger.info(
            f"Stockout simulation complete. "
            f"Cache hits: {cache_hits}, misses: {cache_misses}, "
            f"high-risk products: {len(results)}"
        )

        return results[:limit]

    def predict_stockout(self, variant_id: int, current_stock: float) -> Dict:
        """
        Predict stockout for a single product.
        Renamed from _predict_single_product to match the new loop call.
        """
        # ✅ FIX: Use new internal safe cache
        if self.use_cache:
            cached_prediction = self._load_from_cache(variant_id, current_stock)
            if cached_prediction is not None:
                cached_prediction["cache_hit"] = True
                return cached_prediction

        # --- LOGIC (Monte Carlo) ---
        # Note: We need to fetch product name/category inside here if not passed,
        # but for the core logic, ID and Stock are enough.
        # The calling loop (predict_stockouts) attaches the names later.

        demand_stats = self.analyzer.analyze_product_demand(
            variant_id, lookback_days=90
        )
        lead_time = self.analyzer.estimate_lead_time(variant_id)

        simulation_results = self.simulator.simulate_stockout_probability(
            current_stock=current_stock,
            demand_stats=demand_stats,
            lead_time_range=lead_time,
        )

        # Risk Classification
        stockout_prob = simulation_results["stockout_probability"]
        if stockout_prob >= self.thresholds["high_risk"]:
            risk_level = "critical"
        elif stockout_prob >= self.thresholds["medium_risk"]:
            risk_level = "warning"
        else:
            risk_level = "low"

        # Reorder Calculation
        avg_lead = (lead_time[0] + lead_time[1]) / 2
        calculated_reorder_point = int(
            (demand_stats["daily_demand_mean"] * avg_lead)
            + simulation_results["recommended_safety_stock"]
        )

        eoq = self.simulator.calculate_optimal_order_quantity(demand_stats, lead_time)

        # Build Result
        result = {
            "variant_id": int(variant_id),
            # Names are filled by the loop, placeholders here
            "product_name": "",
            "variant_name": "",
            "category": "",
            "current_stock": int(current_stock),
            "reorder_point": calculated_reorder_point,
            # Legacy fields
            "avg_daily_demand": round(demand_stats["daily_demand_mean"], 2),
            "demand_volatility": round(demand_stats["coefficient_of_variation"], 2),
            "stockout_probability": round(stockout_prob, 3),
            "expected_days_to_stockout": simulation_results[
                "expected_days_to_stockout"
            ],
            "risk_level": risk_level,
            # ✅ METRICS
            "metrics": {
                "burn_rate": round(demand_stats["daily_demand_mean"], 2),
                "volatility": round(demand_stats["coefficient_of_variation"] * 100, 1),
                "days_until_stockout": simulation_results["expected_days_to_stockout"],
                "safety_stock": simulation_results["recommended_safety_stock"],
                "reorder_point": calculated_reorder_point,
                "eoq": eoq,
            },
            "confidence_intervals": {
                "50%": round(simulation_results["confidence_50"], 2),
                "75%": round(simulation_results["confidence_75"], 2),
                "90%": round(simulation_results["confidence_90"], 2),
            },
            "recommendation": {
                "action": (
                    "Buy Now"
                    if current_stock <= calculated_reorder_point
                    else "Monitor"
                ),
                "quantity": eoq,
            },
            "recommended_safety_stock": simulation_results["recommended_safety_stock"],
            "suggested_order_quantity": eoq,
            "lead_time_range": {"min": lead_time[0], "max": lead_time[1]},
            "metadata": {
                "simulation_count": simulation_results["simulation_count"],
                "source": "live_compute",
            },
            "cache_hit": False,
        }

        # Save to safe cache
        if self.use_cache:
            self._save_to_cache(variant_id, current_stock, result)

        return result
