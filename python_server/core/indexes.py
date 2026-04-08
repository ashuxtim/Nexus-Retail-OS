# FILE: python_server/core/indexes.py
# Database performance indexes for fast name lookups.
# Fixes slow disambiguation on large datasets.

from sqlalchemy import text
from scripts.backend_logging import get_logger

logger = get_logger("NexusAI_Backend")


def ensure_indexes(engine):
    """Create indexes for fast name lookups and JOIN paths. Safe to run multiple times (IF NOT EXISTS)."""
    try:
        with engine.connect() as c:
            # Name lookup indexes (disambiguation / search)
            c.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_customer_name ON customer(name COLLATE NOCASE)"
                )
            )
            c.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_product_name ON product(name COLLATE NOCASE)"
                )
            )
            c.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_pv_name ON product_variant(name COLLATE NOCASE)"
                )
            )
            c.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_supplier_name ON supplier(name COLLATE NOCASE)"
                )
            )

            # FK join indexes — critical for sales aggregation queries (get_top_customers,
            # get_today_sales, get_monthly_revenue, get_recent_sales, get_top_products, etc.)
            # Without these, every query does full table scans across credit_sale_item.
            c.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_cs_customer_id ON credit_sale(customer_id)"
                )
            )
            c.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_csi_sale_id ON credit_sale_item(sale_id)"
                )
            )
            c.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_csi_variant_id ON credit_sale_item(variant_id)"
                )
            )
            # Date index for today/weekly/monthly revenue queries
            c.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_cs_sale_date ON credit_sale(sale_date)"
                )
            )
            # Purchase query indexes
            c.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_pi_supplier_id ON purchase_invoice(supplier_id)"
                )
            )
            c.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_pit_invoice_id ON purchase_item(invoice_id)"
                )
            )
            c.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_pit_variant_id ON purchase_item(variant_id)"
                )
            )

            c.commit()
        logger.info("✅ Database indexes verified/created.")
    except Exception as e:
        logger.error(f"⚠️ Index creation failed (non-fatal): {e}")
