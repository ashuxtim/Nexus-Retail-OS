import os
import json
from datetime import datetime
from core.time_utils import now as tz_now
from typing import Dict, Optional
from sqlalchemy import text


class ModelManager:
    """
    Manages ML model lifecycle in database registry.

    Responsibilities:
    - Register new models
    - Promote models to active
    - Retrieve active models
    - Track model versions
    """

    def __init__(self, engine):
        self.engine = engine

    def register_model(
        self,
        model_id: str,
        task_type: str,
        algorithm: str,
        version: str,
        file_path: str,
        metrics: Dict,
        trained_rows: int,
        data_window_months: int = 24,
        is_active: bool = False,
    ) -> bool:
        """
        Register a new trained model in the registry.

        Args:
            model_id: Unique model identifier
            task_type: 'churn', 'forecast', or 'market_basket'
            algorithm: 'XGBoost', 'Prophet', 'Heuristic', etc.
            version: Version string (timestamp or semantic version)
            file_path: Absolute path to model file
            metrics: Dict of evaluation metrics
            trained_rows: Number of samples used for training
            data_window_months: Months of historical data used
            is_active: If True, set as active immediately (auto-promote)

        Returns:
            success: bool
        """
        try:
            # Insert new model as INACTIVE — champion deactivation happens ONLY
            # inside promote_model() after a quality check passes.
            # This prevents the champion from being killed before we know if
            # the challenger is good enough to replace it.
            with self.engine.begin() as conn:
                conn.execute(
                    text("""
                    INSERT INTO model_registry (
                        model_id, task_type, algorithm, model_version,
                        trained_at, trained_rows, data_window_months,
                        file_path, metrics_json,
                        is_active, evaluation_status, promoted_at
                    ) VALUES (
                        :model_id, :task_type, :algorithm, :version,
                        :trained_at, :trained_rows, :data_window_months,
                        :file_path, :metrics_json,
                        :is_active, 'pending', NULL
                    )
                """),
                    {
                        "model_id": model_id,
                        "task_type": task_type,
                        "algorithm": algorithm,
                        "version": version,
                        "trained_at": tz_now().isoformat(),
                        "trained_rows": trained_rows,
                        "data_window_months": data_window_months,
                        "file_path": file_path,
                        "metrics_json": json.dumps(metrics),
                        "is_active": 1 if is_active else 0,
                    },
                )

            print(f"✅ Model registered: {model_id}")
            return True

        except Exception as e:
            print(f"❌ Model registration failed: {e}")
            return False

    def promote_model(self, candidate_id: str) -> bool:
        """
        Promote candidate to active model (atomic operation).

        Args:
            candidate_id: Model ID to promote

        Returns:
            True if successful
        """
        try:
            with self.engine.begin() as conn:
                # Step 1: Deactivate current active model (if exists)
                conn.execute(
                    text("""
                    UPDATE model_registry
                    SET is_active = 0, replaced_by = :new_id
                    WHERE task_type = (
                        SELECT task_type FROM model_registry WHERE model_id = :new_id
                    )
                    AND is_active = 1
                    AND model_id != :new_id
                """),
                    {"new_id": candidate_id},
                )

                # Step 2: Activate candidate
                conn.execute(
                    text("""
                    UPDATE model_registry
                    SET is_active = 1, promoted_at = :now, evaluation_status = 'approved'
                    WHERE model_id = :model_id
                """),
                    {"now": tz_now().isoformat(), "model_id": candidate_id},
                )

            print(f"✅ Model promoted: {candidate_id}")
            return True

        except Exception as e:
            print(f"❌ Model promotion failed: {e}")
            import traceback

            traceback.print_exc()
            return False

    def get_active_model(self, task_type: str) -> Optional[Dict]:
        """
        Get currently active model for a task.

        Args:
            task_type: 'churn', 'forecast', or 'market_basket'

        Returns:
            Model info dict or None
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text("""
                    SELECT 
                        model_id, algorithm, model_version,
                        file_path, trained_at, promoted_at,
                        metrics_json, trained_rows
                    FROM model_registry
                    WHERE task_type = :task_type AND is_active = 1
                    ORDER BY trained_at DESC
                    LIMIT 1
                """),
                    {"task_type": task_type},
                ).fetchone()

                if not result:
                    return None
                file_path = result[3]
                if file_path and not os.path.exists(file_path):
                    print(f"⚠️  Registry points to missing file: {file_path}. Deactivating stale row.")
                    try:
                        with self.engine.begin() as write_conn:
                            write_conn.execute(
                                text("UPDATE model_registry SET is_active = 0 WHERE model_id = :mid"),
                                {"mid": result[0]},
                            )
                    except Exception as cleanup_err:
                        print(f"⚠️  Failed to deactivate stale registry row: {cleanup_err}")
                    return None
                return {
                    "model_id": result[0],
                    "algorithm": result[1],
                    "model_version": result[2],
                    "file_path": file_path,
                    "trained_at": result[4],
                    "promoted_at": result[5],
                    "metrics": json.loads(result[6]) if result[6] else {},
                    "trained_rows": result[7],
                }

        except Exception as e:
            print(f"⚠️  Error getting active model: {e}")
            return None

    def get_model_history(self, task_type: str, limit: int = 10) -> list:
        """Get historical models for a task."""
        try:
            with self.engine.connect() as conn:
                results = conn.execute(
                    text("""
                    SELECT 
                        model_id, algorithm, model_version,
                        trained_at, is_active, metrics_json
                    FROM model_registry
                    WHERE task_type = :task_type
                    ORDER BY trained_at DESC
                    LIMIT :limit
                """),
                    {"task_type": task_type, "limit": limit},
                ).fetchall()

                history = []
                for row in results:
                    history.append(
                        {
                            "model_id": row[0],
                            "algorithm": row[1],
                            "version": row[2],
                            "trained_at": row[3],
                            "is_active": bool(row[4]),
                            "metrics": json.loads(row[5]) if row[5] else {},
                        }
                    )

                return history

        except Exception as e:
            print(f"⚠️  Error getting model history: {e}")
            return []
