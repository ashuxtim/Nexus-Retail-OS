#!/usr/bin/env python3
"""
gen_validate.py  —  NexusRetailOS 10-Year Seed  (Step 3 of 3)
Runs 12 SQL validation checks against the seeded database.
Confirms data is compatible with all 4 ML models:
  XGBoost Churn, FP-Growth Basket, FB Prophet Forecast, Monte Carlo Stockout.

Run standalone:  python gen_validate.py
Or via master:   from gen_validate import main; main()

Exits with code 0 on all-pass, code 1 on any failure.
"""

import os, sys, sqlite3, time
from datetime import datetime

# ═══════════════════════════════════════════════════════════════════════════
#  PATH RESOLUTION
# ═══════════════════════════════════════════════════════════════════════════
if "NEXUS_USER_DATA" in os.environ:
    BASE_DIR = os.environ["NEXUS_USER_DATA"]
elif sys.platform == "win32":
    BASE_DIR = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
else:
    BASE_DIR = os.path.join(os.path.expanduser("~"), ".config", "NexusRetailOS")

DB_PATH = os.path.join(BASE_DIR, "nexus.db")

# ═══════════════════════════════════════════════════════════════════════════
#  VALIDATION CHECKS
# ═══════════════════════════════════════════════════════════════════════════
CHECKS = [
    {
        "name": "Total sales (credit_sale rows)",
        "model": "All models",
        "query": "SELECT COUNT(*) FROM credit_sale",
        "check": lambda x: x >= 800_000,
        "expect": ">= 800,000 rows",
        "hint": "Transaction volume too low — check S-curve growth and daily_tx_count()",
    },
    {
        "name": "Total sale items (credit_sale_item rows)",
        "model": "All models",
        "query": "SELECT COUNT(*) FROM credit_sale_item",
        "check": lambda x: x >= 4_000_000,
        "expect": ">= 4,000,000 rows",
        "hint": "Item count too low — check basket builder",
    },
    {
        "name": "Prophet — distinct revenue days (last 730)",
        "model": "FB Prophet",
        "query": "SELECT COUNT(DISTINCT DATE(s.sale_date)) FROM credit_sale s WHERE s.sale_date >= date('now', '-730 days')",
        "check": lambda x: x >= 700,
        "expect": ">= 700 non-zero days in last 730",
        "hint": "Prophet needs 2+ years dense data. Ensure simulation covers up to today.",
    },
    {
        "name": "FP-Growth — transactions in last 90 days",
        "model": "FP-Growth",
        "query": "SELECT COUNT(*) FROM credit_sale WHERE sale_date >= date('now', '-90 days')",
        "check": lambda x: x >= 40_000,
        "expect": ">= 40,000 transactions in last 90 days",
        "hint": "Last 90 days too sparse. Check that simulation ends near today.",
    },
    {
        "name": "FP-Growth — average basket size",
        "model": "FP-Growth",
        "query": "SELECT AVG(cnt) FROM (SELECT sale_id, COUNT(*) as cnt FROM credit_sale_item GROUP BY sale_id)",
        "check": lambda x: x is not None and x >= 2.5,
        "expect": "avg basket >= 2.5 items per sale",
        "hint": "Basket too small. Increase random items in build_basket()",
    },
    {
        "name": "XGBoost — active customers (bought last 90 days)",
        "model": "XGBoost Churn",
        "query": "SELECT COUNT(DISTINCT customer_id) FROM credit_sale WHERE sale_date >= date('now', '-90 days')",
        "check": lambda x: x >= 2000,
        "expect": ">= 2,000 active customers last 90 days",
        "hint": "Too few recent customers. Ensure customer join_days and churn_days are spread correctly.",
    },
    {
        "name": "XGBoost — churned customers (no buy last 60d, bought before)",
        "model": "XGBoost Churn",
        "query": """
            SELECT COUNT(*) FROM customer c
            WHERE EXISTS (
                SELECT 1 FROM credit_sale
                WHERE customer_id = c.id
                AND sale_date < date('now', '-60 days')
            )
            AND NOT EXISTS (
                SELECT 1 FROM credit_sale
                WHERE customer_id = c.id
                AND sale_date >= date('now', '-60 days')
            )
        """,
        "check": lambda x: x >= 300,
        "expect": ">= 300 churned customers for training label",
        "hint": "Too few churned labels. Ensure 15% permanent churn is applied correctly.",
    },
    {
        "name": "Monte Carlo — variants with demand data (last 90 days)",
        "model": "Monte Carlo",
        "query": """
            SELECT COUNT(DISTINCT i.variant_id)
            FROM credit_sale_item i
            JOIN credit_sale s ON s.id = i.sale_id
            WHERE s.sale_date >= date('now', '-90 days')
        """,
        "check": lambda x: x >= 200,
        "expect": ">= 200 variants with demand history",
        "hint": "Too few variants sold recently. Check that sales cover most product variants.",
    },
    {
        "name": "Credit stability — no customer over ₹1,00,000",
        "model": "Credit System",
        "query": "SELECT COUNT(*) FROM customer WHERE balance > 100000",
        "check": lambda x: x == 0,
        "expect": "0 customers with balance > ₹1,00,000",
        "hint": "Credit runaway detected. Check hard-ceiling enforcement in payment logic.",
    },
    {
        "name": "Credit stability — average outstanding balance",
        "model": "Credit System",
        "query": "SELECT AVG(balance) FROM customer WHERE balance > 0",
        "check": lambda x: x is None or (300 <= x <= 30000),
        "expect": "avg credit balance ₹300 – ₹30,000",
        "hint": "Credit avg out of range. Check salary-week clearance and spontaneous payment rates.",
    },
    {
        "name": "Purchase invoices — no NULL supplier_id",
        "model": "Stockout / Suppliers",
        "query": "SELECT COUNT(*) FROM purchase_invoice WHERE supplier_id IS NULL",
        "check": lambda x: x == 0,
        "expect": "0 invoices with NULL supplier_id",
        "hint": "Some invoices lack supplier. Check fallback supplier assignment in restock logic.",
    },
    {
        "name": "Product variants — no negative stock",
        "model": "Monte Carlo",
        "query": "SELECT COUNT(*) FROM product_variant WHERE current_stock < 0",
        "check": lambda x: x == 0,
        "expect": "0 variants with negative current_stock",
        "hint": "Negative stock exists. Ensure inventory never goes below 0 in simulation.",
    },
]

# ═══════════════════════════════════════════════════════════════════════════
#  SUMMARY STATS  (no pass/fail, just informational)
# ═══════════════════════════════════════════════════════════════════════════
SUMMARY_QUERIES = [
    ("Products", "SELECT COUNT(*) FROM product"),
    ("Variants", "SELECT COUNT(*) FROM product_variant"),
    ("Customers", "SELECT COUNT(*) FROM customer"),
    ("Credit customers", "SELECT COUNT(*) FROM customer WHERE balance > 0"),
    ("Suppliers", "SELECT COUNT(*) FROM supplier"),
    ("Sales", "SELECT COUNT(*) FROM credit_sale"),
    ("Sale items", "SELECT COUNT(*) FROM credit_sale_item"),
    ("Payments", "SELECT COUNT(*) FROM payment"),
    ("Invoices", "SELECT COUNT(*) FROM purchase_invoice"),
    ("Purchase items", "SELECT COUNT(*) FROM purchase_item"),
    (
        "Low-stock variants",
        "SELECT COUNT(*) FROM product_variant WHERE current_stock < 15",
    ),
    (
        "Avg basket size",
        "SELECT ROUND(AVG(cnt),2) FROM (SELECT sale_id, COUNT(*) cnt FROM credit_sale_item GROUP BY sale_id)",
    ),
    (
        "Avg credit balance",
        "SELECT ROUND(AVG(balance),2) FROM customer WHERE balance > 0",
    ),
    ("Max credit balance", "SELECT ROUND(MAX(balance),2) FROM customer"),
    ("Earliest sale", "SELECT MIN(sale_date) FROM credit_sale"),
    ("Latest sale", "SELECT MAX(sale_date) FROM credit_sale"),
    (
        "Revenue last 30d",
        "SELECT ROUND(SUM(i.quantity * i.price_at_sale),2) FROM credit_sale_item i JOIN credit_sale s ON s.id=i.sale_id WHERE s.sale_date >= date('now','-30 days')",
    ),
]


def main():
    t0 = time.time()

    print("=" * 66)
    print("  NexusRetailOS — STEP 3: Seed Validation Report")
    print(f"  DB : {DB_PATH}")
    print(f"  Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 66)

    if not os.path.exists(DB_PATH):
        print(f"\n❌  Database not found: {DB_PATH}")
        print("   Run gen_master_data.py and gen_transactions.py first.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # ── Run checks ─────────────────────────────────────────────────────────
    print(f"\n{'─' * 66}")
    print("  VALIDATION CHECKS")
    print(f"{'─' * 66}")

    passed = 0
    failed = 0
    failures = []

    for chk in CHECKS:
        try:
            result = c.execute(chk["query"].strip()).fetchone()[0]
            ok = chk["check"](result)
        except Exception as e:
            result = f"ERROR: {e}"
            ok = False

        # Format result value for display
        if isinstance(result, float):
            rstr = f"{result:,.2f}"
        elif isinstance(result, int):
            rstr = f"{result:,}"
        else:
            rstr = str(result)

        status = "✅" if ok else "❌"
        label = chk["name"][:45].ljust(46)
        print(f"  {status}  {label} → {rstr:>15}  ({chk['expect']})")

        if ok:
            passed += 1
        else:
            failed += 1
            failures.append((chk["name"], rstr, chk["expect"], chk["hint"]))

    # ── Summary stats ──────────────────────────────────────────────────────
    print(f"\n{'─' * 66}")
    print("  DATABASE SUMMARY")
    print(f"{'─' * 66}")

    for label, query in SUMMARY_QUERIES:
        try:
            val = c.execute(query.strip()).fetchone()[0]
            if isinstance(val, float):
                vstr = f"{val:>18,.2f}"
            elif isinstance(val, int):
                vstr = f"{val:>18,}"
            else:
                vstr = f"{str(val):>18}"
        except Exception as e:
            vstr = f"{'ERROR':>18}"
        print(f"  {label:<28} {vstr}")

    # ── Failure details ────────────────────────────────────────────────────
    if failures:
        print(f"\n{'─' * 66}")
        print("  ❌  FAILED CHECKS — DIAGNOSIS")
        print(f"{'─' * 66}")
        for name, got, expected, hint in failures:
            print(f"\n  Check   : {name}")
            print(f"  Got     : {got}")
            print(f"  Expected: {expected}")
            print(f"  Hint    : {hint}")

    # ── Final verdict ──────────────────────────────────────────────────────
    elapsed = time.time() - t0
    total = passed + failed
    print(f"\n{'═' * 66}")
    if failed == 0:
        print(
            f"  🎉  RESULT: {passed}/{total} checks PASSED — Seed is ML-ready!  ({elapsed:.1f}s)"
        )
    else:
        print(
            f"  ⚠️   RESULT: {passed}/{total} passed, {failed} FAILED.  ({elapsed:.1f}s)"
        )
        print(f"  Re-run after reviewing the hints above.")
    print(f"{'═' * 66}\n")

    conn.close()

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
