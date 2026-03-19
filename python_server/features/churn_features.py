import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from core.time_utils import now as tz_now
from sqlalchemy import text
from typing import Tuple


class ChurnFeatureEngineer:
    """
    Centralized feature engineering for churn prediction.

    All models use the same features to ensure consistency.
    """

    def __init__(self, engine):
        self.engine = engine
        self.feature_version = "v1.0"

    def calculate_rfm(
        self, anchor_date: datetime, lookback_days: int = 365
    ) -> pd.DataFrame:
        """
        Calculate RFM (Recency, Frequency, Monetary) + Velocity features.

        Args:
            anchor_date: Point in time to calculate features (usually now, or T-90 for training)
            lookback_days: How far back to look for transactions

        Returns:
            DataFrame with customer_id as index and RFM+V columns
        """
        cutoff = anchor_date - timedelta(days=lookback_days)

        query = text("""
            SELECT customer_id, sale_date, SUM(quantity*price_at_sale) as total
            FROM credit_sale s
            JOIN credit_sale_item i ON s.id=i.sale_id
            WHERE sale_date >= :cutoff AND sale_date < :anchor
            GROUP BY customer_id, sale_date
        """)

        with self.engine.connect() as conn:
            df = pd.read_sql(
                query,
                conn,
                params={
                    "cutoff": cutoff.strftime("%Y-%m-%d"),
                    "anchor": anchor_date.strftime("%Y-%m-%d"),
                },
            )

        if df.empty:
            return pd.DataFrame()

        # Defensive cast — daily_seed (numpy rng.choice) can store customer_id
        # as BLOB in SQLite. Mixed bytes/int breaks pandas groupby sort.
        df["customer_id"] = pd.to_numeric(df["customer_id"], errors="coerce").astype("Int64")
        df = df.dropna(subset=["customer_id"])
        df["customer_id"] = df["customer_id"].astype(int)

        df["sale_date"] = pd.to_datetime(df["sale_date"])

        # Strip tz for pandas arithmetic — DB timestamps are tz-naive
        anchor_naive = (
            anchor_date.replace(tzinfo=None) if anchor_date.tzinfo else anchor_date
        )

        # === RECENCY, FREQUENCY, MONETARY ===
        rfm = (
            df.groupby("customer_id")
            .agg(
                {
                    "sale_date": lambda x: (anchor_naive - x.max()).days,  # Recency
                    "customer_id": "count",  # Frequency
                    "total": "sum",  # Total spend
                }
            )
            .rename(
                columns={
                    "sale_date": "recency",
                    "customer_id": "frequency",
                    "total": "total_spend",
                }
            )
        )

        # Monetary = Average transaction value
        rfm["monetary"] = rfm["total_spend"] / rfm["frequency"]

        # === VELOCITY ===
        # Recent 30-day spend / Long-term average monthly spend
        v_cutoff = anchor_naive - timedelta(days=30)

        recent_spend = (
            df[df["sale_date"] >= v_cutoff].groupby("customer_id")["total"].sum()
        )
        long_term_spend = df.groupby("customer_id")["total"].sum()

        # Monthly average over lookback period
        monthly_avg = long_term_spend / (lookback_days / 30.0)

        rfm["velocity"] = (recent_spend / monthly_avg).fillna(0).clip(0, 3)

        # Fill missing velocity (customers with no recent purchases)
        rfm["velocity"] = rfm["velocity"].fillna(0)

        return rfm[["recency", "frequency", "monetary", "velocity"]]

    def prepare_training_data(self) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Prepare training data using time-travel logic.

        Strategy:
        1. Calculate features at T-90 (90 days ago)
        2. Label: Did customer purchase in next 90 days? (0=yes, 1=churned)
        3. This simulates "predicting the future" with past data

        Returns:
            (X_train, y_train) where X has RFM+V features, y is churn label
        """
        now = tz_now()
        train_anchor = now - timedelta(days=90)

        # Features at T-90
        X_train = self.calculate_rfm(train_anchor, lookback_days=365)

        if X_train.empty:
            return pd.DataFrame(), pd.Series()

        # Filter: Only customers with 3+ purchases (cold start filter)
        X_train = X_train[X_train["frequency"] >= 3].copy()

        if X_train.empty or len(X_train) < 10:
            return pd.DataFrame(), pd.Series()

        # === LABELS: Active in 90 days after train_anchor? ===
        query = text("""
            SELECT DISTINCT customer_id
            FROM credit_sale
            WHERE sale_date >= :start AND sale_date < :end
        """)

        with self.engine.connect() as conn:
            active_customers = pd.read_sql(
                query,
                conn,
                params={
                    "start": train_anchor.strftime("%Y-%m-%d"),
                    "end": now.strftime("%Y-%m-%d"),
                },
            )

        active_set = set(active_customers["customer_id"])

        # Label: 1 if churned (not in active set), 0 if retained
        y_train = pd.Series(
            [0 if cid in active_set else 1 for cid in X_train.index],
            index=X_train.index,
            name="churned",
        )

        return X_train, y_train

    def prepare_current_data(self) -> pd.DataFrame:
        """
        Prepare features for current customers (prediction mode).

        Returns:
            DataFrame with RFM+V features for all active customers
        """
        now = tz_now()
        X_current = self.calculate_rfm(now, lookback_days=365)

        if X_current.empty:
            return pd.DataFrame()

        # Filter: Only customers with 3+ purchases
        X_current = X_current[X_current["frequency"] >= 3].copy()

        return X_current

    def get_feature_hash(self) -> str:
        """Return hash of feature names/types (for versioning)"""
        features = ["recency", "frequency", "monetary", "velocity"]
        return str(hash(tuple(features)))
