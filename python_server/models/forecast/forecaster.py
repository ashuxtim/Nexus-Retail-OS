import os
import json
import pandas as pd
import numpy as np
from datetime import datetime
from core.time_utils import now as tz_now
from sqlalchemy import text
from typing import Dict, Tuple, Optional

# Time Series Library
from prophet import Prophet


class RevenueForecaster:
    """
    Dedicated forecasting engine using Facebook Prophet.

    Responsibilities:
    1. Aggregating daily revenue history
    2. Training time-series models (Prophet)
    3. Forecasting future revenue (30 days)
    4. Caching results to 'ml_store'
    """

    def __init__(self, engine, base_dir=None):
        self.engine = engine

        # --- 1. SETUP PATHS ---
        if base_dir:
            self.base_dir = base_dir
        else:
            appdata = os.getenv("APPDATA") or os.path.expanduser("~")
            self.base_dir = os.path.join(appdata, "NexusRetailOS")

        # Safe Cache Directory
        self.cache_dir = os.path.join(self.base_dir, "ml_store", "forecast")
        os.makedirs(self.cache_dir, exist_ok=True)

        print(f"📈 RevenueForecaster initialized")
        print(f"   Cache Dir: {self.cache_dir}")

    def _get_cache_path(self) -> str:
        # We cache by date so it refreshes daily
        date_str = tz_now().strftime("%Y-%m-%d")
        return os.path.join(self.cache_dir, f"revenue_forecast_{date_str}.json")

    def get_cached_forecast(self) -> Optional[Dict]:
        """Retrieve today's cached forecast."""
        path = self._get_cache_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                return data
            except Exception as e:
                print(f"⚠️ Failed to load forecast cache: {e}")
        return None

    def _save_to_cache(self, forecast_data: Dict):
        """Save forecast results."""
        path = self._get_cache_path()
        try:
            # Clean up old cache files first
            for f in os.listdir(self.cache_dir):
                if f.startswith("revenue_forecast_") and f != os.path.basename(path):
                    try:
                        os.remove(os.path.join(self.cache_dir, f))
                    except:
                        pass

            with open(path, "w") as f:
                json.dump(forecast_data, f, indent=2)
            print(f"✅ Saved revenue forecast to {path}")
        except Exception as e:
            print(f"❌ Failed to save forecast cache: {e}")

    def generate_forecast(self, days_ahead=30) -> Dict:
        """
        Main pipeline: Check Cache -> Fetch Data -> Train Prophet -> Predict -> Save.
        """
        # 1. Check Cache
        cached = self.get_cached_forecast()
        if cached:
            return cached

        print("📈 Starting Revenue Forecast...")

        # 2. Fetch Historical Data
        df = self._fetch_daily_revenue()

        if df.empty or len(df) < 14:
            print(
                "   ⚠️ Not enough data for Prophet (need > 14 days). Returning empty."
            )
            return self._empty_response()

        # 3. Prepare for Prophet (ds, y)
        df = df.rename(columns={"date": "ds", "revenue": "y"})

        # 4. Train Model & Predict
        try:
            forecast_df, metrics, model_components = self._run_prophet(df, days_ahead)

            # ✅ Convert Timestamps to Strings before saving (Fixes JSON Error)
            history_records = (
                df[["ds", "y"]].rename(columns={"ds": "date", "y": "sales"}).copy()
            )
            history_records["date"] = history_records["date"].dt.strftime("%Y-%m-%d")

            forecast_records = forecast_df.copy()
            # forecast_df 'date' is already string from _run_prophet

            # 5. Format Results
            results = {
                "history": history_records.to_dict("records"),
                "forecast": forecast_records.to_dict("records"),
                "metrics": metrics,
                "trend": self._calculate_trend(forecast_df),
                "model_metadata": {
                    "algorithm": "Prophet (Facebook)",
                    "training_period_days": len(df),
                    "generated_at": tz_now().isoformat(),
                    # Add seasonality stats for expert view
                    "seasonality_strength": model_components.get(
                        "seasonality_strength", 0
                    ),
                    "trend_strength": model_components.get("trend_strength", 0),
                },
            }

            # 6. Save to Cache
            self._save_to_cache(results)
            return results

        except Exception as e:
            print(f"❌ Prophet Error: {e}")
            import traceback

            traceback.print_exc()
            return self._empty_response()

    def _fetch_daily_revenue(self) -> pd.DataFrame:
        """Fetch daily revenue aggregation."""
        query = text("""
            SELECT 
                DATE(s.sale_date) as date,
                SUM(i.quantity * i.price_at_sale) as revenue
            FROM credit_sale s
            JOIN credit_sale_item i ON s.id = i.sale_id
            WHERE s.sale_date >= date('now', '-730 days')
            GROUP BY DATE(s.sale_date)
            ORDER BY date ASC
        """)

        with self.engine.connect() as conn:
            df = pd.read_sql(query, conn)

        # Fill missing dates with 0
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            idx = pd.date_range(df["date"].min(), df["date"].max())
            df = df.set_index("date").reindex(idx, fill_value=0).reset_index()
            df = df.rename(columns={"index": "date"})

        return df

    def _run_prophet(
        self, df: pd.DataFrame, days_ahead: int
    ) -> Tuple[pd.DataFrame, Dict, Dict]:
        """Run Prophet training and prediction with FULL metrics."""
        # Detect simple seasonality
        model = Prophet(
            yearly_seasonality=len(df) > 365,
            weekly_seasonality=True,
            daily_seasonality=False,
            interval_width=0.95,  # 95% Confidence Interval
            changepoint_prior_scale=0.05,
        )

        # Add Monthly Seasonality
        model.add_seasonality(name="monthly", period=30.5, fourier_order=5)

        model.fit(df)

        # Future DataFrame
        future = model.make_future_dataframe(periods=days_ahead)
        forecast = model.predict(future)

        # --- 1. EXTRACT FORECAST ---
        future_forecast = forecast.tail(days_ahead).copy()

        result_df = pd.DataFrame(
            {
                "date": future_forecast["ds"].dt.strftime("%Y-%m-%d"),
                "predicted_sales": future_forecast["yhat"].round(2),
                "lower_bound_95": future_forecast["yhat_lower"].round(2),
                "upper_bound_95": future_forecast["yhat_upper"].round(2),
            }
        )

        # --- 2. CALCULATE ADVANCED METRICS ---
        # Get in-sample predictions (align with history)
        historical_pred = forecast.iloc[:-days_ahead]
        y_true = df["y"].values
        y_pred = historical_pred["yhat"].values

        # Calculate Residuals
        residuals = y_true - y_pred

        # A. Basic Accuracy
        mask = y_true > 0
        if np.any(mask):
            mape = np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask]))
        else:
            mape = 0.0

        mae = np.mean(np.abs(residuals))

        # B. Advanced Stats (RMSE, R2, AIC)
        mse = np.mean(residuals**2)
        rmse = np.sqrt(mse)

        # R-Squared
        ss_res = np.sum(residuals**2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

        # AIC/BIC (Model Complexity)
        n = len(y_true)
        k = 3  # Approx params (trend + 2 seasonalities)
        if mse > 0:
            aic = n * np.log(mse) + 2 * k
            bic = n * np.log(mse) + k * np.log(n)
        else:
            aic, bic = 0, 0

        metrics = {
            "mape": round(mape, 4),
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "r_squared": round(r_squared, 3),
            "aic": round(aic, 1),
            "bic": round(bic, 1),
        }

        # --- 3. CALCULATE SEASONALITY STRENGTH ---
        # Variance of components / Variance of total
        components = model.predict(df)

        seasonal_cols = [
            c for c in ["weekly", "yearly", "monthly"] if c in components.columns
        ]
        if seasonal_cols:
            seasonal_var = components[seasonal_cols].sum(axis=1).var()
        else:
            seasonal_var = 0

        total_var = df["y"].var()
        trend_var = components["trend"].var()

        model_components = {
            "seasonality_strength": (
                round(seasonal_var / total_var, 3) if total_var > 0 else 0
            ),
            "trend_strength": round(trend_var / total_var, 3) if total_var > 0 else 0,
        }

        return result_df, metrics, model_components

    def _calculate_trend(self, forecast_df: pd.DataFrame) -> str:
        """Simple trend direction."""
        if forecast_df.empty:
            return "steady"

        start = forecast_df.iloc[0]["predicted_sales"]
        end = forecast_df.iloc[-1]["predicted_sales"]

        if end > start * 1.05:
            return "up"
        if end < start * 0.95:
            return "down"
        return "steady"

    def _empty_response(self):
        return {
            "history": [],
            "forecast": [],
            "metrics": {"mape": 0, "r_squared": 0, "aic": 0},
            "trend": "unknown",
            "model_metadata": {},
        }
