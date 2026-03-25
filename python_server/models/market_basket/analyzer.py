import os
import sys
import json
import threading
import pandas as pd
import numpy as np
from datetime import datetime
from core.time_utils import now as tz_now
from sqlalchemy import text
from typing import List, Dict, Optional

# Machine Learning Libraries
from mlxtend.frequent_patterns import fpgrowth, association_rules
from mlxtend.preprocessing import TransactionEncoder


class MarketBasketAnalyzer:
    """
    Dedicated analyzer for Market Basket Analysis (Association Rules).

    Responsibilities:
    1. Fetch transaction history
    2. Run FP-Growth algorithm
    3. Generate and filter association rules
    4. Cache results to 'ml_store' for instant dashboard access
    """

    _global_analysis_lock = threading.Lock()

    def __init__(self, engine, base_dir=None):
        self.engine = engine

        # --- 1. SETUP PATHS (Standardized with Churn/Stockout) ---
        if base_dir:
            self.base_dir = base_dir
        else:
            if sys.platform == "win32":
                self.base_dir = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
            else:
                self.base_dir = os.path.join(
                    os.path.expanduser("~"), ".config", "NexusRetailOS"
                )

        # Safe Cache Directory
        self.cache_dir = os.path.join(self.base_dir, "ml_store", "market_basket")
        os.makedirs(self.cache_dir, exist_ok=True)

        print(f"🛒 MarketBasketAnalyzer initialized")
        print(f"   Cache Dir: {self.cache_dir}")

    def _get_cache_path(self) -> str:
        return os.path.join(self.cache_dir, "rules.json")

    def get_cached_rules(self) -> Optional[List[Dict]]:
        """Retrieve cached rules for the dashboard."""
        path = self._get_cache_path()
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    data = json.load(f)
                # Check if cache is fresh (e.g., < 24 hours)
                # For now, we just return it. Logic to invalidate can be added later.
                return data.get("rules", [])
            except Exception as e:
                print(f"⚠️ Failed to load MBA cache: {e}")
        return None

    def _save_to_cache(self, rules: List[Dict], metadata: Dict):
        """Save processed rules to JSON."""
        path = self._get_cache_path()
        try:
            payload = {
                "timestamp": tz_now().isoformat(),
                "metadata": metadata,
                "rules": rules,
            }
            with open(path, "w") as f:
                json.dump(payload, f, indent=2)
            print(f"✅ Saved {len(rules)} rules to {path}")
        except Exception as e:
            print(f"❌ Failed to save MBA cache: {e}")

    def generate_rules(
        self, min_support=0.001, min_confidence=0.1, min_lift=1.5
    ) -> List[Dict]:
        """
        Main pipeline: Fetch Data -> FP-Growth -> Rules -> Cache.
        """
        # Lock guard — if a run is already in progress, return cache or empty
        # instead of spawning a second memory-heavy FP-Growth process
        if MarketBasketAnalyzer._global_analysis_lock.locked():
            print("   ⏳ FP-Growth already running globally — returning current cache.")
            return self.get_cached_rules() or []

        with MarketBasketAnalyzer._global_analysis_lock:
            print("🛒 Starting Market Basket Analysis...")

            # 1. Fetch Transactions (Last 90 days to keep it relevant)
            transactions = self._fetch_transactions(days=90)

            if not transactions:
                print("   ⚠️ No transactions found.")
                return []

            print(f"   Analyzing {len(transactions)} transactions...")

            # 2. Encode Data (One-Hot)
            te = TransactionEncoder()
            te_ary = te.fit(transactions).transform(transactions, sparse=True)
            sparse_df = pd.DataFrame.sparse.from_spmatrix(te_ary, columns=te.columns_)

            # 3. Run FP-Growth
            # use_colnames=True so we get item names, not indices
            frequent_itemsets = fpgrowth(
                sparse_df, min_support=min_support, use_colnames=True, max_len=3
            )

            if frequent_itemsets.empty:
                print("   ⚠️ No frequent itemsets found (try lowering min_support).")
                self._save_to_cache(
                    [],
                    {
                        "algorithm": "FP-Growth",
                        "total_transactions": len(transactions),
                        "min_support": min_support,
                        "min_confidence": min_confidence,
                    },
                )
                return []

            # 4. Generate Association Rules
            rules_df = association_rules(
                frequent_itemsets, metric="confidence", min_threshold=min_confidence
            )

            # Filter by Lift
            rules_df = rules_df[rules_df["lift"] >= min_lift]

            # Sort by Lift (Strongest associations first)
            rules_df = rules_df.sort_values(by="lift", ascending=False)

            print(f"   Found {len(rules_df)} association rules.")

            # 5. Format for Frontend/JSON
            results = []
            for idx, row in rules_df.head(50).iterrows():  # Top 50 only
                # Convert frozensets to clean lists
                antecedents = list(row["antecedents"])
                consequents = list(row["consequents"])

                # Create clean string description: "Bread, Milk" instead of "['Bread', 'Milk']"
                ant_str = ", ".join(str(x) for x in antecedents)
                cons_str = ", ".join(str(x) for x in consequents)

                results.append(
                    {
                        "antecedent": antecedents,
                        "consequent": consequents,
                        "support": round(row["support"], 4),
                        "confidence": round(row["confidence"], 4),
                        "lift": round(row["lift"], 4),
                        "conviction": (
                            round(row["conviction"], 4)
                            if not np.isinf(row["conviction"])
                            else 0.0
                        ),
                        "leverage": round(row["leverage"], 4),
                        "zhangs_metric": (
                            round(row["zhangs_metric"], 4)
                            if "zhangs_metric" in row
                            else None
                        ),
                        # Fixed Description String
                        "description": f"If buy {ant_str}, likely to buy {cons_str}",
                    }
                )

            # 6. Save to Cache
            metadata = {
                "algorithm": "FP-Growth",
                "total_transactions": len(transactions),
                "min_support": min_support,
                "min_confidence": min_confidence,
            }
            self._save_to_cache(results, metadata)

            return results

    def _fetch_transactions(self, days=90) -> List[List[str]]:
        """
        Fetch sales data and group by Invoice/Sale ID.
        Returns list of lists: [['Bread', 'Milk'], ['Diapers', 'Beer'], ...]
        """
        query = text("""
            SELECT 
                s.id as sale_id,
                p.name as product_name
            FROM credit_sale s
            JOIN credit_sale_item i ON s.id = i.sale_id
            JOIN product_variant v ON i.variant_id = v.id
            JOIN product p ON v.product_id = p.id
            WHERE s.id IN (
                SELECT id FROM credit_sale
                WHERE sale_date >= date('now', :days_param)
                ORDER BY id DESC
                LIMIT 10000
            )
            ORDER BY s.id
        """)

        try:
            with self.engine.connect() as conn:
                # SQLite param needs string formatting usually, but SQLAlchemy text handles :param
                # passing '-90 days' string to date function
                result = conn.execute(query, {"days_param": f"-{days} days"}).fetchall()

            # Group by sale_id
            transactions_map = {}
            for row in result:
                sale_id = row[0]
                product = row[1]
                if sale_id not in transactions_map:
                    transactions_map[sale_id] = []
                transactions_map[sale_id].append(product)

            return list(transactions_map.values())

        except Exception as e:
            print(f"❌ DB Error fetching transactions: {e}")
            return []
