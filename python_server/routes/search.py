# FILE: python_server/routes/search.py
# Fast fuzzy search endpoint for POS UI — no ML, no ChromaDB, live SQL only

from fastapi import APIRouter
from sqlalchemy import text
from rapidfuzz import fuzz
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
        if name.startswith(q) or q in name:
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
    sql_q = q.split()[0] if q else ""

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
                """), {"q": f"%{sql_q}%"}).fetchall()

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
                # Crucial Fix: ensure mq maps to q% to catch mobile prefixes
                rows = conn.execute(text("""
                    SELECT id, name, mobile, address, balance
                    FROM customer
                    WHERE LOWER(name) LIKE LOWER(:q) OR CAST(mobile AS TEXT) LIKE :mq
                    LIMIT 100
                """), {"q": f"%{sql_q}%", "mq": f"{q}%"}).fetchall()

                filtered = _fuzzy_filter(
                    q, rows,
                    key_fn=lambda r: f"{r.name} {r.mobile or ''}",
                    threshold=60
                )[:limit]

                results = [{
                    "id": r.id,
                    "name": r.name,
                    "mobile": str(r.mobile or ""),
                    "address": r.address or "",
                    "balance": float(r.balance or 0),
                    "display": f"{r.name} ({r.mobile})" if r.mobile else r.name
                } for r in filtered]

            elif type == "supplier":
                rows = conn.execute(text("""
                    SELECT id, name, mobile
                    FROM supplier
                    WHERE LOWER(name) LIKE LOWER(:q)
                """), {"q": f"%{sql_q}%"}).fetchall()

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
