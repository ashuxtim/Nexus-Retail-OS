from abc import ABC, abstractmethod
from typing import Dict, Tuple, Optional
import numpy as np
import pandas as pd


class ChurnModelInterface(ABC):
    """
    Abstract base class for all churn prediction models.

    This interface ensures all models (XGBoost, CatBoost, Logistic Regression, Heuristics)
    return the same output format, making them interchangeable.
    """

    def __init__(self, config: Dict):
        self.config = config
        self.model = None
        self.metadata = {}
        self.training_time = 0.0
        self.inference_time = 0.0

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Train the model on historical data.

        Args:
            X: Feature matrix (columns: recency, frequency, monetary, velocity)
            y: Target labels (0 = retained, 1 = churned)
        """
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict churn probabilities.

        Args:
            X: Feature matrix

        Returns:
            Array of churn probabilities [0.0 - 1.0]
        """
        pass

    @abstractmethod
    def predict_with_confidence(self, X: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict with confidence intervals.

        Args:
            X: Feature matrix

        Returns:
            (predictions, confidence_intervals) where confidence_intervals are ±error margins
        """
        pass

    @abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        """
        Return feature importance scores.

        Returns:
            Dict mapping feature names to importance values (sum to 1.0)
        """
        pass

    @abstractmethod
    def get_metadata(self) -> Dict:
        """
        Return model performance metrics.

        Returns:
            Dict with keys: accuracy, precision, recall, f1_score, auc_roc, etc.
        """
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Return model algorithm name (e.g., 'XGBoost', 'Heuristic')"""
        pass

    @abstractmethod
    def save(self, path: str) -> None:
        """Save model to disk"""
        pass

    @abstractmethod
    def load(self, path: str) -> None:
        """Load model from disk"""
        pass

    def is_trained(self) -> bool:
        """Check if model has been trained"""
        return self.model is not None
