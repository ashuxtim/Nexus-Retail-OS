import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from core.time_utils import now as tz_now
from sqlalchemy import text
from typing import Dict, Tuple


class DemandAnalyzer:
    """
    Analyze historical demand patterns for stockout prediction.

    Calculates:
    - Daily demand statistics (mean, std, distribution)
    - Demand variability (coefficient of variation)
    - Lead time statistics
    """

    def __init__(self, engine):
        self.engine = engine

    def analyze_product_demand(self, variant_id: int, lookback_days: int = 90) -> Dict:
        """
        Analyze demand patterns for a specific product variant.

        Args:
            variant_id: Product variant ID
            lookback_days: How far back to analyze (default 90 days)

        Returns:
            Dict with demand statistics
        """
        cutoff_date = tz_now() - timedelta(days=lookback_days)

        # Fetch daily sales for this variant
        query = text("""
            SELECT 
                DATE(s.sale_date) as date,
                SUM(i.quantity) as daily_demand
            FROM credit_sale s
            JOIN credit_sale_item i ON s.id = i.sale_id
            WHERE i.variant_id = :variant_id
              AND s.sale_date >= :cutoff
            GROUP BY DATE(s.sale_date)
            ORDER BY date
        """)

        with self.engine.connect() as conn:
            df = pd.read_sql(
                query,
                conn,
                params={"variant_id": variant_id, "cutoff": cutoff_date.date()},
            )

        if df.empty:
            # No sales history - return defaults
            return {
                "variant_id": variant_id,
                "daily_demand_mean": 0.0,
                "daily_demand_std": 0.0,
                "demand_distribution": "unknown",
                "coefficient_of_variation": 0.0,
                "total_sales_days": 0,
                "zero_demand_days": lookback_days,
                "max_daily_demand": 0,
                "percentile_95": 0.0,
                "has_sufficient_history": False,
            }

        # Fill missing dates with zero demand
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")

        # Create full date range
        date_range = pd.date_range(
            start=cutoff_date.date(), end=tz_now().date(), freq="D"
        )
        df = df.reindex(date_range, fill_value=0)
        df.columns = ["daily_demand"]

        # Calculate statistics
        daily_demand = df["daily_demand"].values
        mean_demand = daily_demand.mean()
        std_demand = daily_demand.std()

        # Coefficient of Variation (CV)
        cv = (std_demand / mean_demand) if mean_demand > 0 else 0.0

        # Detect distribution type
        if mean_demand < 5 and cv > 1.0:
            distribution = "poisson"
        elif cv < 0.5:
            distribution = "normal"
        else:
            distribution = "empirical"

        # Count zero-demand days
        zero_days = (daily_demand == 0).sum()
        sales_days = len(daily_demand) - zero_days

        return {
            "variant_id": variant_id,
            "daily_demand_mean": float(mean_demand),
            "daily_demand_std": float(std_demand),
            "demand_distribution": distribution,
            "coefficient_of_variation": float(cv),
            "total_sales_days": int(sales_days),
            "zero_demand_days": int(zero_days),
            "max_daily_demand": int(daily_demand.max()),
            "percentile_95": float(np.percentile(daily_demand, 95)),
            "has_sufficient_history": sales_days >= 10,
            "historical_demand": daily_demand.tolist(),
        }

    def estimate_lead_time(self, variant_id: int) -> Tuple[int, int]:
        """
        Estimate supplier lead time based on product category.

        Returns:
            (min_lead_time_days, max_lead_time_days)
        """
        # Get category from product table (not product_category table)
        query = text("""
            SELECT p.category
            FROM product_variant v
            JOIN product p ON v.product_id = p.id
            WHERE v.id = :variant_id
        """)

        try:
            with self.engine.connect() as conn:
                result = conn.execute(query, {"variant_id": variant_id}).fetchone()

            if result and result[0]:
                category = result[0].lower()

                # Category-based lead time estimates
                if "frozen" in category or "dairy" in category:
                    return (1, 3)  # Perishables: 1-3 days
                elif "beverage" in category or "snack" in category:
                    return (2, 5)  # Fast-moving: 2-5 days
                else:
                    return (3, 7)  # General: 3-7 days
        except:
            pass

        return (3, 7)  # Default fallback

    def get_current_stock(self, variant_id: int) -> int:
        """Get current stock level for variant"""
        query = text("""
            SELECT current_stock 
            FROM product_variant 
            WHERE id = :variant_id
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"variant_id": variant_id}).fetchone()

        return result[0] if result else 0
