import sqlite3
import sys
import os
import time
import random  # Standard random for simple stuff
import numpy as np  # Numpy for weighted choices
from datetime import datetime, timedelta
from core.time_utils import now as tz_now
from faker import Faker

# ==============================================================================
# CONFIGURATION
# ==============================================================================
NEW_CUSTOMERS_RANGE = (1, 10)
DAILY_SALES_RANGE = (1000, 1500)
PAYMENT_PROBABILITY = 0.35
MARKET_BASKET_PROB = 0.40
CHURN_SIMULATION_RATE = 0.05

if "NEXUS_USER_DATA" in os.environ:
    _BASE = os.environ["NEXUS_USER_DATA"]
elif sys.platform == "win32":
    _BASE = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
else:
    _BASE = os.path.join(os.path.expanduser("~"), ".config", "NexusRetailOS")
DB_PATH = os.path.join(_BASE, "nexus.db")

fake = Faker("en_IN")
rng = np.random.default_rng()


# ==============================================================================
# HELPERS
# ==============================================================================
def get_connection():
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Run seed_database.py first!"
        )
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def get_current_stock(conn):
    cur = conn.cursor()
    cur.execute("SELECT id, current_stock, price FROM product_variant")
    return {row[0]: {"stock": row[1], "price": row[2]} for row in cur.fetchall()}


def get_existing_ids(conn, table):
    cur = conn.cursor()
    cur.execute(f"SELECT id FROM {table}")
    return [row[0] for row in cur.fetchall()]


# ==============================================================================
# MAIN SIMULATION
# ==============================================================================
def run_daily_update():
    print(f"🚀 Starting Daily Simulation for: {tz_now().strftime('%Y-%m-%d')}")
    start_time = time.time()
    conn = get_connection()
    cur = conn.cursor()

    # 1. READ STATE
    customer_ids = get_existing_ids(conn, "customer")
    supplier_ids = get_existing_ids(conn, "supplier")
    inventory_map = get_current_stock(conn)
    variant_ids = list(inventory_map.keys())

    if not customer_ids or not variant_ids:
        print(
            "❌ Error: Database seems empty. Please run the full 'seed_database.py' first."
        )
        return

    # Combo Logic
    combos = []
    if len(variant_ids) > 2:
        for _ in range(50):
            # Ensure native Python ints
            pair = rng.choice(variant_ids, size=2, replace=False)
            combos.append([int(p) for p in pair])

    today_str = tz_now().strftime("%Y-%m-%d %H:%M:%S")

    # ---------------------------------------------------------
    # STEP 1: NEW ACQUISITION
    # ---------------------------------------------------------
    # FIX: Cast numpy int to Python int
    num_new = int(rng.integers(NEW_CUSTOMERS_RANGE[0], NEW_CUSTOMERS_RANGE[1] + 1))

    new_cust_batch = []
    for _ in range(num_new):
        new_cust_batch.append(
            (
                f"{fake.first_name()} {fake.last_name()} {random.randint(1000,9999)}",
                f"9{random.randint(100000000, 999999999)}",
                fake.city(),
            )
        )

    if new_cust_batch:
        cur.executemany(
            "INSERT INTO customer (name, mobile, address) VALUES (?, ?, ?)",
            new_cust_batch,
        )
        print(f"   Make: Added {num_new} new customers.")

        # FIX: Explicitly cast num_new to int for SQLite LIMIT clause
        cur.execute("SELECT id FROM customer ORDER BY id DESC LIMIT ?", (int(num_new),))
        new_ids = [r[0] for r in cur.fetchall()]
        customer_ids.extend(new_ids)

    # ---------------------------------------------------------
    # STEP 2: SALES VOLUME
    # ---------------------------------------------------------
    target_sales = int(rng.integers(DAILY_SALES_RANGE[0], DAILY_SALES_RANGE[1] + 1))

    sales_buffer = []
    items_buffer = []
    payments_buffer = []
    debt_updates = {}

    churn_blacklist = set(
        [
            int(c)
            for c in rng.choice(
                customer_ids,
                size=int(len(customer_ids) * CHURN_SIMULATION_RATE),
                replace=False,
            )
        ]
    )

    print(f"   Make: Simulating {target_sales} transactions...")

    total_sales_generated = 0

    while total_sales_generated < target_sales:
        batch_size = min(100, target_sales - total_sales_generated)

        # Pick shoppers (avoiding churn blacklist)
        available_shoppers = [c for c in customer_ids if c not in churn_blacklist]
        if not available_shoppers:
            break

        # FIX: Ensure shoppers are native ints
        shoppers_np = rng.choice(available_shoppers, size=batch_size * 2)
        shoppers = [int(c) for c in shoppers_np][:batch_size]

        if not shoppers:
            break

        for cid in shoppers:
            # Basket Building
            basket = [int(rng.choice(variant_ids))]

            if random.random() < MARKET_BASKET_PROB and combos:
                chosen_combo = random.choice(combos)
                if basket[0] in chosen_combo:
                    basket.append(
                        chosen_combo[1]
                        if basket[0] == chosen_combo[0]
                        else chosen_combo[0]
                    )
                else:
                    basket.extend(chosen_combo)

            if random.random() < 0.5:
                extras_count = int(rng.integers(1, 4))
                extras = [int(v) for v in rng.choice(variant_ids, size=extras_count)]
                basket.extend(extras)

            # Insert Sale
            cur.execute(
                "INSERT INTO credit_sale (customer_id, sale_date) VALUES (?, ?)",
                (cid, today_str),
            )
            sale_id = cur.lastrowid

            current_bill = 0.0

            for vid in basket:
                # FIX: Types
                qty = float(rng.integers(1, 4))
                price = inventory_map[vid]["price"]
                total_line = qty * price
                current_bill += total_line

                items_buffer.append((sale_id, vid, qty, price))

                # Update Memory Stock
                inventory_map[vid]["stock"] -= qty

            # Debt Logic
            debt_updates[cid] = debt_updates.get(cid, 0.0) + current_bill

            if random.random() < PAYMENT_PROBABILITY:
                payment_amt = current_bill + random.uniform(0, 500)
                payments_buffer.append((cid, today_str, round(payment_amt, 2)))
                debt_updates[cid] -= payment_amt

        total_sales_generated += batch_size

        if items_buffer:
            cur.executemany(
                "INSERT INTO credit_sale_item (sale_id, variant_id, quantity, price_at_sale) VALUES (?, ?, ?, ?)",
                items_buffer,
            )
            items_buffer = []

    if payments_buffer:
        cur.executemany(
            "INSERT INTO payment (customer_id, payment_date, amount) VALUES (?, ?, ?)",
            payments_buffer,
        )
        print(f"   Make: Recorded {len(payments_buffer)} payments (XGBoost Signal).")

    # ---------------------------------------------------------
    # STEP 3: RESTOCKING
    # ---------------------------------------------------------
    restock_list = []
    for vid, data in inventory_map.items():
        if data["stock"] < 20:
            restock_list.append(vid)

    if restock_list:
        print(f"   Make: Restocking {len(restock_list)} low-inventory items...")

        orders = {}
        for vid in restock_list:
            sid = int(rng.choice(supplier_ids))
            if sid not in orders:
                orders[sid] = []

            base_cost = inventory_map[vid]["price"] * 0.6
            mc_variance = rng.normal(0, base_cost * 0.05)
            final_cost = max(1.0, base_cost + mc_variance)

            # FIX: Types
            qty = int(rng.integers(50, 200))
            orders[sid].append((vid, qty, final_cost))

            inventory_map[vid]["stock"] += qty

        for sid, items in orders.items():
            total_inv = sum(x[1] * x[2] for x in items)
            cur.execute(
                "INSERT INTO purchase_invoice (supplier_id, invoice_date, total_amount) VALUES (?, ?, ?)",
                (sid, today_str, total_inv),
            )
            inv_id = cur.lastrowid

            p_items = [(inv_id, v, q, c) for v, q, c in items]
            cur.executemany(
                "INSERT INTO purchase_item (invoice_id, variant_id, quantity, unit_cost) VALUES (?, ?, ?, ?)",
                p_items,
            )

    # ---------------------------------------------------------
    # STEP 4: COMMIT
    # ---------------------------------------------------------
    print("   Sync: Updating Balances & Inventory...")

    # Update balances
    # We must ensure all values in debt_updates are native types
    balance_update_list = [
        (float(change), int(cid))
        for cid, change in debt_updates.items()
        if abs(change) > 0.01
    ]
    if balance_update_list:
        cur.executemany(
            "UPDATE customer SET balance = balance + ? WHERE id = ?",
            balance_update_list,
        )

    # Update inventory
    stock_update_list = [
        (float(data["stock"]), int(vid)) for vid, data in inventory_map.items()
    ]
    if stock_update_list:
        cur.executemany(
            "UPDATE product_variant SET current_stock = ? WHERE id = ?",
            stock_update_list,
        )

    conn.commit()
    conn.execute("PRAGMA optimize;")

    duration = time.time() - start_time
    print(f"✅ Daily Simulation Complete in {duration:.2f}s.")
    conn.close()


if __name__ == "__main__":
    try:
        run_daily_update()
    except Exception as e:
        print(f"❌ Error: {e}")
        input("Press Enter to exit...")
