# FILE: python_server/core/indexes.py
# Database performance indexes for fast name lookups.
# Fixes slow disambiguation on large datasets.

from sqlalchemy import text
from scripts.backend_logging import get_logger

logger = get_logger("NexusAI_Backend")


def ensure_indexes(engine):
    """Create indexes for fast name lookups. Safe to run multiple times (IF NOT EXISTS)."""
    try:
        with engine.connect() as c:
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
            c.commit()
        logger.info("✅ Database indexes verified/created.")
    except Exception as e:
        logger.error(f"⚠️ Index creation failed (non-fatal): {e}")
