# Nexus Retail OS — Vector Store & ML Pipeline Rebuild Plan
**Status:** Analysis Complete | Ready for Implementation  
**Scope:** ChromaDB migration, 3-entity vector store, full ML pipeline wiring, UI fuzzy search, agent tool overhaul  
**Rule:** Complete each phase fully, test all checkpoints, only then move to the next phase.

---

## What This Plan Fixes (Root Cause Summary)

Before touching any code, understand what is actually broken and why:

| Problem | Root Cause | Impact |
|---|---|---|
| New products invisible to AI | FAISS has no live sync, only runs at startup | AI recommends stale/wrong items |
| Deleted products still returned | `max_id` tracker only appends, never removes | Zombie records in search results |
| Monte Carlo never used by chatbot | No tool connects search → stockout predictor | "When will chips finish" answered with naive SQL math |
| XGBoost never used by chatbot | No tool connects product buyers → churn scores | "Are chips customers at risk?" unanswerable |
| FP-Growth never used by chatbot | No tool connects product → association rules | "What sells with Maggi?" ignores your ML entirely |
| Suppliers not vectorized | Only products and customers indexed | "Who supplies our chips?" misses semantic queries |
| Phone numbers in embeddings | Customer `get_text` concatenates name + mobile | Semantic search degraded by random numbers |
| Search tool returns display string | `SEARCH_ENGINE.search()` returns formatted text | IDs cannot be programmatically passed to ML models |
| UI has no smart search | No `/api/search` endpoint exists | POS search bar gets zero benefit from any of this |
| ChromaDB not installed or used | FAISS only, no delete support | Zombie bug is architecturally unsolvable in FAISS |

---

## Architecture After This Plan

```
Owner Query: "how many types of chips and when will stock finish"
         │
         ▼
  [Agent Router] — LangGraph ReAct Agent
         │
         ▼
  [resolve_entity_tool("chips", "product")]
         │
         ▼
  [ChromaDB: products collection]
         │  returns: [{variant_id: 12, name: "Lays Classic"}, {variant_id: 15, name: "Lays Masala"}, ...]
         ▼
  [get_stockout_prediction_tool(variant_ids=[12, 15, ...])]
         │
         ▼
  [StockoutPredictor — Monte Carlo cached results]
         │  returns: [{name: "Lays Classic", days_left: 4, risk: "critical"}, ...]
         ▼
  Agent formats final answer with real ML data
```

```
UI Search Bar: owner types "lays masa"
         │
         ▼
  [GET /api/search?q=lays+masa&type=product]
         │
         ▼
  [SQL: LIKE + RapidFuzz typo tolerance — live DB, sub-10ms]
         │
         ▼
  Returns product list instantly — no model, no FAISS, no ChromaDB
```

---

## Phase 1 — ChromaDB Migration + Fix All Vector Store Bugs

**What this phase does:** Replaces FAISS entirely with ChromaDB. Adds suppliers as a third collection. Fixes the stale data bug with a live polling loop. Fixes zombie records with proper ID reconciliation. Removes phone numbers from customer embeddings. This phase is purely about the vector store — no agent changes yet.

**Why this must be Phase 1:** Every phase after this depends on a working, trustworthy vector store. If the data is stale or zombie-filled, all the ML wiring in Phase 2 produces wrong answers.

---

### Step 1.1 — Install ChromaDB

Add to `requirements.txt`:
```
chromadb==0.5.3
```

Remove from `requirements.txt`:
```
faiss-cpu==1.13.2
```

> **Note:** `sentence-transformers` stays. You still need it to generate embeddings before storing in ChromaDB. ChromaDB can use its own embedding functions but using your existing `all-MiniLM-L6-v2` model keeps consistency with what was already indexed and avoids re-downloading a different model.

---

### Step 1.2 — Rewrite `vector_store.py` from Scratch

Replace the entire file. The new class is called `SmartSearchEngine` (keep the same class name so `tools.py` and `state.py` don't need changes yet).

**New file structure:**

```python
# vector_store.py

import os
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

        # State flags (keep same interface as before)
        self.is_ready = False
        self.is_loading = False
        self.load_error = None

    def initialize(self):
        """Non-blocking startup — same interface as before."""
        if self.is_loading or self.is_ready:
            return
        self.is_loading = True
        print("⏳ AI Engine: ChromaDB initialization started in background...")
        thread = threading.Thread(target=self._heavy_load_process, daemon=True)
        thread.start()

    def _get_db_engine(self):
        return create_engine(
            f"sqlite:///{self.db_path}", connect_args=sqlite_connect_args()
        )

    def _heavy_load_process(self):
        try:
            # 1. Load embedding model
            print("   ⬇️ Loading embedding model...")
            self.model = SentenceTransformer("all-MiniLM-L6-v2")

            # 2. Initialize ChromaDB persistent client
            self.client = chromadb.PersistentClient(
                path=self.chroma_dir,
                settings=Settings(anonymized_telemetry=False)
            )

            # 3. Get or create all three collections
            for name in self.collections:
                self.collections[name] = self.client.get_or_create_collection(
                    name=name,
                    metadata={"hnsw:space": "cosine"}  # cosine similarity — better than L2
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
            print(f"✅ ChromaDB ready. Products: {counts['product']} | "
                  f"Customers: {counts['customer']} | Suppliers: {counts['supplier']}")

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
        This is the core fix for both the stale data bug and zombie record bug.
        
        Strategy:
        1. Fetch all current IDs from SQLite (the source of truth)
        2. Fetch all IDs currently in ChromaDB collection
        3. Delete IDs that are in ChromaDB but not in SQLite (zombie records)
        4. Add IDs that are in SQLite but not in ChromaDB (new records)
        """
        collection = self.collections[entity_type]
        db_engine = self._get_db_engine()

        # --- FETCH FROM DATABASE ---
        with db_engine.connect() as conn:
            if entity_type == "product":
                rows = conn.execute(text(
                    """SELECT v.id, v.name as v_name, p.name as p_name, 
                              p.category, v.price, v.current_stock
                       FROM product_variant v 
                       JOIN product p ON v.product_id = p.id
                       WHERE v.current_stock >= 0"""
                )).fetchall()
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
                        "entity_type": "product"
                    }

            elif entity_type == "customer":
                rows = conn.execute(text(
                    "SELECT id, name, mobile, address FROM customer"
                )).fetchall()
                def make_doc(row):
                    # CRITICAL FIX: mobile NOT included in embedding text
                    # Mobile is stored as metadata only for exact lookup
                    return f"{row.name}"
                def make_meta(row):
                    return {
                        "customer_id": row.id,
                        "name": row.name,
                        "mobile": str(row.mobile or ""),
                        "entity_type": "customer"
                    }

            elif entity_type == "supplier":
                rows = conn.execute(text(
                    "SELECT id, name, mobile FROM supplier"
                )).fetchall()
                def make_doc(row):
                    return f"{row.name}"
                def make_meta(row):
                    return {
                        "supplier_id": row.id,
                        "name": row.name,
                        "mobile": str(row.mobile or ""),
                        "entity_type": "supplier"
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
            print(f"   🗑️ ChromaDB [{entity_type}]: Removed {len(to_delete)} zombie records.")

        # ADD new records (in SQLite but not in ChromaDB)
        to_add_ids = db_ids - chroma_ids
        if to_add_ids:
            new_rows = [row for row in rows if str(row.id) in to_add_ids]
            docs = [make_doc(row) for row in new_rows]
            metas = [make_meta(row) for row in new_rows]
            ids = [str(row.id) for row in new_rows]
            
            # Encode in batches to avoid memory spikes on large catalogs
            embeddings = self.model.encode(docs, batch_size=64, show_progress_bar=False)
            
            collection.add(
                ids=ids,
                embeddings=embeddings.tolist(),
                documents=docs,
                metadatas=metas
            )
            print(f"   ✅ ChromaDB [{entity_type}]: Added {len(to_add_ids)} new records.")

    def search(self, entity_type, query, limit=5):
        """
        Main search method — same signature as before for backward compatibility.
        Returns STRUCTURED DICT (not a display string) so tools can use IDs programmatically.
        """
        if not self.is_ready:
            if self.is_loading:
                return {"error": "warming_up", "message": "⏳ AI System is warming up... Please try in 30 seconds."}
            if self.load_error:
                return {"error": "load_failed", "message": f"❌ AI System failed: {self.load_error}"}
            return {"error": "offline", "message": "❌ AI System is offline."}

        collection = self.collections.get(entity_type)
        if collection is None or collection.count() == 0:
            return {"error": "empty", "message": f"No {entity_type}s indexed yet."}

        results = collection.query(
            query_texts=[query],
            n_results=min(limit, collection.count()),
            include=["metadatas", "distances", "documents"]
        )

        matches = []
        metadatas = results["metadatas"][0]
        distances = results["distances"][0]

        for meta, dist in zip(metadatas, distances):
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity percentage
            similarity = round((1 - dist) * 100, 1)
            matches.append({
                **meta,
                "similarity": similarity
            })

        return {
            "entity_type": entity_type,
            "query": query,
            "count": len(matches),
            "matches": matches
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
                output += (f"- [ID: {m['variant_id']}] **{m['product_name']} {m['variant_name']}** "
                           f"[{m['category']}] (Stock: {m['current_stock']}) | Match: {sim}%\n")
            elif entity_type == "customer":
                output += f"- [ID: {m['customer_id']}] **{m['name']}** (Mobile: {m['mobile']}) | Match: {sim}%\n"
            elif entity_type == "supplier":
                output += f"- [ID: {m['supplier_id']}] **{m['name']}** (Mobile: {m['mobile']}) | Match: {sim}%\n"
        return output
```

---

### Step 1.3 — Delete Old FAISS Files

On first run with the new code, the old FAISS files in `ml_store/vectors/` are no longer used. Add a one-time migration cleanup in the `_heavy_load_process`:

```python
# Add at the start of _heavy_load_process before ChromaDB init
import shutil
old_vectors_dir = os.path.join(os.path.dirname(self.chroma_dir), "vectors")
if os.path.exists(old_vectors_dir):
    shutil.rmtree(old_vectors_dir)
    print("   🗑️ Cleaned up old FAISS index files.")
```

---

### Phase 1 Checkpoints — Test Before Moving to Phase 2

- [ ] Server starts without ImportError (faiss removed, chromadb installed)
- [ ] ChromaDB folder appears at `ml_store/chroma/` on first run
- [ ] Console shows: `✅ ChromaDB ready. Products: X | Customers: Y | Suppliers: Z`
- [ ] Add a new product in the app → wait 5 minutes → ask chatbot "do we have [new product]?" → it finds it (no restart needed)
- [ ] Delete a product in the app → wait 5 minutes → ask chatbot about it → it says not found
- [ ] Customer search does NOT embed mobile number (check `make_doc` for customer — only name)
- [ ] `search()` method returns a dict, not a string
- [ ] `search_display()` method returns the same formatted string as before

---

## Phase 2 — Wire All ML Models to the Chatbot Agent

**What this phase does:** Creates new compound tools that connect ChromaDB entity resolution to your actual ML model outputs. This is the phase that makes the chatbot genuinely intelligent. Each new tool follows the same pattern: resolve entity name → get IDs → query the right ML model → return enriched answer.

**Why Phase 2 comes after Phase 1:** The new tools depend on `search()` returning structured dicts with IDs. If Phase 1 isn't done, this phase cannot work.

---

### Step 2.1 — Add New Tool: `get_product_stockout_tool`

**Answers:** "how many types of chips and when will stock finish", "which cold drinks are running low", "what snacks will run out this week"

Add to `tools.py`:

```python
@tool
def get_product_stockout_tool(product_name: str) -> str:
    """
    Finds all variants matching a product name/category and returns Monte Carlo
    stockout predictions for each. Use this when the user asks about when a 
    product will run out, stock finishing, or restocking urgency.
    
    Examples: "when will chips finish", "cold drinks running low", 
              "which biscuits need restock", "dairy stock status"
    """
    if not SEARCH_ENGINE or not SEARCH_ENGINE.is_ready:
        return "⏳ Search engine warming up. Try again in 30 seconds."

    # Step 1: Resolve entity name → variant IDs via ChromaDB
    search_result = SEARCH_ENGINE.search("product", product_name, limit=10)
    if "error" in search_result:
        return search_result["message"]

    if not search_result["matches"]:
        return f"No products found matching '{product_name}'."

    variant_ids = [m["variant_id"] for m in search_result["matches"]]
    product_names_found = list({
        f"{m['product_name']} {m['variant_name']}" for m in search_result["matches"]
    })

    # Step 2: Get Monte Carlo predictions (already cached by StockoutPredictor)
    try:
        from models.stockout.predictor import StockoutPredictor
        from core import state as _state

        predictor = StockoutPredictor(
            db_engine=_state.raw_engine,
            config={"n_simulations": 10000, "forecast_days": 30}
        )
        all_predictions = predictor.predict_stockouts(limit=500)

        # Filter to only the variants we found
        relevant = [p for p in all_predictions if p["variant_id"] in variant_ids]

    except Exception as e:
        return f"❌ Could not fetch stockout predictions: {e}"

    if not relevant:
        # Fallback: return basic stock info from search results
        report = f"📦 **{product_name.title()} — Stock Status:**\n\n"
        for m in search_result["matches"]:
            report += f"• **{m['product_name']} {m['variant_name']}** — {m['current_stock']} units in stock\n"
        report += "\n⚠️ Stockout prediction not available for these items yet."
        return report

    # Step 3: Format enriched answer
    report = f"📦 **{product_name.title()} — Stockout Forecast ({len(relevant)} variants):**\n\n"
    
    # Sort by urgency
    relevant.sort(key=lambda x: x["metrics"].get("days_until_stockout", 999))
    
    for p in relevant:
        name = p.get("product_name", f"Variant {p['variant_id']}")
        days = p["metrics"].get("days_until_stockout", "N/A")
        stock = p.get("current_stock", "?")
        risk = p.get("risk_level", "unknown").upper()
        rec = p.get("recommendation", "")
        
        risk_emoji = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}.get(risk, "⚪")
        
        report += f"{risk_emoji} **{name}** — {stock} units left\n"
        if isinstance(days, (int, float)):
            report += f"   Runs out in: **{days:.0f} days** | Risk: {risk}\n"
        if rec:
            report += f"   Recommendation: {rec}\n"
        report += "\n"

    return report
```

---

### Step 2.2 — Add New Tool: `get_product_basket_tool`

**Answers:** "what do people buy with Maggi", "what sells with Lays", "cross-sell suggestions for dairy"

```python
@tool
def get_product_basket_tool(product_name: str) -> str:
    """
    Finds what products are frequently bought together with the given product.
    Uses FP-Growth market basket analysis results.
    
    Examples: "what sells with Maggi", "cross-sell for Lays", 
              "what goes with bread", "combo suggestions for milk"
    """
    if not SEARCH_ENGINE or not SEARCH_ENGINE.is_ready:
        return "⏳ Search engine warming up."

    # Step 1: Resolve product name
    search_result = SEARCH_ENGINE.search("product", product_name, limit=5)
    if "error" in search_result:
        return search_result["message"]

    if not search_result["matches"]:
        return f"No products found matching '{product_name}'."

    # Get the canonical product name from the best match
    best_match = search_result["matches"][0]
    canonical_name = best_match["product_name"]
    variant_name = best_match["variant_name"]

    # Step 2: Get FP-Growth rules from analytics cache
    try:
        from analytics import AnalyticsEngine
        from core import state as _state

        analytics = AnalyticsEngine(_state.raw_engine, base_dir=_state.BASE_DIR)
        dashboard = analytics.get_dashboard_metrics()
        dash_data = dashboard.get("data", dashboard)
        mb = dash_data.get("market_basket", {})
        rules = mb.get("rules", []) if isinstance(mb, dict) else []

    except Exception as e:
        return f"❌ Could not fetch market basket data: {e}"

    if not rules:
        return f"🛒 Market basket analysis not ready yet. Check back after the analytics pipeline runs."

    # Step 3: Filter rules where this product appears as antecedent
    # Match against canonical product name (case-insensitive)
    search_term = canonical_name.lower()
    matching_rules = []
    
    for rule in rules:
        ant = rule.get("antecedent", [])
        ant_str = ant[0] if isinstance(ant, list) and ant else str(ant)
        if search_term in ant_str.lower():
            matching_rules.append(rule)

    if not matching_rules:
        return (f"🛒 No frequent buying patterns found for **{canonical_name}** yet.\n"
                f"This may mean it hasn't been sold enough times to establish patterns, "
                f"or the market basket cache needs to refresh.")

    # Step 4: Format results
    report = f"🛒 **What sells with {canonical_name} {variant_name}:**\n\n"
    for i, rule in enumerate(matching_rules[:8], 1):
        ant = rule.get("antecedent", ["?"])
        con = rule.get("consequent", ["?"])
        conf = rule.get("confidence", 0)
        lift = rule.get("lift", 0)
        ant_str = ant[0] if isinstance(ant, list) else str(ant).strip("[]'")
        con_str = con[0] if isinstance(con, list) else str(con).strip("[]'")
        report += f"{i}. **{ant_str}** → **{con_str}** | Confidence: {conf:.0%} | Lift: {lift:.2f}\n"

    report += f"\n💡 *Place these products near {canonical_name} to boost sales.*"
    return report
```

---

### Step 2.3 — Add New Tool: `get_customer_churn_for_product_tool`

**Answers:** "customers who buy Lays, are any of them at churn risk", "which chips buyers haven't come back", "loyalty risk for our dairy customers"

```python
@tool
def get_customer_churn_for_product_tool(product_name: str) -> str:
    """
    Finds customers who have bought a specific product and checks their churn risk.
    Cross-references product buyers with XGBoost churn predictions.
    
    Examples: "are Lays buyers at churn risk", "which chips customers are leaving",
              "churn risk for customers who buy bread", "loyal buyers of Maggi"
    """
    if not SEARCH_ENGINE or not SEARCH_ENGINE.is_ready:
        return "⏳ Search engine warming up."

    # Step 1: Resolve product to variant IDs
    search_result = SEARCH_ENGINE.search("product", product_name, limit=10)
    if "error" in search_result:
        return search_result["message"]

    if not search_result["matches"]:
        return f"No products found matching '{product_name}'."

    variant_ids = [m["variant_id"] for m in search_result["matches"]]
    canonical = search_result["matches"][0]["product_name"]

    # Step 2: Find customers who have bought these variants
    try:
        from sqlalchemy import text
        from core import state as _state

        placeholders = ",".join([str(vid) for vid in variant_ids])
        with _state.raw_engine.connect() as conn:
            buyer_rows = conn.execute(text(f"""
                SELECT DISTINCT c.id, c.name
                FROM customer c
                JOIN credit_sale cs ON c.id = cs.customer_id
                JOIN credit_sale_item csi ON cs.id = csi.sale_id
                WHERE csi.variant_id IN ({placeholders})
            """)).fetchall()

    except Exception as e:
        return f"❌ Could not fetch buyer data: {e}"

    if not buyer_rows:
        return f"No customer purchase history found for '{canonical}'."

    buyer_ids = {row.id for row in buyer_rows}
    buyer_map = {row.id: row.name for row in buyer_rows}

    # Step 3: Get XGBoost churn predictions and filter to these buyers
    try:
        from analytics import AnalyticsEngine
        from core import state as _state

        analytics = AnalyticsEngine(_state.raw_engine, base_dir=_state.BASE_DIR)
        dashboard = analytics.get_dashboard_metrics()
        dash_data = dashboard.get("data", dashboard)
        all_churn = dash_data.get("churn_risk", [])

    except Exception as e:
        return f"❌ Could not fetch churn predictions: {e}"

    # Filter churn results to only buyers of this product
    at_risk = [
        c for c in all_churn
        if c.get("customer_id") in buyer_ids and c.get("risk_score", 0) >= 50
    ]
    safe = [
        c for c in all_churn
        if c.get("customer_id") in buyer_ids and c.get("risk_score", 0) < 50
    ]

    report = f"👥 **Churn Risk — Buyers of {canonical} ({len(buyer_ids)} customers total):**\n\n"
    
    if at_risk:
        at_risk.sort(key=lambda x: x.get("risk_score", 0), reverse=True)
        report += f"🔴 **At Risk ({len(at_risk)} customers):**\n"
        for c in at_risk[:10]:
            report += (f"• **{c.get('name')}** — Risk: {c.get('risk_score')}% | "
                      f"Inactive: {c.get('days_inactive', 0)} days | {c.get('trend', '')}\n")
    else:
        report += "✅ No high-risk churn detected among these buyers.\n"

    report += f"\n✅ **Loyal Buyers ({len(safe)} customers):** Regularly purchasing, low churn risk.\n"
    report += f"\n💡 *Consider a loyalty offer for at-risk {canonical} buyers to retain them.*"
    return report
```

---

### Step 2.4 — Add New Tool: `resolve_entity_tool`

**Answers:** Direct entity lookup for the agent when it needs IDs for its own SQL queries or chaining.

```python
@tool
def resolve_entity_tool(name: str, entity_type: str = "product") -> str:
    """
    Resolves a fuzzy name to exact database records using semantic search.
    Returns IDs and metadata. Use this when you need to find the exact ID 
    of a product, customer, or supplier before running a SQL query or analysis.
    
    entity_type: 'product', 'customer', or 'supplier'
    
    Examples: "resolve Maggi to product ID", "find supplier ID for Haldiram",
              "get customer ID for Ramesh Sharma"
    """
    if not SEARCH_ENGINE or not SEARCH_ENGINE.is_ready:
        return "⏳ Search engine warming up."

    result = SEARCH_ENGINE.search(entity_type, name, limit=5)
    if "error" in result:
        return result["message"]

    if not result["matches"]:
        return f"No {entity_type} found matching '{name}'."

    lines = [f"🔍 **Resolved '{name}' → {entity_type} matches:**\n"]
    for m in result["matches"]:
        if entity_type == "product":
            lines.append(f"- ID: {m['variant_id']} | {m['product_name']} {m['variant_name']} "
                        f"| Category: {m['category']} | Stock: {m['current_stock']} | Match: {m['similarity']}%")
        elif entity_type == "customer":
            lines.append(f"- ID: {m['customer_id']} | {m['name']} | Mobile: {m['mobile']} | Match: {m['similarity']}%")
        elif entity_type == "supplier":
            lines.append(f"- ID: {m['supplier_id']} | {m['name']} | Mobile: {m['mobile']} | Match: {m['similarity']}%")

    return "\n".join(lines)
```

---

### Step 2.5 — Update `search_catalog_tool` and `search_supplier_tool`

Replace the old `search_catalog_tool` in `tools.py` to use the new display wrapper and support supplier:

```python
@tool
def search_catalog_tool(search_term: str, category: str = "product"):
    """
    SEARCH ENGINE. Use this when user asks 'Do we have X?' or 'Find X' for general lookup.
    category: 'product', 'customer', or 'supplier'.
    For deep analysis (stockout, churn, basket), use the specialized tools instead.
    """
    if not SEARCH_ENGINE or not SEARCH_ENGINE.is_ready:
        return "Search Engine is still loading..."
    # Use display version for general chat responses
    return SEARCH_ENGINE.search_display(category, search_term, limit=10)
```

The old `search_supplier_tool` (plain SQL LIKE) can be **kept as a fallback** for exact name lookups but `search_catalog_tool` with `category="supplier"` now handles semantic supplier search. You can keep both or remove `search_supplier_tool` — it doesn't hurt to keep it.

---

### Step 2.6 — Update `agent_builder.py` Tool List and System Prompt

In `agent_builder.py`, import and register the new tools:

```python
from .tools import (
    # Existing — keep all
    search_catalog_tool,
    search_supplier_tool,
    check_churn_risk_tool,
    get_market_insights_tool,
    get_business_overview_tool,
    get_sales_trends_tool,
    get_top_performers_tool,
    get_customer_segments_tool,
    get_inventory_velocity_tool,
    get_revenue_comparison_tool,
    # NEW — add these
    get_product_stockout_tool,
    get_product_basket_tool,
    get_customer_churn_for_product_tool,
    resolve_entity_tool,
)
```

Update `all_tools` list in `build_nexus_agent`:

```python
all_tools = [
    # Entity resolution and search
    resolve_entity_tool,          # NEW: fuzzy name → ID lookup
    search_catalog_tool,          # General search (products/customers/suppliers)
    search_supplier_tool,         # Keep: exact supplier name SQL fallback

    # Product-specific ML tools (NEW)
    get_product_stockout_tool,    # Monte Carlo predictions for a specific product
    get_product_basket_tool,      # FP-Growth associations for a specific product
    get_customer_churn_for_product_tool,  # XGBoost churn for a product's buyers

    # Business-wide ML tools (existing — keep all)
    check_churn_risk_tool,        # All customers churn risk
    get_market_insights_tool,     # All market basket rules
    get_business_overview_tool,   # Full business summary
    get_sales_trends_tool,
    get_top_performers_tool,
    get_customer_segments_tool,
    get_inventory_velocity_tool,
    get_revenue_comparison_tool,
    run_sql_query,
]
```

Update the **TOOL SELECTION GUIDE** section of the system prompt:

```python
system_prompt = """You are 'NexusRetail OS AI', a retail business intelligence assistant.

CRITICAL RULES:
1. GIVE DIRECT, CONCLUSIVE ANSWERS. NEVER ask follow-up questions. Just answer fully.
2. ALWAYS use tools. NEVER say "I don't know" — call a tool instead.
3. You are READ-ONLY. You CANNOT add, delete, or update any records.
4. Use Indian Rupees (₹) for all currency.
5. Be concise. Use markdown headers, bullet points and bold for key numbers.
6. PREFER calling ONE specialized tool over calling many generic ones.

TOOL SELECTION GUIDE (CRITICAL — pick the RIGHT tool):

PRODUCT-SPECIFIC QUERIES (use these first for product questions):
- "when will [product] finish" / "[product] stock running low" / "restock [product]"
  → get_product_stockout_tool(product_name)
  
- "what sells with [product]" / "cross-sell [product]" / "combo for [product]"
  → get_product_basket_tool(product_name)
  
- "are [product] buyers at risk" / "churn for [product] customers" 
  → get_customer_churn_for_product_tool(product_name)

- "find [product/customer/supplier]" / "do we have X" / "who supplies X"
  → search_catalog_tool(search_term, category='product'/'customer'/'supplier')

- "get ID for [name]" / "resolve [name]" (when you need ID for SQL)
  → resolve_entity_tool(name, entity_type)

BUSINESS-WIDE QUERIES:
- "business summary" / "how are we doing" / "give me insights" 
  → get_business_overview_tool()
  
- "all customers at churn risk" / "who's leaving overall"
  → check_churn_risk_tool()
  
- "shopping patterns overall" / "what goes with what generally"
  → get_market_insights_tool()
  
- "revenue this week vs last" → get_revenue_comparison_tool()
- "sales trends" → get_sales_trends_tool()
- "top sellers" / "dead stock" → get_top_performers_tool()
- "inventory status" / "what to restock overall" → get_inventory_velocity_tool()
- "customer segments" / "who buys most" → get_customer_segments_tool()
- Any other data question → run_sql_query with SELECT query

...(keep rest of system prompt unchanged)"""
```

---

### Phase 2 Checkpoints — Test Before Moving to Phase 3

Test each query exactly as written. These are your acceptance tests:

- [ ] **"how many types of chips and when will stock finish"** → Agent calls `get_product_stockout_tool("chips")` → Returns variant list with Monte Carlo days-to-stockout, not raw SQL math
- [ ] **"which cold drinks are running low"** → `get_product_stockout_tool("cold drinks")` → Returns category-matched variants filtered by risk level
- [ ] **"customers who buy Lays, are any of them at churn risk"** → `get_customer_churn_for_product_tool("Lays")` → Returns buyer list with XGBoost scores
- [ ] **"what do people buy with Maggi"** → `get_product_basket_tool("Maggi")` → Returns FP-Growth association rules for Maggi variants
- [ ] **"find supplier for haldiram"** → `search_catalog_tool("haldiram", "supplier")` → Returns Haldiram supplier record via ChromaDB semantic search
- [ ] **"get ID for Ramesh Sharma"** → `resolve_entity_tool("Ramesh Sharma", "customer")` → Returns customer ID and metadata
- [ ] All existing tools still work (business overview, trends, revenue comparison, etc.)
- [ ] `run_sql_query` still available for edge cases

---

## Phase 3 — UI Fuzzy Search Endpoint

**What this phase does:** Builds a fast, live, typo-tolerant search endpoint for the POS UI search bar. This uses only SQL + lightweight fuzzy matching. No ChromaDB, no embeddings, no ML. This is what the owner uses at the billing counter.

**Why Phase 3 is separate:** This is completely independent of the chatbot and ChromaDB. It can be built and shipped standalone. Don't block UI improvements on Phase 2 completion.

---

### Step 3.1 — Install RapidFuzz

Add to `requirements.txt`:
```
rapidfuzz==3.9.7
```

---

### Step 3.2 — Create `routes/search.py`

```python
# FILE: python_server/routes/search.py
# Fast fuzzy search endpoint for POS UI — no ML, no ChromaDB, live SQL only

from fastapi import APIRouter
from sqlalchemy import text
from rapidfuzz import fuzz, process
from core import state

router = APIRouter()


def _fuzzy_filter(query: str, candidates: list, key_fn, threshold: int = 60):
    """
    Filters a list using RapidFuzz partial ratio matching.
    Returns items where fuzzy score >= threshold.
    """
    q = query.lower().strip()
    results = []
    for item in candidates:
        name = key_fn(item).lower()
        # Check exact prefix first (fastest)
        if name.startswith(q):
            results.append((item, 100))
            continue
        # Then fuzzy partial match
        score = fuzz.partial_ratio(q, name)
        if score >= threshold:
            results.append((item, score))
    # Sort by score descending
    results.sort(key=lambda x: x[1], reverse=True)
    return [item for item, score in results]


@router.get("/api/search")
async def search(q: str, type: str = "product", limit: int = 20):
    """
    Fast UI search. type: 'product', 'customer', 'supplier'.
    Returns live data directly from SQLite. Sub-10ms for small catalogs.
    """
    if not state.raw_engine:
        return {"success": False, "error": "Database not connected", "results": []}

    if not q or len(q.strip()) < 1:
        return {"success": True, "results": [], "count": 0}

    q = q.strip()

    try:
        with state.raw_engine.connect() as conn:

            if type == "product":
                # Broad SQL fetch with LIKE (catches prefix matches fast)
                rows = conn.execute(text("""
                    SELECT v.id, p.name as product_name, v.name as variant_name,
                           p.category, v.price, v.current_stock, v.unit
                    FROM product_variant v
                    JOIN product p ON v.product_id = p.id
                    WHERE (LOWER(p.name) LIKE LOWER(:q) OR LOWER(v.name) LIKE LOWER(:q)
                           OR LOWER(p.category) LIKE LOWER(:q))
                    LIMIT 100
                """), {"q": f"%{q}%"}).fetchall()

                # Apply fuzzy filter on top of SQL results
                filtered = _fuzzy_filter(
                    q, rows,
                    key_fn=lambda r: f"{r.product_name} {r.variant_name}",
                    threshold=55
                )[:limit]

                results = [{
                    "id": r.id,
                    "product_name": r.product_name,
                    "variant_name": r.variant_name,
                    "category": r.category,
                    "price": float(r.price or 0),
                    "stock": float(r.current_stock or 0),
                    "unit": r.unit,
                    "display": f"{r.product_name} {r.variant_name}"
                } for r in filtered]

            elif type == "customer":
                # For customers: exact prefix on mobile OR fuzzy on name
                rows = conn.execute(text("""
                    SELECT id, name, mobile, address, balance
                    FROM customer
                    WHERE LOWER(name) LIKE LOWER(:q) OR CAST(mobile AS TEXT) LIKE :mq
                    LIMIT 100
                """), {"q": f"%{q}%", "mq": f"{q}%"}).fetchall()

                filtered = _fuzzy_filter(
                    q, rows,
                    key_fn=lambda r: r.name,
                    threshold=60
                )[:limit]

                results = [{
                    "id": r.id,
                    "name": r.name,
                    "mobile": str(r.mobile or ""),
                    "address": r.address or "",
                    "balance": float(r.balance or 0),
                    "display": f"{r.name} ({r.mobile})"
                } for r in filtered]

            elif type == "supplier":
                rows = conn.execute(text("""
                    SELECT id, name, mobile
                    FROM supplier
                    WHERE LOWER(name) LIKE LOWER(:q)
                    LIMIT 50
                """), {"q": f"%{q}%"}).fetchall()

                filtered = _fuzzy_filter(
                    q, rows,
                    key_fn=lambda r: r.name,
                    threshold=60
                )[:limit]

                results = [{
                    "id": r.id,
                    "name": r.name,
                    "mobile": str(r.mobile or ""),
                    "display": r.name
                } for r in filtered]

            else:
                return {"success": False, "error": f"Unknown type: {type}", "results": []}

        return {"success": True, "type": type, "query": q, "count": len(results), "results": results}

    except Exception as e:
        return {"success": False, "error": str(e), "results": []}
```

---

### Step 3.3 — Register Router in `main.py`

```python
# Add import
from routes.search import router as search_router

# Add after other routers
app.include_router(search_router)
```

---

### Step 3.4 — Frontend Integration (React)

Replace the current POS search bar fetch with calls to the new endpoint:

```javascript
// In your product search component
const searchProducts = async (query) => {
  if (!query || query.length < 1) return [];
  const res = await fetch(`http://127.0.0.1:8000/api/search?q=${encodeURIComponent(query)}&type=product`);
  const data = await res.json();
  return data.results || [];
};

// In your customer lookup component
const searchCustomers = async (query) => {
  const res = await fetch(`http://127.0.0.1:8000/api/search?q=${encodeURIComponent(query)}&type=customer`);
  const data = await res.json();
  return data.results || [];
};
```

---

### Phase 3 Checkpoints

- [ ] `GET /api/search?q=lays&type=product` returns Lays variants in under 50ms
- [ ] `GET /api/search?q=lays+masa&type=product` returns "Lays Masala" (typo tolerance working)
- [ ] `GET /api/search?q=9876543210&type=customer` returns customer by mobile prefix
- [ ] `GET /api/search?q=ramesh&type=customer` returns fuzzy name matches
- [ ] `GET /api/search?q=haldiram&type=supplier` returns supplier records
- [ ] Newly added product appears in search immediately (no restart, no wait — it's live SQL)
- [ ] Deleted product disappears immediately from search results
- [ ] POS search bar in UI uses this endpoint instead of any old implementation

---

## Phase 4 — Tool Audit: Keep, Refactor, or Remove

**What this phase does:** Reviews all 11 existing agent tools after the new tools are added. Decides what stays, what gets cleaned up, and what is now redundant. Also cleans up `tools.py` context injection.

---

### Tool Audit Decision Table

| Tool | Decision | Reason |
|---|---|---|
| `search_catalog_tool` | **KEEP, updated** | General search, now uses ChromaDB for products/customers/suppliers |
| `search_supplier_tool` | **KEEP as fallback** | Plain SQL LIKE, fast for exact supplier lookup by partial name |
| `resolve_entity_tool` | **NEW — add** | Structured ID resolution for SQL chaining |
| `get_product_stockout_tool` | **NEW — add** | Monte Carlo wiring |
| `get_product_basket_tool` | **NEW — add** | FP-Growth wiring |
| `get_customer_churn_for_product_tool` | **NEW — add** | XGBoost wiring for product-buyer intersection |
| `check_churn_risk_tool` | **KEEP** | Business-wide churn overview — different scope than product-specific tool |
| `get_market_insights_tool` | **KEEP** | Business-wide basket rules overview — different scope |
| `get_business_overview_tool` | **KEEP** | Best single tool for strategic questions — proven useful |
| `get_sales_trends_tool` | **KEEP** | Unique time-series data, no overlap with new tools |
| `get_top_performers_tool` | **KEEP** | Dead stock + top sellers — useful, no overlap |
| `get_customer_segments_tool` | **KEEP** | Segmentation view — different from churn tool |
| `get_inventory_velocity_tool` | **KEEP** | General inventory overview — `get_product_stockout_tool` is product-specific, this is catalog-wide |
| `get_revenue_comparison_tool` | **KEEP** | Revenue comparison with category breakdown — standalone value |
| `run_sql_query` | **KEEP** | Safety net for any edge case query not covered by tools |

**Net result:** 11 existing tools all kept + 4 new tools = 15 tools total. No removals because there is no actual overlap — existing tools are business-wide, new tools are entity-specific.

---

### Step 4.1 — Clean Up `set_context` in `tools.py`

The current `set_context` function injects `engine`, `search_engine_ref`, and `analytics_cache_ref`. After Phase 1 and 2, the new tools import from `core.state` directly (same pattern as `check_churn_risk_tool` already uses). Verify that all new tools are consistent in how they access state — use `from core import state as _state` pattern throughout.

---

### Step 4.2 — Update `tools.py` imports block

```python
# At the top of tools.py, ensure new tools are importable
# All four new tools should be defined in tools.py alongside existing ones
# Do NOT put them in a separate file — keep the single tools.py pattern
```

---

### Phase 4 Checkpoints

- [ ] Total tool count in agent is 15 (11 original + 4 new)
- [ ] No import errors on startup
- [ ] `agent_builder.py` tool list matches exactly — no tool registered twice
- [ ] System prompt TOOL SELECTION GUIDE has entries for all 4 new tools
- [ ] Run a full suite of the 4 target queries from Phase 2 checkpoints again — still working after tool list expansion

---

## Phase 5 — End-to-End Hardening

**What this phase does:** Final polish. Handles edge cases, error boundaries, and ensures the full system is production-stable for a shipped desktop app.

---

### Step 5.1 — Handle ChromaDB Cold Start on First Install

On a fresh user installation, ChromaDB has zero records. The polling loop handles ongoing sync, but the first sync happens in `_heavy_load_process`. Add a startup status endpoint so the UI can show a "warming up" indicator:

In `routes/analytics.py`, update the existing `/health` endpoint:

```python
@router.get("/health")
async def health_check():
    from core import state
    search_status = "ready"
    if hasattr(state, 'search_engine') and state.search_engine:
        if state.search_engine.is_loading:
            search_status = "warming_up"
        elif state.search_engine.load_error:
            search_status = "error"
        elif not state.search_engine.is_ready:
            search_status = "offline"
    
    return {
        "status": "Active" if state.safety_guard else "Missing Keys",
        "search_engine": search_status,
        "ai_failed": state.AI_INIT_FAILED
    }
```

---

### Step 5.2 — Handle Empty ML Cache Gracefully in New Tools

If `StockoutPredictor` cache is cold (first run, cache was just cleared), `predict_stockouts()` runs a fresh Monte Carlo simulation which takes time. Add a timeout guard in `get_product_stockout_tool`:

```python
# In get_product_stockout_tool, wrap the predictor call:
import concurrent.futures

with concurrent.futures.ThreadPoolExecutor() as executor:
    future = executor.submit(predictor.predict_stockouts, limit=500)
    try:
        all_predictions = future.result(timeout=30)  # 30 second max
    except concurrent.futures.TimeoutError:
        return (f"⏳ Stockout predictions are being calculated (Monte Carlo simulation running). "
                f"Basic stock info: " + 
                "\n".join([f"• {m['product_name']} {m['variant_name']}: {m['current_stock']} units" 
                           for m in search_result["matches"]]))
```

---

### Step 5.3 — ChromaDB Thread Safety

ChromaDB's `PersistentClient` is thread-safe for reads but the `_polling_loop` writes to the same collections the main thread reads. Add a threading lock to `_sync_entity`:

```python
# In __init__, add:
self._sync_lock = threading.Lock()

# In _sync_entity, wrap with lock:
def _sync_entity(self, entity_type):
    with self._sync_lock:
        # ... existing sync code
```

---

### Step 5.4 — force_refresh_all Cleanup

In `analytics.py`, `force_refresh_all()` deletes the entire `ml_store` folder including `ml_store/chroma/`. This would nuke your ChromaDB collections. Fix this:

```python
def force_refresh_all(self):
    """..."""
    ml_store_path = os.path.join(self.stockout_ai.base_dir, "ml_store")
    
    if os.path.exists(ml_store_path):
        # Delete everything EXCEPT the chroma directory
        for item in os.listdir(ml_store_path):
            item_path = os.path.join(ml_store_path, item)
            if item == "chroma":
                print("   ⏭️  Skipping ChromaDB directory (vector store preserved).")
                continue
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
            else:
                os.remove(item_path)
    # ... rest of method unchanged
```

---

### Step 5.5 — Confidence Score is Now Real

Verify that the new ChromaDB cosine distance is returning meaningful similarity scores. ChromaDB cosine distance of 0 = identical, 1 = orthogonal, 2 = opposite. The formula `(1 - dist) * 100` gives:
- `dist=0.1` → 90% match (very close)
- `dist=0.5` → 50% match (related)
- `dist=0.9` → 10% match (distant)

This is mathematically honest unlike the old `100 - (dist * 40)` FAISS formula. No additional changes needed — just verify the scores look sensible in testing.

---

### Phase 5 Checkpoints — Final Acceptance

- [ ] `force_refresh_all()` from dashboard does NOT delete ChromaDB data
- [ ] After `force_refresh_all()`, all 4 target queries still work (ChromaDB intact)
- [ ] Cold start on fresh machine: server starts in < 5 seconds, search warms up in background
- [ ] Polling loop log appears every 5 minutes: `🔄 ChromaDB: Background sync complete.`
- [ ] Adding and deleting records reflect in chatbot answers within 5 minutes max
- [ ] Similarity scores in search results are in sensible range (70%+ for good matches)
- [ ] No threading errors or race conditions under normal usage

---

## Summary: Files Modified Per Phase

| Phase | Files Modified | Files Created |
|---|---|---|
| Phase 1 | `vector_store.py` (full rewrite), `requirements.txt` | None |
| Phase 2 | `tools.py` (4 new tools added), `agent_builder.py` (tool list + system prompt) | None |
| Phase 3 | `main.py` (router registration), `requirements.txt` (rapidfuzz) | `routes/search.py` |
| Phase 4 | `tools.py` (cleanup), `agent_builder.py` (final tool list) | None |
| Phase 5 | `analytics.py` (force_refresh fix), `routes/analytics.py` (health endpoint), `vector_store.py` (lock + timeout) | None |

---

## The 4 Target Queries — Expected Behavior After All Phases Complete

| Query | Tool Called | Data Source | Expected Answer |
|---|---|---|---|
| "how many types of chips and when will stock finish" | `get_product_stockout_tool("chips")` | ChromaDB → Monte Carlo | List of chip variants with days-to-stockout, risk level, recommendation |
| "which cold drinks are running low" | `get_product_stockout_tool("cold drinks")` | ChromaDB → Monte Carlo | Cold drink variants filtered to medium/high/critical risk |
| "customers who buy Lays, are any of them at churn risk" | `get_customer_churn_for_product_tool("Lays")` | ChromaDB → SQL buyers → XGBoost | Lays buyer list segmented by churn risk score |
| "what do people buy with Maggi" | `get_product_basket_tool("Maggi")` | ChromaDB → FP-Growth | Association rules where Maggi is antecedent, with confidence and lift |

---

*Plan authored against codebase: vector_store.py, tools.py, agent_builder.py, analytics.py, main.py, requirements.txt*  
*Date: March 2026*
