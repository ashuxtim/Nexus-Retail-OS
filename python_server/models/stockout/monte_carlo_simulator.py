import numpy as np
from typing import Dict, List, Tuple


class MonteCarloSimulator:
    """
    Monte Carlo simulation for stockout probability.
    ULTRA-OPTIMIZED: Matrix vectorization (50-200x faster than loops).
    """

    def __init__(self, n_simulations: int = 1000, forecast_days: int = 30):
        """
        Args:
            n_simulations: 1000 is the sweet spot for speed vs accuracy.
            forecast_days: Days to simulate (default 30).
        """
        self.n_simulations = n_simulations
        self.forecast_days = forecast_days

    def simulate_stockout_probability(
        self, current_stock: int, demand_stats: Dict, lead_time_range: Tuple[int, int]
    ) -> Dict:
        """
        Run Matrix-based Monte Carlo simulation.
        Generates all random demands at once for maximum speed.
        """
        # 1. Edge Case: Already empty
        if current_stock <= 0:
            return self._empty_response(1.0, 0.0)

        mean = demand_stats.get("daily_demand_mean", 0)
        std = demand_stats.get("daily_demand_std", 0)

        # 2. Edge Case: No demand
        if mean == 0:
            return self._empty_response(0.0, None)

        # --- MATRIX SIMULATION ---

        # A. Generate ALL demands for ALL days at once
        # Shape: (1000, 30) - drastically smaller memory footprint than 10k
        if demand_stats.get("demand_distribution") == "poisson":
            demands = np.random.poisson(
                max(0.1, mean), (self.n_simulations, self.forecast_days)
            )
        else:
            demands = np.random.normal(
                mean, std, (self.n_simulations, self.forecast_days)
            )
            demands = np.maximum(demands, 0)
            demands = np.rint(demands)

        # B. Calculate Cumulative Demand over time
        cumulative_demand = np.cumsum(demands, axis=1)

        # C. Check for Stockouts (True if demand >= current_stock)
        stockout_mask = cumulative_demand >= current_stock

        # --- CALCULATE METRICS ---

        # 1. Did it ever stock out?
        did_stockout = stockout_mask.any(axis=1)
        stockout_prob = did_stockout.mean()

        # 2. When did it stock out? (Find first 'True' index)
        # argmax returns 0 if no True found, so we filter by did_stockout first
        first_stockout_days = np.argmax(stockout_mask, axis=1) + 1
        valid_days = first_stockout_days[did_stockout]

        expected_days = float(valid_days.mean()) if len(valid_days) > 0 else None

        # 3. Confidence Levels (Percentiles of "Days to Stockout")
        # Interpretation: "90% of stockouts happened BY Day X"
        if len(valid_days) > 0:
            confidence_50 = float(np.percentile(valid_days, 50))  # Median Day
            confidence_75 = float(np.percentile(valid_days, 75))
            confidence_90 = float(np.percentile(valid_days, 90))  # Worst case Day
        else:
            confidence_50 = confidence_75 = confidence_90 = 0.0

        # 4. Safety Stock (Standard Formula)
        min_lead, max_lead = lead_time_range
        avg_lead_time = (min_lead + max_lead) / 2
        z_score = 1.65  # 95% service level
        safety_stock = int(z_score * np.sqrt(avg_lead_time) * std)

        return {
            "stockout_probability": float(round(stockout_prob, 4)),
            "expected_days_to_stockout": (
                float(round(expected_days, 2)) if expected_days else None
            ),
            "stockout_dates_distribution": valid_days.tolist(),
            "recommended_safety_stock": safety_stock,
            "confidence_50": confidence_50,
            "confidence_75": confidence_75,
            "confidence_90": confidence_90,
            "simulation_count": self.n_simulations,
        }

    def _empty_response(self, prob, days):
        return {
            "stockout_probability": prob,
            "expected_days_to_stockout": days,
            "stockout_dates_distribution": [],
            "recommended_safety_stock": 0,
            "confidence_50": 0.0,
            "confidence_75": 0.0,
            "confidence_90": 0.0,
            "simulation_count": 0,
        }

    def calculate_optimal_order_quantity(
        self,
        demand_stats: Dict,
        lead_time_range: Tuple[int, int],
        holding_cost_per_unit: float = 1.0,
        ordering_cost: float = 50.0,
    ) -> int:
        """Calculate EOQ (Economic Order Quantity)."""
        annual_demand = demand_stats.get("daily_demand_mean", 0) * 365
        if annual_demand == 0:
            return 0
        eoq = np.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)
        return int(np.round(eoq))
