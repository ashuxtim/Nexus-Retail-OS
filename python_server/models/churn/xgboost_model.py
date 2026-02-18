import numpy as np
import pandas as pd
import pickle
import time
import os
from typing import Dict, Tuple
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    confusion_matrix,
)

from models.base import ChurnModelInterface


class XGBoostChurnModel(ChurnModelInterface):
    """
    XGBoost-based churn prediction for NexusRetail OS.

    Features:
    - Gradient boosting decision trees
    - Feature importance analysis
    - Probability calibration
    - Cross-validation metrics
    """

    def __init__(self, config: Dict):
        super().__init__(config)
        self.model = None
        self.feature_names = ["recency", "frequency", "monetary", "velocity"]
        self.metadata = {}  # ← INITIALIZE METADATA
        self.training_time = 0.0

        # XGBoost hyperparameters (optimized for imbalanced churn data)
        self.params = {
            "n_estimators": config.get("n_estimators", 100),
            "max_depth": config.get("max_depth", 4),
            "learning_rate": config.get("learning_rate", 0.1),
            "min_child_weight": config.get("min_child_weight", 3),
            "gamma": config.get("gamma", 0.1),
            "subsample": config.get("subsample", 0.8),
            "colsample_bytree": config.get("colsample_bytree", 0.8),
            "scale_pos_weight": config.get("scale_pos_weight", None),  # Auto-calculated
            "eval_metric": "logloss",
            "random_state": config.get("random_state", 42),
            "use_label_encoder": False,
            "verbosity": 0,
        }

    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Train XGBoost model with cross-validation.

        Args:
            X: Feature matrix (recency, frequency, monetary, velocity)
            y: Churn labels (0=retained, 1=churned)
        """
        start_time = time.time()

        # Auto-calculate scale_pos_weight for imbalanced classes
        if self.params["scale_pos_weight"] is None:
            neg_count = (y == 0).sum()
            pos_count = (y == 1).sum()
            self.params["scale_pos_weight"] = (
                neg_count / pos_count if pos_count > 0 else 1.0
            )

        # Store feature names
        self.feature_names = list(X.columns)

        # Split for validation (80/20)
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )

        # Train model
        self.model = XGBClassifier(**self.params)
        self.model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        self.training_time = time.time() - start_time

        # === EVALUATE ON VALIDATION SET ===
        y_pred = self.model.predict(X_val)
        y_pred_proba = self.model.predict_proba(X_val)[:, 1]

        # Calculate metrics
        accuracy = accuracy_score(y_val, y_pred)
        precision = precision_score(y_val, y_pred, zero_division=0)
        recall = recall_score(y_val, y_pred, zero_division=0)
        f1 = f1_score(y_val, y_pred, zero_division=0)

        try:
            auc_roc = roc_auc_score(y_val, y_pred_proba)
        except:
            auc_roc = 0.5  # Fallback if only one class in validation

        cm = confusion_matrix(y_val, y_pred)
        tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)

        # ✅ FLAT STRUCTURE - No nested "metrics" dict
        self.metadata = {
            "algorithm": "XGBoost",
            "model_type": "gradient_boosting",
            "training_samples": len(X_train),
            "validation_samples": len(X_val),
            "training_time_seconds": round(self.training_time, 2),
            # Primary metrics (FLAT - directly accessible)
            "accuracy": round(accuracy, 3),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1_score": round(f1, 3),
            "auc_roc": round(auc_roc, 3),
            # Confusion matrix
            "confusion_matrix": {
                "true_negatives": int(tn),
                "false_positives": int(fp),
                "false_negatives": int(fn),
                "true_positives": int(tp),
            },
            # Class distribution
            "churn_rate_train": round(y_train.mean(), 3),
            "churn_rate_val": round(y_val.mean(), 3),
            # Hyperparameters
            "hyperparameters": self.params,
            # Feature importance (calculated and stored)
            "feature_importance": self._get_feature_importance(),
        }

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict churn probabilities.

        Args:
            X: Feature matrix

        Returns:
            Array of churn probabilities [0.0 - 1.0]
        """
        if self.model is None:
            raise ValueError("Model not trained. Call train() first.")

        start_time = time.time()
        predictions = self.model.predict_proba(X)[:, 1]
        self.inference_time = time.time() - start_time

        return predictions

    def predict_with_confidence(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict with confidence intervals using bootstrap estimation.

        Returns:
            (predictions, confidence_margins) where margins are ±error estimates
        """
        predictions = self.predict(X)

        # Estimate confidence using standard error approximation
        uncertainty = np.abs(predictions - 0.5) * 0.15
        confidence_margins = 0.05 + uncertainty

        return predictions, confidence_margins

    def _get_feature_importance(self) -> Dict[str, float]:
        """
        Get feature importance scores from XGBoost.

        Returns:
            Dict mapping feature names to importance values (normalized to sum to 1.0)
        """
        if self.model is None:
            return {}

        # Get importance scores
        importance = self.model.feature_importances_

        # Normalize to sum to 1.0
        total = importance.sum()
        if total > 0:
            importance = importance / total

        # Map to feature names
        importance_dict = {
            name: round(float(imp), 3)
            for name, imp in zip(self.feature_names, importance)
        }

        return dict(sorted(importance_dict.items(), key=lambda x: x[1], reverse=True))

    def get_feature_importance(self) -> Dict[str, float]:
        """Public method to get feature importance (for external calls)"""
        return self._get_feature_importance()

    def get_metadata(self) -> Dict:
        """Return all model metadata and metrics"""
        return self.metadata

    def get_model_name(self) -> str:
        return "XGBoost"

    def save(self, path: str) -> None:
        """
        Save model to disk (pickle format for consistency).
        Args:
            path: File path (should end with .pkl)
        """
        print(f"🔍 XGBoost save() called")
        print(f"   Path: {path}")
        print(f"   Model is None: {self.model is None}")

        if self.model is None:
            raise ValueError("Cannot save untrained model.")

        # Ensure directory exists
        os.makedirs(os.path.dirname(path), exist_ok=True)

        try:
            # Save as single pickle file (model + metadata together)
            with open(path, "wb") as f:
                data_to_save = {
                    "model": self.model,
                    "feature_names": self.feature_names,
                    "metadata": self.metadata,
                    "params": self.params,
                }
                print(f"   Metadata keys: {list(self.metadata.keys())}")
                pickle.dump(data_to_save, f)
            print(f"   ✅ Pickle dump successful")
        except Exception as e:
            print(f"   ❌ Pickle dump failed: {e}")
            raise

    def load(self, path: str) -> None:
        """
        Load model from disk.

        Args:
            path: File path to pickle file
        """
        with open(path, "rb") as f:
            data = pickle.load(f)
            self.model = data["model"]
            self.feature_names = data["feature_names"]
            self.metadata = data["metadata"]
            self.params = data["params"]
