# FILE: python_server/ai_engine/queries.py
# Pure Python + SQLAlchemy. No LLM. No imports from ai_engine.
# All pre-written SQL queries as Python functions — zero LLM involved.

from sqlalchemy import text


# ─────────────────────────────────────────
# SALES QUERIES
# ─────────────────────────────────────────

def get_top_customers(engine, limit=5):
    """Top customers by total purchase value."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT c.name, ROUND(SUM(csi.quantity * csi.price_at_sale), 2) as total
            FROM customer c
            JOIN credit_sale cs ON c.id = cs.customer_id
            JOIN credit_sale_item csi ON cs.id = csi.sale_id
            GROUP BY c.id, c.name
            ORDER BY total DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
    return rows


def get_today_sales(engine):
    """Total sales count and revenue for today."""
    with engine.connect() as c:
        row = c.execute(text("""
            SELECT COUNT(DISTINCT cs.id), ROUND(SUM(csi.quantity * csi.price_at_sale), 2)
            FROM credit_sale cs
            JOIN credit_sale_item csi ON cs.id = csi.sale_id
            WHERE date(cs.sale_date) = date('now', 'localtime')
        """)).fetchone()
    return row  # (count, total) — may be (0, None)


def get_monthly_revenue(engine):
    """Total revenue for current month."""
    with engine.connect() as c:
        row = c.execute(text("""
            SELECT ROUND(SUM(csi.quantity * csi.price_at_sale), 2)
            FROM credit_sale cs
            JOIN credit_sale_item csi ON cs.id = csi.sale_id
            WHERE strftime('%Y-%m', cs.sale_date) = strftime('%Y-%m', 'now', 'localtime')
        """)).fetchone()
    return row[0] or 0


def get_weekly_revenue(engine):
    """Total revenue for current week."""
    with engine.connect() as c:
        row = c.execute(text("""
            SELECT ROUND(SUM(csi.quantity * csi.price_at_sale), 2)
            FROM credit_sale cs
            JOIN credit_sale_item csi ON cs.id = csi.sale_id
            WHERE date(cs.sale_date) >= date('now', 'localtime', '-7 days')
        """)).fetchone()
    return row[0] or 0


def get_recent_sales(engine, limit=10):
    """Most recent sales transactions."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT c.name, p.name, pv.name, csi.quantity,
                   csi.price_at_sale, cs.sale_date
            FROM credit_sale cs
            JOIN customer c ON cs.customer_id = c.id
            JOIN credit_sale_item csi ON cs.id = csi.sale_id
            JOIN product_variant pv ON csi.variant_id = pv.id
            JOIN product p ON pv.product_id = p.id
            ORDER BY cs.sale_date DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
    return rows


# ─────────────────────────────────────────
# INVENTORY QUERIES
# ─────────────────────────────────────────

def get_low_stock(engine, threshold=10):
    """Products with stock at or below threshold."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT p.name, pv.name, pv.current_stock, p.category
            FROM product_variant pv
            JOIN product p ON pv.product_id = p.id
            WHERE pv.current_stock <= :threshold
            ORDER BY pv.current_stock ASC
        """), {"threshold": threshold}).fetchall()
    return rows


def get_out_of_stock(engine):
    """Products with zero stock."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT p.name, pv.name, p.category
            FROM product_variant pv
            JOIN product p ON pv.product_id = p.id
            WHERE pv.current_stock = 0
        """)).fetchall()
    return rows


def get_all_products(engine, limit=50):
    """List all products with stock and price."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT p.name, pv.name, pv.price, pv.current_stock, p.category
            FROM product_variant pv
            JOIN product p ON pv.product_id = p.id
            ORDER BY p.name ASC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
    return rows


def search_product(engine, name):
    """Search product by name."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT p.name, pv.name, pv.price, pv.current_stock
            FROM product_variant pv
            JOIN product p ON pv.product_id = p.id
            WHERE LOWER(p.name) LIKE LOWER(:name)
               OR LOWER(pv.name) LIKE LOWER(:name)
            ORDER BY p.name ASC
            LIMIT 20
        """), {"name": f"%{name}%"}).fetchall()
    return rows


def get_top_products(engine, limit=5):
    """Best selling products by quantity sold."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT p.name, pv.name, SUM(csi.quantity) as qty_sold
            FROM credit_sale_item csi
            JOIN product_variant pv ON csi.variant_id = pv.id
            JOIN product p ON pv.product_id = p.id
            GROUP BY pv.id
            ORDER BY qty_sold DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
    return rows


# ─────────────────────────────────────────
# CUSTOMER QUERIES
# ─────────────────────────────────────────

def get_all_customers(engine, limit=50):
    """List all customers."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT name, mobile, address
            FROM customer
            ORDER BY name ASC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
    return rows


def search_customer(engine, name):
    """Search customer by name."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT name, mobile, address
            FROM customer
            WHERE LOWER(name) LIKE LOWER(:name)
            LIMIT 10
        """), {"name": f"%{name}%"}).fetchall()
    return rows


def get_customer_purchase_history(engine, customer_name, limit=10):
    """Purchase history for a specific customer."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT p.name, pv.name, csi.quantity,
                   csi.price_at_sale, cs.sale_date
            FROM credit_sale cs
            JOIN customer c ON cs.customer_id = c.id
            JOIN credit_sale_item csi ON cs.id = csi.sale_id
            JOIN product_variant pv ON csi.variant_id = pv.id
            JOIN product p ON pv.product_id = p.id
            WHERE LOWER(c.name) LIKE LOWER(:name)
            ORDER BY cs.sale_date DESC
            LIMIT :limit
        """), {"name": f"%{customer_name}%", "limit": limit}).fetchall()
    return rows


# ─────────────────────────────────────────
# SUPPLIER & PURCHASE QUERIES
# ─────────────────────────────────────────

def get_all_suppliers(engine):
    """List all suppliers."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT name, mobile FROM supplier ORDER BY name ASC
        """)).fetchall()
    return rows


def get_recent_purchases(engine, limit=10):
    """Most recent purchases from suppliers."""
    with engine.connect() as c:
        rows = c.execute(text("""
            SELECT s.name, p.name, pv.name, pit.quantity,
                   pit.unit_cost, pi.invoice_date
            FROM purchase_invoice pi
            JOIN supplier s ON pi.supplier_id = s.id
            JOIN purchase_item pit ON pi.id = pit.invoice_id
            JOIN product_variant pv ON pit.variant_id = pv.id
            JOIN product p ON pv.product_id = p.id
            ORDER BY pi.invoice_date DESC
            LIMIT :limit
        """), {"limit": limit}).fetchall()
    return rows


# ─────────────────────────────────────────
# SUMMARY / DASHBOARD
# ─────────────────────────────────────────

def get_quick_summary(engine):
    """Single call to get key dashboard numbers."""
    with engine.connect() as c:
        today = c.execute(text("""
            SELECT COUNT(DISTINCT cs.id), ROUND(SUM(csi.quantity * csi.price_at_sale), 2)
            FROM credit_sale cs
            JOIN credit_sale_item csi ON cs.id = csi.sale_id
            WHERE date(cs.sale_date) = date('now', 'localtime')
        """)).fetchone()

        low_stock_count = c.execute(text("""
            SELECT COUNT(*) FROM product_variant WHERE current_stock <= 10
        """)).fetchone()[0]

        total_customers = c.execute(text("""
            SELECT COUNT(*) FROM customer
        """)).fetchone()[0]

        total_products = c.execute(text("""
            SELECT COUNT(*) FROM product_variant
        """)).fetchone()[0]

    return {
        "today_sales_count": today[0] or 0,
        "today_revenue": today[1] or 0,
        "low_stock_items": low_stock_count,
        "total_customers": total_customers,
        "total_products": total_products,
    }
