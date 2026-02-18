import faiss
import numpy as np
import pandas as pd
import json
import os
import threading
import time
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
from core.time_utils import sqlite_connect_args

# 1. FIX TIMEOUT: Set this globally before model load
# Increases wait time from 10s to 120s to handle slow internet
os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "120"


class SmartSearchEngine:
    def __init__(self, db_path, base_dir=None):
        self.db_path = db_path

        # Determine storage paths
        if base_dir:
            self.store_dir = os.path.join(base_dir, "ml_store", "vectors")
        else:
            self.store_dir = os.path.join(
                os.path.dirname(db_path), "ml_store", "vectors"
            )

        os.makedirs(self.store_dir, exist_ok=True)

        # Paths for files
        self.paths = {
            "p_index": os.path.join(self.store_dir, "products.index"),
            "p_meta": os.path.join(self.store_dir, "products_meta.json"),
            "c_index": os.path.join(self.store_dir, "customers.index"),
            "c_meta": os.path.join(self.store_dir, "customers_meta.json"),
        }

        self.model = None
        self.product_index = None
        self.customer_index = None
        self.product_data = []
        self.customer_data = []

        # --- NEW STATE FLAGS ---
        self.is_ready = False
        self.is_loading = False
        self.load_error = None

    def initialize(self):
        """
        🚀 NON-BLOCKING INITIALIZATION
        Starts the heavy loading process in a background thread.
        This allows main.py to finish starting up immediately.
        """
        if self.is_loading or self.is_ready:
            return

        self.is_loading = True
        print(
            "⏳ AI Engine: Initialization started in background... (App is responsive)"
        )

        # Start the heavy lifting in a separate thread (Daemon = dies if app closes)
        thread = threading.Thread(target=self._heavy_load_process, daemon=True)
        thread.start()

    def _heavy_load_process(self):
        """The actual heavy lifting that used to block your app."""
        try:
            # 1. Load Model (This triggers the download)
            print("   ⬇️ Loading/Downloading Embedding Model (timeout=120s)...")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")

            # 2. Handle Indexes
            self._handle_index("product")
            self._handle_index("customer")

            # 3. Mark as Ready
            self.is_ready = True
            self.is_loading = False
            self.load_error = None
            print(
                f"✅ AI Engine: Online and ready. Products: {len(self.product_data)} | Customers: {len(self.customer_data)}"
            )

        except Exception as e:
            self.load_error = str(e)
            self.is_loading = False
            print(f"❌ AI Engine Initialization Failed: {e}")
            # Optional: Retry logic could go here

    def _handle_index(self, entity_type):
        """Generic logic to Load -> Check Updates -> Save"""
        if entity_type == "product":
            index_path = self.paths["p_index"]
            meta_path = self.paths["p_meta"]
            table_query = "SELECT v.id, v.name as v_name, p.name as p_name, v.price, v.current_stock FROM product_variant v JOIN product p ON v.product_id = p.id"

            def get_text(row):
                return f"{row['p_name']} {row['v_name']}"

        else:
            index_path = self.paths["c_index"]
            meta_path = self.paths["c_meta"]
            table_query = "SELECT id, name, mobile FROM customer"

            def get_text(row):
                return f"{row['name']} {str(row['mobile'])}"

        # 1. LOAD or CREATE
        index = None
        current_data = []
        last_max_id = 0

        if os.path.exists(index_path) and os.path.exists(meta_path):
            try:
                index = faiss.read_index(index_path)
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                    current_data = meta.get("data", [])
                    last_max_id = meta.get("max_id", 0)
            except Exception as e:
                print(f"   ⚠️ Corrupt index found, rebuilding: {e}")
                index = None

        # 2. FETCH DATA FROM DB
        engine = create_engine(
            f"sqlite:///{self.db_path}", connect_args=sqlite_connect_args()
        )
        with engine.connect() as conn:
            if index is not None:
                df = pd.read_sql(text(table_query), conn)
                new_rows = df[df["id"] > last_max_id].copy()
            else:
                df = pd.read_sql(text(table_query), conn)
                new_rows = df

        if df.empty:
            if entity_type == "product":
                self.product_index = index
                self.product_data = current_data
            else:
                self.customer_index = index
                self.customer_data = current_data
            return

        # 3. INCREMENTAL UPDATE
        if not new_rows.empty:
            new_rows["search_text"] = new_rows.apply(get_text, axis=1)
            embeddings = self.model.encode(new_rows["search_text"].tolist())

            if index is None:
                dimension = embeddings.shape[1]
                index = faiss.IndexFlatL2(dimension)

            index.add(np.array(embeddings).astype("float32"))

            new_data_list = new_rows.drop(columns=["search_text"]).to_dict("records")
            current_data.extend(new_data_list)
            new_max_id = int(df["id"].max())

            faiss.write_index(index, index_path)
            with open(meta_path, "w") as f:
                json.dump(
                    {
                        "max_id": new_max_id,
                        "count": len(current_data),
                        "data": current_data,
                    },
                    f,
                )

        if entity_type == "product":
            self.product_index = index
            self.product_data = current_data
        else:
            self.customer_index = index
            self.customer_data = current_data

    def search(self, entity_type, query, limit=3):
        # --- NEW: Check Readiness ---
        if not self.is_ready:
            if self.is_loading:
                return "⏳ **AI System is warming up...**\nPlease try again in 30 seconds. (Downloading models in background)"
            if self.load_error:
                return f"❌ **AI System Failed to Load:**\n{self.load_error}"
            return "❌ **AI System is Offline**"

        # --- Standard Logic ---
        index = self.product_index if entity_type == "product" else self.customer_index
        data = self.product_data if entity_type == "product" else self.customer_data

        if index is None or not data:
            return f"No {entity_type}s indexed yet."

        vec = self.model.encode([query])
        distances, indices = index.search(np.array(vec).astype("float32"), limit)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx < 0 or idx >= len(data):
                continue

            item = data[idx]
            dist = distances[0][i]
            confidence = max(0, 100 - (dist * 40))

            results.append({"match": item, "confidence": round(confidence, 1)})

        output = f"🔍 **Found {len(results)} matches for '{query}':**\n"
        for r in results:
            match = r["match"]
            conf = r["confidence"]
            if entity_type == "product":
                output += f"- [ID: {match['id']}] **{match['p_name']} {match['v_name']}** (Stock: {match['current_stock']}) | Confidence: {conf}%\n"
            else:
                output += f"- [ID: {match['id']}] **{match['name']}** (Mobile: {match['mobile']}) | Confidence: {conf}%\n"
        return output
