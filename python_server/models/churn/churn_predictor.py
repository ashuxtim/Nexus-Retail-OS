import os
import sys
import pathlib
import json
import logging
import threading
import numpy as np
from datetime import datetime
from core.time_utils import now as tz_now
from typing import Dict, List, Optional
import pandas as pd
from sqlalchemy import text
from features.churn_features import ChurnFeatureEngineer
from mlops.model_manager import ModelManager
from models.churn.xgboost_model import XGBoostChurnModel
from models.churn.heuristic_model import HeuristicChurnModel

_logger = logging.getLogger("NexusAI_Backend")

_global_retrain_lock = threading.Lock()
_global_retrain_in_progress = False

class ChurnPredictor:
    """
    High-level orchestrator for churn prediction.

    Handles:
    - Automatic model loading from registry
    - Feature preparation
    - Prediction with fallback logic
    - Result formatting for frontend
    - Caching of daily predictions to 'ml_store'
    """

    def __init__(self, engine, base_dir=None):
        """
        Initialize ChurnPredictor with consistent paths.

        Args:
            engine: SQLAlchemy engine
            base_dir: Base directory (should be AppData path from main.py)
        """
        self.engine = engine

        # Use provided base_dir (AppData), NOT project directory
        if base_dir:
            self.base_dir = base_dir
        else:
            # Fallback: use AppData location or Linux config
            if sys.platform == "win32":
                self.base_dir = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
            else:
                self.base_dir = os.path.join(
                    os.path.expanduser("~"), ".config", "NexusRetailOS"
                )

        # ✅ FIX: Move to 'ml_store' to prevent Electron wiping the folder
        self.model_dir = os.path.join(self.base_dir, "ml_store", "models")

        # ✅ NEW: Path for caching JSON results (Speed up Dashboard)
        self.cache_dir = os.path.join(self.base_dir, "ml_store", "churn")

        # Ensure directories exist
        os.makedirs(self.model_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)

        print(f"🔧 ChurnPredictor initialized")
        print(f"   Base Dir: {self.base_dir}")
        print(f"   Model Dir: {self.model_dir}")
        print(f"   Cache Dir: {self.cache_dir}")

        # Initialize components
        self.feature_engineer = ChurnFeatureEngineer(engine)
        self.model_manager = ModelManager(engine)
        self.model_instance = None
        self.active_model = None


    # --- CACHING HELPERS (NEW) ---
    def _get_cache_path(self) -> str:
        """Get path for the daily churn risk report."""
        date_str = tz_now().strftime("%Y-%m-%d")
        return os.path.join(self.cache_dir, f"churn_risk_{date_str}.json")

    def get_cached_predictions(self) -> Optional[List[Dict]]:
        """Retrieve today's cached predictions if available."""
        cache_path = self._get_cache_path()
        if os.path.exists(cache_path):
            try:
                with open(cache_path, "r") as f:
                    data = json.load(f)
                print(
                    f"✅ Loaded {len(data.get('data', []))} cached churn predictions."
                )
                return data.get("data", [])
            except Exception as e:
                print(f"⚠️ Failed to load churn cache: {e}")
        return None

    def save_predictions_to_cache(self, predictions: List[Dict]):
        """Save predictions to JSON for fast dashboard loading."""
        cache_path = self._get_cache_path()
        try:
            payload = {
                "timestamp": tz_now().isoformat(),
                "count": len(predictions),
                "data": predictions,
            }
            with open(cache_path, "w") as f:
                json.dump(payload, f, indent=2)
            print(f"✅ Saved {len(predictions)} churn predictions to {cache_path}")
        except Exception as e:
            print(f"❌ Failed to save churn cache: {e}")

    # -----------------------------

    def _cleanup_old_files(self, keep_pkl: int = 2, keep_json: int = 7) -> None:
        """Delete old challenger .pkl files and stale daily JSON cache files."""
        try:
            # Clean up old .pkl files — keep only the most recent `keep_pkl`
            model_dir = pathlib.Path(self.model_dir)
            if model_dir.exists():
                pkl_files = sorted(
                    model_dir.glob("churn_xgboost_*.pkl"),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True,
                )
                for old_file in pkl_files[keep_pkl:]:
                    old_file.unlink()
                    print(f"🗑️  Removed stale model file: {old_file.name}")
        except Exception as e:
            print(f"⚠️  .pkl cleanup failed: {e}")

        try:
            # Clean up old daily JSON cache files — keep only the most recent `keep_json`
            cache_dir = pathlib.Path(self.cache_dir)
            if cache_dir.exists():
                json_files = sorted(
                    cache_dir.glob("churn_risk_????-??-??.json"),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True,
                )
                for old_file in json_files[keep_json:]:
                    old_file.unlink()
                    print(f"🗑️  Removed stale churn cache: {old_file.name}")
        except Exception as e:
            print(f"⚠️  JSON cleanup failed: {e}")

    def train_and_register(self):
        """
        Train new XGBoost model and register in MLOps system.
        """
        try:
            print("📊 Training new XGBoost churn model...")

            # 1. Prepare training data
            X_train, y_train = self.feature_engineer.prepare_training_data()

            if X_train.empty:
                print("   ❌ No training data available")
                return False

            print(f"   Training samples: {len(X_train)}")

            # 2. Train XGBoost model
            model = XGBoostChurnModel(
                config={"max_depth": 4, "learning_rate": 0.1, "n_estimators": 100}
            )

            model.train(X_train, y_train)
            metrics = model.get_metadata()

            if metrics is None:
                print("   ❌ Model training failed - no metrics returned")
                return False

            print(f"   ✅ Model trained successfully")
            print(f"      Accuracy: {metrics.get('accuracy', 0):.1%}")
            print(f"      AUC-ROC: {metrics.get('auc_roc', 0):.3f}")

            # 3. Generate version timestamp
            version = tz_now().strftime("%Y%m%d_%H%M%S")
            model_id = f"churn_xgboost_{version}"

            filename = f"churn_xgboost_{version}.pkl"
            file_path = os.path.join(self.model_dir, filename)

            # 4. Save model file
            print(f"💾 Attempting to save to: {file_path}")
            try:
                model.save(file_path)

                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    print(f"   ✅ File created: {file_size:,} bytes")
                else:
                    print(f"   ❌ ERROR: File not created after save!")
                    return False

            except Exception as save_error:
                print(f"   ❌ SAVE FAILED: {save_error}")
                import traceback

                traceback.print_exc()
                return False

            # 5. Register in MLOps database
            self.model_manager.register_model(
                model_id=model_id,
                task_type="churn",
                algorithm="XGBoost",
                version=version,
                file_path=file_path,
                metrics=metrics,
                trained_rows=len(X_train),
            )
            try:
                end_date = tz_now()
                start_date = end_date.replace(year=end_date.year - 2)
                with self.model_manager.engine.begin() as snap_conn:
                    snap_conn.execute(
                        text("""
                            INSERT INTO dataset_snapshots
                                (model_id, task_type, start_date, end_date, row_count)
                            VALUES
                                (:model_id, :task_type, :start_date, :end_date, :row_count)
                        """),
                        {
                            "model_id": model_id,
                            "task_type": "churn",
                            "start_date": start_date.date().isoformat(),
                            "end_date": end_date.date().isoformat(),
                            "row_count": len(X_train),
                        },
                    )
                print(f"📸 Dataset snapshot recorded for {model_id}")
            except Exception as snap_err:
                print(f"⚠️  Dataset snapshot failed (non-fatal): {snap_err}")

            # 6. Champion vs Challenger — only promote if better than current champion
            auc = metrics.get("auc_roc", 0)
            current_champion = self.model_manager.get_active_model("churn")

            if current_champion:
                champion_auc = current_champion.get("metrics", {}).get("auc_roc", 0)
                if auc > champion_auc + 0.01:
                    self.model_manager.promote_model(model_id)
                    print(f"   🏆 New champion! AUC {auc:.3f} beats old champion {champion_auc:.3f}")
                else:
                    print(f"   ⚠️  Challenger AUC {auc:.3f} did not beat champion {champion_auc:.3f} (+0.01 margin). Keeping current champion.")
            else:
                # No champion yet (first install) — promote if meets baseline threshold
                if auc >= 0.85:
                    self.model_manager.promote_model(model_id)
                    print(f"   🚀 First model promoted to active (AUC: {auc:.3f})")
                else:
                    print(f"   ⚠️  Model trained but not promoted — AUC {auc:.3f} < 0.85 minimum threshold")

            self.load_active_model()
            self._cleanup_old_files()
            return True

        except Exception as e:
            print(f"   ❌ Training failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    def load_active_model(self) -> bool:
        """
        Load currently active churn model from registry.
        Self-Healing: If DB says active but file is missing, invalidate DB record.
        """
        model_info = self.model_manager.get_active_model("churn")

        if not model_info:
            print("⚠️  No active churn model found in registry.")
            self.active_model = None  # Ensure state is clear
            return False

        algorithm = model_info["algorithm"]
        file_path = model_info["file_path"]
        model_id = model_info["model_id"]

        # --- SELF HEALING LOGIC ---
        if not os.path.exists(file_path):
            _logger.critical(
                f"Model file missing for {model_id} at {file_path}. "
                f"Invalidating registry record and scheduling retrain."
            )

            # Atomically deactivate corrupted registry record
            with self.engine.connect() as conn:
                conn.execute(
                    text(
                        "UPDATE model_registry SET is_active = 0 WHERE model_id = :mid"
                    ),
                    {"mid": model_id},
                )
                conn.commit()

            self.active_model = None
            self.model_instance = None

            # Trigger background retrain (guarded against duplicates)
            global _global_retrain_in_progress
            with _global_retrain_lock:
                if not _global_retrain_in_progress:
                    _global_retrain_in_progress = True

                    def _background_retrain():
                        try:
                            _logger.info("Background churn model retrain started.")
                            self.train_and_register()
                            _logger.info("Background churn model retrain completed.")
                        except Exception as e:
                            _logger.error(f"Background churn retrain failed: {e}")
                        finally:
                            with _global_retrain_lock:
                                global _global_retrain_in_progress
                                _global_retrain_in_progress = False

                    threading.Thread(target=_background_retrain, daemon=True).start()

            return False
        # ---------------------------

        try:
            if algorithm == "XGBoost":
                self.model_instance = XGBoostChurnModel(config={})
                self.model_instance.load(file_path)
            elif algorithm == "Heuristic":
                self.model_instance = HeuristicChurnModel(config={})
                self.model_instance.load(file_path)

            # Set active model ONLY after successful load
            self.active_model = model_info
            print(f"✅ Loaded active model: {model_id}")
            return True

        except Exception as e:
            print(f"⚠️  Error loading model (File corrupt?): {e}")
            self.active_model = None
            return False

    def get_model_info(self) -> Dict:
        """
        Get information about currently active model.
        Serves as the Single Source of Truth for the Dashboard.
        """
        # If we are running on fallback/heuristic because load failed
        if not self.model_instance or not self.active_model:
            return {
                "algorithm": "Heuristic (Fallback)",
                "model_id": "heuristic_fallback",
                "version": "1.0.0",
                "trained_at": tz_now().isoformat(),
                "metrics": {
                    "accuracy": 0.65,  # Baseline placeholders
                    "auc_roc": 0.5,
                    "precision": 0,
                    "recall": 0,
                    "f1_score": 0,
                },
            }

        # If we have a loaded model, return its ACTUAL metrics from the DB record/Instance
        # We prioritize the 'metrics' JSON stored in the DB record if available
        metrics = self.active_model.get("metrics")

        # If DB metrics are a string (JSON), parse them
        if isinstance(metrics, str):
            try:
                metrics = json.loads(metrics)
            except:
                metrics = {}

        # Fallback to instance metadata if DB is empty
        if not metrics and self.model_instance:
            metrics = self.model_instance.get_metadata()

        return {
            "model_id": self.active_model.get("model_id", "unknown"),
            "algorithm": self.active_model.get("algorithm", "unknown"),
            "version": self.active_model.get("version", "unknown"),
            "trained_at": self.active_model.get("trained_at", "unknown"),
            # Flatten metrics for easier frontend consumption
            "metrics": {
                "accuracy": metrics.get("accuracy", 0),
                "precision": metrics.get("precision", 0),
                "recall": metrics.get("recall", 0),
                "f1_score": metrics.get("f1_score", 0),
                "auc_roc": metrics.get("auc_roc", 0),
                "support": metrics.get("validation_samples", 0),
            },
        }

    def predict_all_customers(self) -> List[Dict]:
        """
        Predict churn risk for all active customers.
        Use Cache if available (optimizes dashboard speed).
        """
        # 1. CHECK CACHE FIRST
        cached_data = self.get_cached_predictions()
        if cached_data:
            return cached_data

        # 2. RUN PREDICTION PIPELINE (Cache Miss)
        # Prepare features
        X_current = self.feature_engineer.prepare_current_data()

        if X_current.empty:
            return []

        # Load model if not already loaded
        if not self.model_instance:
            success = self.load_active_model()
            if not success:
                # Fallback to heuristic
                print("⚠️  Using fallback heuristic model")
                self.model_instance = HeuristicChurnModel(config={})
                X_train, y_train = self.feature_engineer.prepare_training_data()
                self.model_instance.train(X_train, y_train)

        # Make predictions
        print(f"🔮 Making predictions with: {type(self.model_instance).__name__}")
        predictions = self.model_instance.predict(X_current)

        # Get customer details
        customer_ids = X_current.index.tolist()

        with self.engine.connect() as conn:
            customer_details = {}
            if customer_ids:
                placeholders = ",".join(["?" for _ in customer_ids])
                sql_query = f"""
                    SELECT id, name, mobile, balance
                    FROM customer
                    WHERE id IN ({placeholders})
                """
                # Using raw connection for sqlite parameter style
                raw_conn = conn.connection
                cursor = raw_conn.execute(sql_query, customer_ids)
                for row in cursor:
                    customer_details[row[0]] = {
                        "name": row[1],
                        "mobile": row[2],
                        "balance": float(row[3] or 0),
                    }

        # Format results
        results = []
        for idx, customer_id in enumerate(customer_ids):
            churn_score = float(predictions[idx])

            # Determine risk level
            if churn_score >= 0.7:
                risk_level = "high"
                risk_label = "High Risk"
            elif churn_score >= 0.4:
                risk_level = "medium"
                risk_label = "Medium Risk"
            else:
                risk_level = "low"
                risk_label = "Low Risk"

            customer_info = customer_details.get(customer_id, {})

            result = {
                "customer_id": int(customer_id),
                "customer_name": customer_info.get("name", "Unknown"),
                "mobile": customer_info.get("mobile", ""),
                "churn_score": round(churn_score, 4),
                "risk_level": risk_level,
                "risk_label": risk_label,
                "balance": customer_info.get("balance", 0),
                "features": {
                    "recency": int(X_current.loc[customer_id, "recency"]),
                    "frequency": int(X_current.loc[customer_id, "frequency"]),
                    "monetary": float(X_current.loc[customer_id, "monetary"]),
                    "velocity": float(X_current.loc[customer_id, "velocity"]),
                },
            }
            results.append(result)

        # Sort by churn score descending
        results.sort(key=lambda x: x["churn_score"], reverse=True)

        # Log prediction stats
        self._log_predictions(predictions)

        # 3. SAVE TO CACHE (Optimizes next load)
        self.save_predictions_to_cache(results)

        return results

    def predict_single_customer(self, customer_id: int) -> Optional[Dict]:
        """Predict churn risk for a single customer."""
        all_predictions = self.predict_all_customers()
        for pred in all_predictions:
            if pred["customer_id"] == customer_id:
                return pred
        return None

    def get_high_risk_customers(
        self, threshold: float = 0.7, limit: int = 50
    ) -> List[Dict]:
        """Get customers with churn risk above threshold."""
        all_predictions = self.predict_all_customers()
        high_risk = [p for p in all_predictions if p["churn_score"] >= threshold]
        return high_risk[:limit]

    def get_model_info(self) -> Dict:
        """Get information about currently active model with full metrics."""
        # Load model if not already loaded
        if not self.model_instance:
            success = self.load_active_model()
            if not success and not self.active_model:
                return {
                    "algorithm": "Heuristic (Fallback)",
                    "version": "1.0.0",
                    "status": "Using fallback - no active model in registry",
                    "metrics": {},
                    "feature_importance": {},
                }

        if not self.active_model:
            return {
                "algorithm": "Heuristic (Fallback)",
                "version": "1.0.0",
                "status": "Using fallback - no active model in registry",
                "metrics": {},
                "feature_importance": {},
            }

        full_metadata = {}
        feature_importance = {}

        if self.model_instance:
            try:
                full_metadata = self.model_instance.get_metadata() or {}
                feature_importance = self.model_instance.get_feature_importance() or {}
            except Exception as e:
                print(f"⚠️ Error getting model metadata: {e}")

        return {
            "model_id": self.active_model.get("model_id", "unknown"),
            "algorithm": self.active_model.get("algorithm", "unknown"),
            "version": self.active_model.get("model_version", "unknown"),
            "trained_at": self.active_model.get("trained_at", "unknown"),
            "promoted_at": self.active_model.get("promoted_at", "unknown"),
            "metrics": {
                "accuracy": full_metadata.get("accuracy", 0),
                "precision": full_metadata.get("precision", 0),
                "recall": full_metadata.get("recall", 0),
                "f1_score": full_metadata.get("f1_score", 0),
                "auc_roc": full_metadata.get("auc_roc", 0),
                "training_samples": full_metadata.get("training_samples", 0),
                "validation_samples": full_metadata.get("validation_samples", 0),
            },
            "feature_importance": feature_importance,
        }

    def _log_predictions(self, predictions):
        """Log aggregated prediction statistics to database."""
        if len(predictions) == 0:
            return

        stats = {
            "date": tz_now().strftime("%Y-%m-%d"),
            "task_type": "churn",
            "model_version": (
                self.active_model["model_version"] if self.active_model else "heuristic"
            ),
            "total_predictions": len(predictions),
            "avg_prediction": float(np.mean(predictions)),
            "high_risk_count": int((predictions >= 0.7).sum()),
            "p25": float(np.percentile(predictions, 25)),
            "p50": float(np.percentile(predictions, 50)),
            "p75": float(np.percentile(predictions, 75)),
            "p95": float(np.percentile(predictions, 95)),
        }

        query = text("""
            INSERT OR REPLACE INTO prediction_log (
                date, task_type, model_version,
                total_predictions, avg_prediction, high_risk_count,
                p25, p50, p75, p95
            ) VALUES (
                :date, :task_type, :model_version,
                :total_predictions, :avg_prediction, :high_risk_count,
                :p25, :p50, :p75, :p95
            )
        """)

        try:
            with self.engine.connect() as conn:
                conn.execute(query, stats)
                conn.commit()
        except Exception as e:
            print(f"⚠️  Prediction logging failed: {e}")
