import sqlite3
import os
import time
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from core.time_utils import now as tz_now
from faker import Faker

# ================= CONFIG =================
YEARS_TO_SIMULATE = 10
CUSTOMERS_TARGET = 5000
PRODUCTS_TARGET = 5000
SUPPLIERS_TARGET = 1000
DAILY_TX_AVG = 500
CHURN_RATE = 0.05
SLOWDOWN_RATE = 0.10
MARKET_BASKET_PAIRS = 50

# REALISM TWEAKS
PERCENT_CREDIT_CUSTOMERS = 0.30  # Only 30% people have "Khata"
CREDIT_LIMIT = 5000  # Max debt allowed before forced payment
SALARY_DAYS = [1, 2, 3, 4, 5, 6, 7]  # Days of month when people clear debts

if "NEXUS_USER_DATA" in os.environ:
    _BASE = os.environ["NEXUS_USER_DATA"]
elif sys.platform == "win32":
    _BASE = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
else:
    _BASE = os.path.join(os.path.expanduser("~"), ".config", "NexusRetailOS")
DB_PATH = os.path.join(_BASE, "nexus.db")

fake = Faker("en_IN")

CATEGORIES = [
    "Dairy",
    "Bakery",
    "Beverages",
    "Snacks",
    "Staples",
    "Personal Care",
    "Cleaning",
    "Spices",
    "Instant Food",
    "Frozen",
    "Health",
    "Baby Care",
    "Pet Food",
]
REAL_PRODUCTS = [
    ("Amul Milk 500ml", "Dairy", 34),
    ("Britannia Bread", "Bakery", 45),
    ("Coca Cola 2L", "Beverages", 95),
    ("Lays Classic Salted", "Snacks", 20),
    ("Tata Salt 1kg", "Staples", 28),
    ("Lux Soap", "Personal Care", 38),
    ("Surf Excel 1kg", "Cleaning", 145),
    ("Maggi Noodles", "Instant Food", 14),
    ("Aashirvaad Atta 5kg", "Staples", 240),
    ("Amul Butter 100g", "Dairy", 56),
]


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    # Speed Optimizations
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-64000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def create_tables(conn):
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS product (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, category TEXT);
        CREATE TABLE IF NOT EXISTS product_variant (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, name TEXT NOT NULL, price REAL NOT NULL, unit TEXT DEFAULT 'Unit', current_stock REAL DEFAULT 0, FOREIGN KEY(product_id) REFERENCES product(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS customer (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, mobile TEXT, address TEXT, balance REAL DEFAULT 0, next_payment_date TEXT);
        CREATE TABLE IF NOT EXISTS credit_sale (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL, sale_date TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(customer_id) REFERENCES customer(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS credit_sale_item (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, variant_id INTEGER NOT NULL, quantity REAL NOT NULL, price_at_sale REAL NOT NULL, FOREIGN KEY(sale_id) REFERENCES credit_sale(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS payment (id INTEGER PRIMARY KEY AUTOINCREMENT, customer_id INTEGER NOT NULL, payment_date TEXT DEFAULT CURRENT_TIMESTAMP, amount REAL NOT NULL, FOREIGN KEY(customer_id) REFERENCES customer(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS supplier (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, mobile TEXT, address TEXT, is_deleted INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS purchase_invoice (id INTEGER PRIMARY KEY AUTOINCREMENT, supplier_id INTEGER, invoice_date TEXT DEFAULT CURRENT_TIMESTAMP, total_amount REAL NOT NULL, reference_number TEXT, FOREIGN KEY(supplier_id) REFERENCES supplier(id) ON DELETE SET NULL);
        CREATE TABLE IF NOT EXISTS purchase_item (id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER NOT NULL, variant_id INTEGER NOT NULL, quantity REAL NOT NULL, unit_cost REAL NOT NULL, FOREIGN KEY(invoice_id) REFERENCES purchase_invoice(id) ON DELETE CASCADE);
    """)
    conn.commit()


def seed_data():
    start_time = time.time()
    conn = get_connection()
    create_tables(conn)
    c = conn.cursor()
    rng = np.random.default_rng()

    print(f"🚀 Starting Realism Update Seed: {YEARS_TO_SIMULATE} Years")

    # --- 1. Static Data ---
    curr_supp = c.execute("SELECT COUNT(*) FROM supplier").fetchone()[0]
    if curr_supp < SUPPLIERS_TARGET:
        batch = []
        for _ in range(SUPPLIERS_TARGET - curr_supp):
            batch.append(
                (
                    f"{fake.company()} Traders",
                    f"9{rng.integers(100000000, 999999999)}",
                    fake.address().replace("\n", ", "),
                )
            )
        c.executemany(
            "INSERT OR IGNORE INTO supplier (name, mobile, address) VALUES (?, ?, ?)",
            batch,
        )
        conn.commit()

    supplier_ids = np.array(
        [r[0] for r in c.execute("SELECT id FROM supplier").fetchall()], dtype=np.int64
    )

    curr_prod = c.execute("SELECT COUNT(*) FROM product").fetchone()[0]
    if curr_prod < PRODUCTS_TARGET:
        batch_p = []
        if curr_prod == 0:
            for n, cat, p in REAL_PRODUCTS:
                batch_p.append((n, cat, p))
        needed = PRODUCTS_TARGET - curr_prod - len(batch_p)
        if needed > 0:
            cats = rng.choice(CATEGORIES, size=needed)
            prices = rng.integers(20, 2000, size=needed)
            for i in range(needed):
                batch_p.append(
                    (
                        f"{fake.word().capitalize()} {cats[i]} {rng.integers(100, 999)}",
                        cats[i],
                        float(prices[i]),
                    )
                )

        for name, cat, price in batch_p:
            c.execute(
                "INSERT OR IGNORE INTO product (name, category) VALUES (?, ?)",
                (name, cat),
            )

            # --- THE FIX: Force SQLite to give you the REAL ID ---
            c.execute("SELECT id FROM product WHERE name = ?", (name,))
            row = c.fetchone()

            if row:
                pid = row[0]
                # Only add variant if we have a valid Product ID
                c.execute(
                    "INSERT OR IGNORE INTO product_variant (product_id, name, price, current_stock) VALUES (?, 'Standard', ?, 0)",
                    (pid, price),
                )

        conn.commit()

    variants_data = c.execute("SELECT id, price FROM product_variant").fetchall()
    variant_ids = np.array([r[0] for r in variants_data], dtype=np.int64)
    variant_prices = {r[0]: r[1] for r in variants_data}

    curr_cust = c.execute("SELECT COUNT(*) FROM customer").fetchone()[0]
    if curr_cust < CUSTOMERS_TARGET:
        batch_c = []
        for i in range(CUSTOMERS_TARGET - curr_cust):
            batch_c.append(
                (
                    f"{fake.first_name()} {fake.last_name()} {rng.integers(1,9999)}",
                    f"9{rng.integers(100000000, 999999999)}",
                    fake.city(),
                )
            )
        c.executemany(
            "INSERT OR IGNORE INTO customer (name, mobile, address) VALUES (?, ?, ?)",
            batch_c,
        )
        conn.commit()

    customer_ids = np.array(
        [r[0] for r in c.execute("SELECT id FROM customer").fetchall()], dtype=np.int64
    )

    # --- 2. Simulation Setup ---
    print("⚙️  Calculating Logic...")

    # Assign "Khata Enabled" Status to 30% of customers
    is_credit_customer = {
        cid: (rng.random() < PERCENT_CREDIT_CUSTOMERS) for cid in customer_ids
    }

    # Churn & Slowdown
    now = tz_now()
    churn_map = {}
    slow_map = {}

    num_churn = int(len(customer_ids) * CHURN_RATE)
    num_slow = int(len(customer_ids) * SLOWDOWN_RATE)
    indices = np.arange(len(customer_ids))
    rng.shuffle(indices)

    for idx in indices[:num_churn]:
        churn_map[customer_ids[idx]] = now - timedelta(days=int(rng.integers(60, 540)))

    remaining = indices[num_churn:]
    for idx in remaining[:num_slow]:
        slow_map[customer_ids[idx]] = now - timedelta(days=int(rng.integers(90, 180)))

    combos = []
    if len(variant_ids) >= 2:
        for _ in range(MARKET_BASKET_PAIRS):
            combos.append(rng.choice(variant_ids, size=2, replace=False))

    start_date = now - timedelta(days=YEARS_TO_SIMULATE * 365)
    total_days = (now - start_date).days

    print(f"⏳ Simulating {total_days} days...")

    inventory = {vid: 0.0 for vid in variant_ids}
    cust_debt = {cid: 0.0 for cid in customer_ids}

    sale_id_start = c.execute("SELECT IFNULL(MAX(id), 0) FROM credit_sale").fetchone()[
        0
    ]
    inv_id_start = c.execute(
        "SELECT IFNULL(MAX(id), 0) FROM purchase_invoice"
    ).fetchone()[0]
    current_sale_id = sale_id_start
    current_inv_id = inv_id_start

    # Pre-calc daily volume
    days_range = np.arange(total_days)
    start_weekday = start_date.weekday()
    weekdays = (days_range + start_weekday) % 7
    is_weekend = weekdays >= 5
    means = np.where(is_weekend, DAILY_TX_AVG * 1.3, DAILY_TX_AVG)
    daily_tx_counts = np.maximum(5, rng.normal(means, 10).astype(int))

    sales_q, items_q, purchases_q, p_items_q, payments_q = [], [], [], [], []
    BATCH_SIZE = 50

    for day in range(total_days):
        current_date = start_date + timedelta(days=day)
        date_str = current_date.strftime("%Y-%m-%d %H:%M:%S")
        day_of_month = current_date.day
        is_salary_week = day_of_month in SALARY_DAYS

        tx_count = daily_tx_counts[day]
        potential_cids = rng.choice(customer_ids, size=int(tx_count * 1.5))

        valid_cids = []
        for cid in potential_cids:
            if len(valid_cids) >= tx_count:
                break
            if cid in churn_map and current_date > churn_map[cid]:
                continue
            if cid in slow_map and current_date > slow_map[cid] and rng.random() < 0.8:
                continue
            valid_cids.append(cid)

        restock_needs = []

        for cid in valid_cids:
            current_sale_id += 1
            sales_q.append((current_sale_id, int(cid), date_str))

            # Basket
            basket_size = 1 + rng.integers(0, 4)
            basket_vids = [rng.choice(variant_ids)]
            if combos and rng.random() < 0.3:
                basket_vids.extend(combos[rng.integers(0, len(combos))])
            if basket_size > 1:
                basket_vids.extend(rng.choice(variant_ids, size=basket_size - 1))

            total_bill = 0.0
            for vid in basket_vids:
                qty = float(rng.integers(1, 4))
                price = variant_prices[vid]
                total_bill += qty * price
                items_q.append((current_sale_id, int(vid), qty, price))

                inventory[vid] -= qty
                if inventory[vid] < 10:
                    restock = float(50 + rng.integers(0, 51))
                    inventory[vid] += restock
                    restock_needs.append((vid, restock, price * 0.75))

            # --- REALISTIC PAYMENT LOGIC ---

            # 1. Non-Credit Customer? Pay Immediately.
            if not is_credit_customer[cid]:
                payments_q.append((int(cid), date_str, float(total_bill)))
                # Balance stays 0 (Bill added to debt, payment removes it instantly)

            # 2. Credit Customer?
            else:
                cust_debt[cid] += total_bill  # Add new bill to debt

                # Rule A: Hard Limit (Debt > 5000) -> Pay enough to go below limit
                if cust_debt[cid] > CREDIT_LIMIT:
                    # They pay the excess + some extra
                    excess = cust_debt[cid] - CREDIT_LIMIT
                    pay_amt = excess + rng.uniform(500, 2000)
                    pay_amt = min(pay_amt, cust_debt[cid])  # Can't overpay
                    cust_debt[cid] -= pay_amt
                    payments_q.append((int(cid), date_str, float(pay_amt)))

                # Rule B: Salary Week (First 7 days of month) -> Clear full debt
                elif is_salary_week and cust_debt[cid] > 500:
                    if rng.random() < 0.85:  # 85% chance they clear debt on salary week
                        pay_amt = cust_debt[cid]
                        cust_debt[cid] = 0
                        payments_q.append((int(cid), date_str, float(pay_amt)))

        # Process Restocks
        if restock_needs:
            supp_batches = {}
            for vid, qty, cost in restock_needs:
                sid = rng.choice(supplier_ids)
                if sid not in supp_batches:
                    supp_batches[sid] = []
                supp_batches[sid].append((vid, qty, cost))

            for sid, items in supp_batches.items():
                current_inv_id += 1
                total_amt = sum(x[1] * x[2] for x in items)
                inv_date = (
                    current_date - timedelta(hours=int(rng.integers(2, 48)))
                ).strftime("%Y-%m-%d %H:%M:%S")
                purchases_q.append((current_inv_id, int(sid), inv_date, total_amt))
                for vid, qty, cost in items:
                    p_items_q.append((current_inv_id, int(vid), qty, cost))

        # Batch Commit
        if day % BATCH_SIZE == 0:
            if sales_q:
                c.executemany(
                    "INSERT INTO credit_sale (id, customer_id, sale_date) VALUES (?, ?, ?)",
                    sales_q,
                )
                c.executemany(
                    "INSERT INTO credit_sale_item (sale_id, variant_id, quantity, price_at_sale) VALUES (?, ?, ?, ?)",
                    items_q,
                )
                sales_q.clear()
                items_q.clear()
            if payments_q:
                c.executemany(
                    "INSERT INTO payment (customer_id, payment_date, amount) VALUES (?, ?, ?)",
                    payments_q,
                )
                payments_q.clear()
            if purchases_q:
                c.executemany(
                    "INSERT INTO purchase_invoice (id, supplier_id, invoice_date, total_amount) VALUES (?, ?, ?, ?)",
                    purchases_q,
                )
                c.executemany(
                    "INSERT INTO purchase_item (invoice_id, variant_id, quantity, unit_cost) VALUES (?, ?, ?, ?)",
                    p_items_q,
                )
                purchases_q.clear()
                p_items_q.clear()
            conn.commit()
            if day % 100 == 0:
                print(f"   🗓️  Day {day}/{total_days}")

    # Final Flush
    if sales_q:
        c.executemany(
            "INSERT INTO credit_sale (id, customer_id, sale_date) VALUES (?, ?, ?)",
            sales_q,
        )
    if items_q:
        c.executemany(
            "INSERT INTO credit_sale_item (sale_id, variant_id, quantity, price_at_sale) VALUES (?, ?, ?, ?)",
            items_q,
        )
    if payments_q:
        c.executemany(
            "INSERT INTO payment (customer_id, payment_date, amount) VALUES (?, ?, ?)",
            payments_q,
        )
    if purchases_q:
        c.executemany(
            "INSERT INTO purchase_invoice (id, supplier_id, invoice_date, total_amount) VALUES (?, ?, ?, ?)",
            purchases_q,
        )
    if p_items_q:
        c.executemany(
            "INSERT INTO purchase_item (invoice_id, variant_id, quantity, unit_cost) VALUES (?, ?, ?, ?)",
            p_items_q,
        )
    conn.commit()

    print("💾 Finalizing Balances...")
    # Update final customer balances
    c.executemany(
        "UPDATE customer SET balance = ? WHERE id = ?",
        [(b, cid) for cid, b in cust_debt.items() if b > 0],
    )
    # Update inventory
    c.executemany(
        "UPDATE product_variant SET current_stock = ? WHERE id = ?",
        [(s, v) for v, s in inventory.items()],
    )
    conn.commit()

    end_time = time.time()
    print(f"✅ Realism Simulation Complete in {end_time - start_time:.2f} seconds.")

    print("🔧 Optimizing database (VACUUM + ANALYZE)...")
    conn.execute("VACUUM;")
    conn.execute("ANALYZE;")
    print("✅ Database optimized!")

    conn.close()


if __name__ == "__main__":
    seed_data()
