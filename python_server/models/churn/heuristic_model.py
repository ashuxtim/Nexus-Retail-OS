import numpy as np
import pandas as pd
import pickle
from typing import Dict, Tuple
from models.base import ChurnModelInterface


class HeuristicChurnModel(ChurnModelInterface):
    """
    Rule-based churn prediction (your current logic as a fallback).

    Rules:
    - Velocity < 0.5 AND Recency > 20 → 85% risk
    - Recency > 60 → 95% risk
    - Otherwise → Based on recency/velocity combination

    Used as fallback if ML models fail.
    """

    def __init__(self, config: Dict):
        super().__init__(config)
        self.model_name = "Heuristic Rule-Based"
        self.thresholds = {
            "velocity_low": config.get("velocity_low", 0.5),
            "recency_medium": config.get("recency_medium", 20),
            "recency_high": config.get("recency_high", 60),
        }
        self.model = "initialized"  # Heuristics don't need training

    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Heuristics don't train - they use fixed rules.
        But we calculate basic stats for metadata.
        """
        self.metadata = {
            "algorithm": "Heuristic Rules",
            "training_samples": len(X),
            "feature_stats": {
                "recency_mean": float(X["recency"].mean()),
                "frequency_mean": float(X["frequency"].mean()),
                "velocity_mean": float(X["velocity"].mean()),
            },
        }

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Apply heuristic rules to calculate churn probability"""
        probabilities = np.zeros(len(X))

        for idx, (cid, row) in enumerate(X.iterrows()):
            recency = row["recency"]
            velocity = row["velocity"]

            # Rule 1: Long absence = very high risk
            if recency > self.thresholds["recency_high"]:
                prob = 0.95

            # Rule 2: Declining velocity + medium absence = high risk
            elif (
                velocity < self.thresholds["velocity_low"]
                and recency > self.thresholds["recency_medium"]
            ):
                prob = 0.85

            # Rule 3: Declining velocity only = medium risk
            elif velocity < self.thresholds["velocity_low"]:
                prob = 0.60

            # Rule 4: Moderate absence = low-medium risk
            elif recency > self.thresholds["recency_medium"]:
                prob = 0.45

            # Rule 5: Active customer = low risk
            else:
                prob = 0.15

            probabilities[idx] = prob

        return probabilities

    def predict_with_confidence(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Heuristics have no statistical confidence intervals.
        Return fixed ±10% margin.
        """
        predictions = self.predict(X)
        confidence_margins = np.full(len(predictions), 0.10)
        return predictions, confidence_margins

    def get_feature_importance(self) -> Dict[str, float]:
        """
        Heuristics are primarily driven by recency and velocity.
        Return approximate importance.
        """
        return {"recency": 0.50, "velocity": 0.40, "frequency": 0.05, "monetary": 0.05}

    def get_metadata(self) -> Dict:
        """
        Return metadata (no accuracy metrics for heuristics).
        """
        return {
            "algorithm": "Heuristic Rules",
            "model_type": "deterministic",
            "thresholds": self.thresholds,
            **self.metadata,
        }

    def get_model_name(self) -> str:
        return "Heuristic"

    def save(self, path: str) -> None:
        """Save heuristic config"""
        with open(path, "wb") as f:
            pickle.dump({"thresholds": self.thresholds, "metadata": self.metadata}, f)

    def load(self, path: str) -> None:
        """Load heuristic config"""
        with open(path, "rb") as f:
            data = pickle.load(f)
            self.thresholds = data["thresholds"]
            self.metadata = data["metadata"]
            self.model = "loaded"
