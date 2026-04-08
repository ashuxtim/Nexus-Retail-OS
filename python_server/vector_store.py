import os
import sys
import shutil
import threading
import time
from sentence_transformers import SentenceTransformer
from sqlalchemy import create_engine, text
import chromadb
from chromadb.config import Settings
from core.time_utils import sqlite_connect_args

os.environ["HF_HUB_DOWNLOAD_TIMEOUT"] = "120"


class SmartSearchEngine:
    def __init__(self, db_path, base_dir=None):
        self.db_path = db_path

        # ChromaDB storage path — replaces ml_store/vectors/
        if base_dir:
            self.chroma_dir = os.path.join(base_dir, "ml_store", "chroma")
        else:
            self.chroma_dir = os.path.join(
                os.path.dirname(db_path), "ml_store", "chroma"
            )
        os.makedirs(self.chroma_dir, exist_ok=True)

        self.model = None
        self.client = None

        # Three collections — products, customers, suppliers
        self.collections = {
            "product": None,
            "customer": None,
            "supplier": None,
        }

        # State flags
        self.is_ready = False
        self.is_loading = False
        self.load_error = None

        # Threading lock for polling loop
        self._sync_lock = threading.Lock()

        # Lazy-initialized DB engine (shared across sync calls)
        self._db_engine = None

    def initialize(self):
        """Non-blocking startup"""
        if self.is_loading or self.is_ready:
            return
        self.is_loading = True
        print("⏳ AI Engine: ChromaDB initialization started in background...")
        thread = threading.Thread(target=self._heavy_load_process, daemon=True)
        thread.start()

    def _get_db_engine(self):
        if self._db_engine is None:
            self._db_engine = create_engine(
                f"sqlite:///{self.db_path}", connect_args=sqlite_connect_args()
            )
        return self._db_engine

    def _heavy_load_process(self):
        try:
            # Clean up old FAISS files
            old_vectors_dir = os.path.join(os.path.dirname(self.chroma_dir), "vectors")
            if os.path.exists(old_vectors_dir):
                shutil.rmtree(old_vectors_dir)
                print("   🗑️ Cleaned up old FAISS index files.")

            # 1. Load embedding model
            print("   ⬇️ Loading embedding model...")
            if hasattr(sys, "_MEIPASS"):
                model_path = os.path.join(
                    sys._MEIPASS, "sentence_transformers_models", "all-MiniLM-L6-v2"
                )
            else:
                model_path = "all-MiniLM-L6-v2"
            self.model = SentenceTransformer(model_path)

            # 2. Initialize ChromaDB persistent client
            self.client = chromadb.PersistentClient(
                path=self.chroma_dir, settings=Settings(anonymized_telemetry=False)
            )

            # 3. Get or create all three collections
            for name in self.collections:
                self.collections[name] = self.client.get_or_create_collection(
                    name=name,
                    metadata={
                        "hnsw:space": "cosine"
                    },  # cosine similarity — better than L2
                )

            # 4. Do initial full sync for all three entities
            self._sync_entity("product")
            self._sync_entity("customer")
            self._sync_entity("supplier")

            # 5. Start background polling loop (every 5 minutes)
            poll_thread = threading.Thread(target=self._polling_loop, daemon=True)
            poll_thread.start()

            self.is_ready = True
            self.is_loading = False
            self.load_error = None

            counts = {k: self.collections[k].count() for k in self.collections}
            print(
                f"✅ ChromaDB ready. Products: {counts['product']} | "
                f"Customers: {counts['customer']} | Suppliers: {counts['supplier']}"
            )

        except Exception as e:
            self.load_error = str(e)
            self.is_loading = False
            print(f"❌ ChromaDB initialization failed: {e}")

    def _polling_loop(self):
        """Runs every 5 minutes — checks for new, updated, or deleted records."""
        while True:
            time.sleep(300)  # 5 minutes
            try:
                self._sync_entity("product")
                self._sync_entity("customer")
                self._sync_entity("supplier")
                print("🔄 ChromaDB: Background sync complete.")
            except Exception as e:
                print(f"⚠️ ChromaDB poll sync error: {e}")

    def _sync_entity(self, entity_type):
        """
        Full reconciliation sync — handles NEW, UPDATED, and DELETED records.
        """
        with self._sync_lock:
            collection = self.collections[entity_type]
            db_engine = self._get_db_engine()

            # --- FETCH FROM DATABASE ---
            with db_engine.connect() as conn:
                if entity_type == "product":
                    rows = conn.execute(
                        text("""SELECT v.id, v.name as v_name, p.name as p_name, 
                                  p.category, v.price, v.current_stock
                           FROM product_variant v 
                           JOIN product p ON v.product_id = p.id
                           WHERE v.current_stock >= 0""")
                    ).fetchall()

                    def make_doc(row):
                        # category included for category-based queries like "cold drinks"
                        return f"{row.p_name} {row.v_name} {row.category or ''}"

                    def make_meta(row):
                        return {
                            "variant_id": row.id,
                            "product_name": row.p_name,
                            "variant_name": row.v_name,
                            "category": row.category or "",
                            "price": float(row.price or 0),
                            "current_stock": float(row.current_stock or 0),
                            "entity_type": "product",
                        }

                elif entity_type == "customer":
                    rows = conn.execute(
                        text("SELECT id, name, mobile, address FROM customer")
                    ).fetchall()

                    def make_doc(row):
                        address = row.address or ""
                        return f"{row.name} {address}"

                    def make_meta(row):
                        return {
                            "customer_id": row.id,
                            "name": row.name,
                            "mobile": str(row.mobile or ""),
                            "entity_type": "customer",
                        }

                elif entity_type == "supplier":
                    rows = conn.execute(
                        text("SELECT id, name, mobile FROM supplier")
                    ).fetchall()

                    def make_doc(row):
                        return f"{row.name}"

                    def make_meta(row):
                        return {
                            "supplier_id": row.id,
                            "name": row.name,
                            "mobile": str(row.mobile or ""),
                            "entity_type": "supplier",
                        }

            if not rows:
                return

            # --- RECONCILIATION ---
            db_ids = {str(row.id) for row in rows}

            # Get all IDs currently in ChromaDB for this collection
            existing = collection.get(include=[])  # Only fetch IDs, no embeddings
            chroma_ids = set(existing["ids"]) if existing["ids"] else set()

            # DELETE zombie records (in ChromaDB but deleted from SQLite)
            to_delete = chroma_ids - db_ids
            if to_delete:
                collection.delete(ids=list(to_delete))
                print(
                    f"   🗑️ ChromaDB [{entity_type}]: Removed {len(to_delete)} zombie records."
                )

            # ADD new records (in SQLite but not in ChromaDB)
            to_add_ids = db_ids - chroma_ids
            if to_add_ids:
                new_rows = [row for row in rows if str(row.id) in to_add_ids]
                docs = [make_doc(row) for row in new_rows]
                metas = [make_meta(row) for row in new_rows]
                ids = [str(row.id) for row in new_rows]

                # Encode in batches to avoid memory spikes on large catalogs
                embeddings = self.model.encode(
                    docs, batch_size=64, show_progress_bar=False
                )

                # ChromaDB has max batch size limit of 5461 elements.
                # Process strictly in smaller chunks to prevent insertion failure.
                BATCH_LIMIT = 5000
                total_items = len(new_rows)

                # We need embeddings as list for ChromaDB
                embeddings_list = embeddings.tolist()

                for i in range(0, total_items, BATCH_LIMIT):
                    batch_ids = ids[i : i + BATCH_LIMIT]
                    batch_embeddings = embeddings_list[i : i + BATCH_LIMIT]
                    batch_documents = docs[i : i + BATCH_LIMIT]
                    batch_metadatas = metas[i : i + BATCH_LIMIT]

                    collection.add(
                        ids=batch_ids,
                        embeddings=batch_embeddings,
                        documents=batch_documents,
                        metadatas=batch_metadatas,
                    )
                print(
                    f"   ✅ ChromaDB [{entity_type}]: Added {len(to_add_ids)} new records."
                )

    def search(self, entity_type, query, limit=5):
        """
        Main search method
        Returns STRUCTURED DICT (not a display string) so tools can use IDs programmatically.
        """
        if not self.is_ready:
            if self.is_loading:
                return {
                    "error": "warming_up",
                    "message": "⏳ AI System is warming up... Please try in 30 seconds.",
                }
            if self.load_error:
                return {
                    "error": "load_failed",
                    "message": f"❌ AI System failed: {self.load_error}",
                }
            return {"error": "offline", "message": "❌ AI System is offline."}

        collection = self.collections.get(entity_type)
        if collection is None or collection.count() == 0:
            return {"error": "empty", "message": f"No {entity_type}s indexed yet."}

        fetch_limit = min(limit * 10, collection.count())
        results = collection.query(
            query_texts=[query],
            n_results=fetch_limit,
            include=["metadatas", "distances", "documents"],
        )

        matches = []

        if not results["metadatas"] or not results["metadatas"][0]:
            return {"error": "empty", "message": f"No {entity_type} matches found."}

        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for meta, dist in zip(metadatas, distances):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity percentage
            similarity = round((1 - dist) * 100, 1)
            matches.append({**meta, "similarity": similarity})

        # Deduplicate by brand (first word of product_name), max 3 per brand
        if entity_type == "product":
            seen_brands = {}
            deduped = []
            for m in matches:
                # Use split to carefully get first word, handle empty strings safely
                p_name = m.get("product_name", "")
                parts = p_name.split()
                brand = parts[0] if parts else ""

                count = seen_brands.get(brand, 0)
                if count < 5:
                    deduped.append(m)
                    seen_brands[brand] = count + 1
            matches = deduped

        return {
            "entity_type": entity_type,
            "query": query,
            "count": len(matches),
            "matches": matches,
        }

    def search_display(self, entity_type, query, limit=5):
        """
        Wrapper that returns a formatted display string.
        Used only for the legacy chatbot text response where IDs aren't needed downstream.
        """
        result = self.search(entity_type, query, limit)

        if "error" in result:
            return result["message"]

        output = f"🔍 **Found {result['count']} matches for '{query}':**\n"
        for m in result["matches"]:
            sim = m["similarity"]
            if entity_type == "product":
                output += (
                    f"- [ID: {m['variant_id']}] **{m['product_name']} {m['variant_name']}** "
                    f"[{m['category']}] (Stock: {m['current_stock']}) | Match: {sim}%\n"
                )
            elif entity_type == "customer":
                output += f"- [ID: {m['customer_id']}] **{m['name']}** (Mobile: {m['mobile']}) | Match: {sim}%\n"
            elif entity_type == "supplier":
                output += f"- [ID: {m['supplier_id']}] **{m['name']}** (Mobile: {m['mobile']}) | Match: {sim}%\n"
        return output
