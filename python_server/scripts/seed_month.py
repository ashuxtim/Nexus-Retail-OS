import sqlite3
import sys
import os
import time
import numpy as np
from datetime import datetime, timedelta
from core.time_utils import now as tz_now

# ============================================================
# seed_month.py — One Month Realistic Seed for UI/AI Testing
# Designed to exercise all 4 Phase 5 target queries:
#   1. Stockout prediction (chips, cold drinks)
#   2. Market basket / FP-Growth (Maggi combos)
#   3. Customer churn for product buyers (Lays buyers)
#   4. Semantic supplier search
# ============================================================

DAYS_TO_SIMULATE = 30
DAILY_TX_AVG = 80
CHURN_RATE = 0.15
SLOWDOWN_RATE = 0.10
CREDIT_LIMIT = 5000
SALARY_DAYS = [1, 2, 3, 4, 5, 6, 7]
PERCENT_CREDIT_CUSTOMERS = 0.35

if "NEXUS_USER_DATA" in os.environ:
    _BASE = os.environ["NEXUS_USER_DATA"]
elif sys.platform == "win32":
    _BASE = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
else:
    _BASE = os.path.join(os.path.expanduser("~"), ".config", "NexusRetailOS")
DB_PATH = os.path.join(_BASE, "nexus.db")

# ============================================================
# REAL PRODUCTS
# Format: (product_name, category, variant_name, price, opening_stock)
# Opening stock is intentionally LOW for chips/cold drinks
# so stockout predictions fire meaningfully.
# ============================================================
REAL_PRODUCTS = [
    # --- SNACKS (chips — low stock to trigger stockout) ---
    ("Lays",            "Snacks",       "Classic Salted 26g",       20,   18),
    ("Lays",            "Snacks",       "Masala 26g",               20,   14),
    ("Lays",            "Snacks",       "American Cream 26g",       20,   22),
    ("Kurkure",         "Snacks",       "Masala Munch 90g",         30,   12),
    ("Kurkure",         "Snacks",       "Green Chutney 90g",        30,    9),
    ("Bingo",           "Snacks",       "Mad Angles 75g",           20,   16),
    ("Uncle Chips",     "Snacks",       "Spicy Treat 60g",          20,    8),
    ("Haldiram",        "Snacks",       "Aloo Bhujia 200g",         80,   35),

    # --- COLD DRINKS (beverages — mixed stock) ---
    ("Coca Cola",       "Beverages",    "330ml Can",                40,   30),
    ("Coca Cola",       "Beverages",    "2L Bottle",                95,   11),
    ("Pepsi",           "Beverages",    "330ml Can",                40,   25),
    ("Pepsi",           "Beverages",    "2L Bottle",                90,   18),
    ("Sprite",          "Beverages",    "330ml Can",                40,   20),
    ("Thums Up",        "Beverages",    "600ml Bottle",             45,    7),
    ("Maaza",           "Beverages",    "600ml Bottle",             45,   40),
    ("Frooti",          "Beverages",    "200ml Tetrapack",          20,   55),
    ("Limca",           "Beverages",    "300ml Bottle",             35,   15),

    # --- INSTANT FOOD (Maggi — for basket analysis) ---
    ("Maggi",           "Instant Food", "2 Minute Noodles 70g",     14,  120),
    ("Maggi",           "Instant Food", "Masala Noodles 140g",      28,   80),
    ("Yippee",          "Instant Food", "Magic Masala 70g",         12,   60),
    ("Top Ramen",       "Instant Food", "Curry Noodles 70g",        12,   45),

    # --- DAIRY ---
    ("Amul",            "Dairy",        "Milk 500ml Pouch",         30,  200),
    ("Amul",            "Dairy",        "Butter 100g",              56,   40),
    ("Amul",            "Dairy",        "Paneer 200g",             100,   20),
    ("Mother Dairy",    "Dairy",        "Milk 1L",                  58,  150),

    # --- BAKERY ---
    ("Britannia",       "Bakery",       "Bread Brown 400g",         45,   60),
    ("Britannia",       "Bakery",       "Good Day Biscuit 150g",    35,   90),
    ("Parle",           "Bakery",       "G Biscuit 250g",           15,  110),
    ("Sunfeast",        "Bakery",       "Dark Fantasy 75g",         30,   50),

    # --- STAPLES ---
    ("Tata Salt",       "Staples",      "1kg Pack",                 28,  100),
    ("Aashirvaad",      "Staples",      "Atta 5kg",                240,   30),
    ("Fortune",         "Staples",      "Sunflower Oil 1L",        140,   40),

    # --- PERSONAL CARE ---
    ("Lux",             "Personal Care","Rose Soap 100g",           38,   70),
    ("Dove",            "Personal Care","Moisturising Soap 100g",   55,   45),
    ("Colgate",         "Personal Care","Strong Teeth 200g",        90,   55),

    # --- CLEANING ---
    ("Surf Excel",      "Cleaning",     "Washing Powder 1kg",      145,   35),
    ("Vim",             "Cleaning",     "Dishwash Bar 250g",        30,   60),
]

# ============================================================
# REAL CUSTOMERS (Indian names — loyal, churned, at-risk mix)
# ============================================================
REAL_CUSTOMERS = [
    # Regular loyal customers
    ("Rajesh Kumar",        "9812345601", "Sector 4, Rohini"),
    ("Priya Sharma",        "9823456702", "Lajpat Nagar"),
    ("Mohammad Arif",       "9834567803", "Okhla Phase 2"),
    ("Sunita Devi",         "9845678904", "Dwarka Sector 11"),
    ("Amit Verma",          "9856789005", "Pitampura"),
    ("Kavita Singh",        "9867890106", "Janakpuri Block B"),
    ("Ravi Shankar",        "9878901207", "Mayur Vihar Phase 1"),
    ("Deepa Nair",          "9889012308", "Vasant Kunj"),
    ("Suresh Gupta",        "9890123409", "Saket"),
    ("Anita Joshi",         "9801234510", "Nehru Place"),
    ("Vikram Yadav",        "9712345611", "Laxmi Nagar"),
    ("Meena Kumari",        "9723456712", "Shahdara"),
    ("Harpreet Kaur",       "9734567813", "Paschim Vihar"),
    ("Arun Mishra",         "9745678914", "Tilak Nagar"),
    ("Pooja Agarwal",       "9756789015", "Rajouri Garden"),
    ("Sanjay Tiwari",       "9767890116", "Uttam Nagar"),
    ("Rekha Pillai",        "9778901217", "Kalkaji"),
    ("Manoj Dubey",         "9789012318", "Greater Kailash"),
    ("Fatima Begum",        "9790123419", "Jamia Nagar"),
    ("Rahul Bhatt",         "9901234520", "Malviya Nagar"),
    # Credit / Khata customers
    ("Dinesh Chandra",      "9612345621", "Karol Bagh"),
    ("Shanti Prasad",       "9623456722", "Sadar Bazar"),
    ("Lalit Mohan",         "9634567823", "Chandni Chowk"),
    ("Geeta Rawat",         "9645678924", "Model Town"),
    ("Naresh Bansal",       "9656789025", "Wazirpur"),
    # At-risk / slow customers (churn candidates)
    ("Vinod Saxena",        "9567890126", "Burari"),
    ("Kamla Rani",          "9578901227", "Narela"),
    ("Prakash Rao",         "9589012328", "Bawana"),
    ("Usha Tripathi",       "9590123429", "Rohtak Road"),
    ("Bharat Lal",          "9501234530", "Nangloi"),
    # Occasional / light buyers
    ("Sachin Pawar",        "9412345631", "Dwarka Sector 7"),
    ("Nisha Rathi",         "9423456732", "Uttam Nagar West"),
    ("Tarun Khanna",        "9434567833", "Kirti Nagar"),
    ("Savita Mehta",        "9445678934", "Punjabi Bagh"),
    ("Gopal Krishna",       "9456789035", "Ashok Vihar"),
    ("Rani Deshpande",      "9467890136", "Shalimar Bagh"),
    ("Ajay Thakur",         "9478901237", "Tri Nagar"),
    ("Sudha Verma",         "9489012338", "Shakurpur"),
    ("Hemant Chauhan",      "9490123439", "Vikaspuri"),
    ("Pushpa Srivastava",   "9401234540", "Hari Nagar"),
    # Lays-specific buyers
    ("Rohit Lamba",         "9312345641", "Palam"),
    ("Seema Arora",         "9323456742", "Vasant Vihar"),
    ("Kiran Bedi",          "9334567843", "R K Puram"),
    ("Mukesh Garg",         "9345678944", "Safdarjung"),
    ("Ananya Kapoor",       "9356789045", "Hauz Khas"),
    # Maggi-specific buyers
    ("Neha Sood",           "9267890146", "South Ex"),
    ("Rahul Nanda",         "9278901247", "Lodi Colony"),
    ("Tara Chand",          "9289012348", "Andrews Ganj"),
    ("Zara Khan",           "9290123449", "Jangpura"),
    ("Vivek Oberoi",        "9201234550", "Nizamuddin"),
]

# ============================================================
# REAL SUPPLIERS (distributor / company style names)
# ============================================================
REAL_SUPPLIERS = [
    ("PepsiCo India Distributors",      "9111222301", "Okhla Industrial Area, Delhi"),
    ("Frito-Lay North India",           "9111222302", "Sector 63, Noida"),
    ("ITC Snacks Division",             "9111222303", "Sahibabad Industrial Area"),
    ("Haldiram Snacks Pvt Ltd",         "9111222304", "Nagpur Road, Delhi"),
    ("Hindustan Coca-Cola Beverages",   "9222333401", "Vardhman Industrial Estate"),
    ("Varun Beverages Ltd",             "9222333402", "Greater Noida West"),
    ("PepsiCo Beverages India",         "9222333403", "Manesar, Haryana"),
    ("Parle Agro Distributors",         "9222333404", "Andheri East, Mumbai"),
    ("Amul Delhi Distribution Hub",     "9333444501", "Mother Dairy Crossing, Delhi"),
    ("Mother Dairy Fruit & Veg",        "9333444502", "Patparganj, Delhi"),
    ("Verka Milk Products",             "9333444503", "Rajpura, Punjab"),
    ("Britannia Industries Ltd",        "9444555601", "Vikaspuri, Delhi"),
    ("Parle Products Pvt Ltd",          "9444555602", "Santacruz West, Mumbai"),
    ("ITC Sunfeast Division",           "9444555603", "Sahibabad, UP"),
    ("Nestle India Ltd",                "9555666701", "Gurgaon, Haryana"),
    ("ITC Yippee Division",             "9555666702", "Sahibabad Industrial Area"),
    ("Tata Consumer Products",          "9666777801", "Lower Parel, Mumbai"),
    ("ITC Aashirvaad Division",         "9666777802", "Tobacco House, Kolkata"),
    ("Adani Wilmar Ltd",                "9666777803", "Fortune House, Ahmedabad"),
    ("HUL Delhi Distributor",           "9777888901", "Okhla Phase 3, Delhi"),
    ("Colgate-Palmolive India",         "9777888902", "Central Avenue, Mumbai"),
]

# ============================================================
# BASKET COMBOS — product name pairs with strong buy-together
# signal so FP-Growth picks up meaningful association rules.
# ============================================================
BASKET_COMBOS_BY_NAME = [
    ("Maggi",       "Britannia"),
    ("Maggi",       "Tata Salt"),
    ("Maggi",       "Amul"),
    ("Maggi",       "Lux"),
    ("Maggi",       "Parle"),
    ("Lays",        "Coca Cola"),
    ("Lays",        "Pepsi"),
    ("Lays",        "Kurkure"),
    ("Coca Cola",   "Lays"),
    ("Pepsi",       "Kurkure"),
    ("Sprite",      "Haldiram"),
    ("Britannia",   "Amul"),
    ("Britannia",   "Mother Dairy"),
]


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-64000;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def create_tables(conn):
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS product (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT
        );
        CREATE TABLE IF NOT EXISTS product_variant (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            unit TEXT DEFAULT 'Unit',
            current_stock REAL DEFAULT 0,
            FOREIGN KEY(product_id) REFERENCES product(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS customer (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            mobile TEXT,
            address TEXT,
            balance REAL DEFAULT 0,
            next_payment_date TEXT
        );
        CREATE TABLE IF NOT EXISTS credit_sale (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            sale_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(customer_id) REFERENCES customer(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS credit_sale_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            price_at_sale REAL NOT NULL,
            FOREIGN KEY(sale_id) REFERENCES credit_sale(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS payment (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER NOT NULL,
            payment_date TEXT DEFAULT CURRENT_TIMESTAMP,
            amount REAL NOT NULL,
            FOREIGN KEY(customer_id) REFERENCES customer(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS supplier (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            mobile TEXT,
            address TEXT,
            is_deleted INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS purchase_invoice (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            supplier_id INTEGER,
            invoice_date TEXT DEFAULT CURRENT_TIMESTAMP,
            total_amount REAL NOT NULL,
            reference_number TEXT,
            FOREIGN KEY(supplier_id) REFERENCES supplier(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS purchase_item (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_id INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            quantity REAL NOT NULL,
            unit_cost REAL NOT NULL,
            FOREIGN KEY(invoice_id) REFERENCES purchase_invoice(id) ON DELETE CASCADE
        );
    """)
    conn.commit()


def seed_data():
    start_time = time.time()
    conn = get_connection()
    create_tables(conn)
    c = conn.cursor()
    rng = np.random.default_rng(42)

    print("🚀 seed_month.py — Seeding 1 Month of Realistic Data")
    print(f"   DB: {DB_PATH}")

    # --------------------------------------------------------
    # 1. SUPPLIERS
    # --------------------------------------------------------
    print("\n📦 Inserting suppliers...")
    for name, mobile, address in REAL_SUPPLIERS:
        c.execute(
            "INSERT OR IGNORE INTO supplier (name, mobile, address) VALUES (?, ?, ?)",
            (name, mobile, address)
        )
    conn.commit()

    supplier_rows = c.execute("SELECT id, name FROM supplier").fetchall()
    supplier_ids = np.array([r[0] for r in supplier_rows], dtype=np.int64)

    supplier_map = {}
    for sid, sname in supplier_rows:
        for keyword in ["pepsico", "frito", "itc", "haldiram", "coca-cola", "varun",
                        "parle agro", "amul", "mother dairy", "verka", "britannia",
                        "parle products", "nestle", "tata", "adani", "hul", "colgate"]:
            if keyword in sname.lower():
                supplier_map.setdefault(keyword, sid)

    print(f"   ✅ {len(supplier_rows)} suppliers ready.")

    # --------------------------------------------------------
    # 2. PRODUCTS + VARIANTS
    # --------------------------------------------------------
    print("\n🛒 Inserting products and variants...")

    product_id_map = {}
    variant_id_map = {}

    for prod_name, category, variant_name, price, opening_stock in REAL_PRODUCTS:
        c.execute(
            "INSERT OR IGNORE INTO product (name, category) VALUES (?, ?)",
            (prod_name, category)
        )
        c.execute("SELECT id FROM product WHERE name = ?", (prod_name,))
        pid = c.fetchone()[0]
        product_id_map[prod_name] = pid

        c.execute(
            "INSERT OR IGNORE INTO product_variant (product_id, name, price, current_stock) VALUES (?, ?, ?, ?)",
            (pid, variant_name, price, opening_stock)
        )
        c.execute(
            "SELECT id FROM product_variant WHERE product_id = ? AND name = ?",
            (pid, variant_name)
        )
        vid = c.fetchone()[0]
        variant_id_map[(prod_name, variant_name)] = vid

    conn.commit()

    variants_data = c.execute("SELECT id, price FROM product_variant").fetchall()
    all_variant_ids = np.array([r[0] for r in variants_data], dtype=np.int64)
    variant_price_map = {r[0]: r[1] for r in variants_data}

    vid_to_product = {vid: pname for (pname, _), vid in variant_id_map.items()}

    print(f"   ✅ {len(product_id_map)} products, {len(variant_id_map)} variants ready.")

    # --------------------------------------------------------
    # 3. CUSTOMERS
    # --------------------------------------------------------
    print("\n👥 Inserting customers...")
    for name, mobile, address in REAL_CUSTOMERS:
        c.execute(
            "INSERT OR IGNORE INTO customer (name, mobile, address) VALUES (?, ?, ?)",
            (name, mobile, address)
        )
    conn.commit()

    customer_rows = c.execute("SELECT id, name FROM customer").fetchall()
    customer_ids = np.array([r[0] for r in customer_rows], dtype=np.int64)
    customer_name_map = {r[0]: r[1] for r in customer_rows}

    print(f"   ✅ {len(customer_rows)} customers ready.")

    # --------------------------------------------------------
    # 4. BASKET COMBOS — resolve product names → variant id lists
    # --------------------------------------------------------
    combo_vid_pairs = []
    for prod_a, prod_b in BASKET_COMBOS_BY_NAME:
        vids_a = [vid for (pn, _), vid in variant_id_map.items() if pn == prod_a]
        vids_b = [vid for (pn, _), vid in variant_id_map.items() if pn == prod_b]
        if vids_a and vids_b:
            combo_vid_pairs.append((vids_a, vids_b))

    # --------------------------------------------------------
    # 5. CHURN / SLOWDOWN ASSIGNMENT
    # --------------------------------------------------------
    now = tz_now()
    churn_map = {}
    slow_map = {}

    churn_names = {"Vinod Saxena", "Kamla Rani", "Prakash Rao",
                   "Usha Tripathi", "Bharat Lal", "Sachin Pawar", "Nisha Rathi", "Tarun Khanna"}
    for cid, cname in customer_rows:
        if cname in churn_names:
            churn_map[cid] = now - timedelta(days=int(rng.integers(40, 90)))

    slow_names = {"Savita Mehta", "Gopal Krishna", "Rani Deshpande"}
    for cid, cname in customer_rows:
        if cname in slow_names:
            slow_map[cid] = now - timedelta(days=int(rng.integers(20, 45)))

    credit_names = {"Dinesh Chandra", "Shanti Prasad", "Lalit Mohan", "Geeta Rawat",
                    "Naresh Bansal", "Rajesh Kumar", "Amit Verma", "Ravi Shankar", "Suresh Gupta"}
    is_credit_customer = {
        cid: (customer_name_map[cid] in credit_names)
        for cid in customer_ids
    }

    # --------------------------------------------------------
    # 6. PRODUCT-SPECIFIC BUYER GROUPS
    # --------------------------------------------------------
    lays_buyer_names = {"Rohit Lamba", "Seema Arora", "Kiran Bedi",
                        "Mukesh Garg", "Ananya Kapoor", "Rajesh Kumar", "Amit Verma"}
    lays_buyer_ids = {cid for cid, cname in customer_rows if cname in lays_buyer_names}
    lays_variant_ids = [vid for (pn, _), vid in variant_id_map.items() if pn == "Lays"]

    maggi_buyer_names = {"Neha Sood", "Rahul Nanda", "Tara Chand",
                         "Zara Khan", "Vivek Oberoi", "Priya Sharma", "Kavita Singh"}
    maggi_buyer_ids = {cid for cid, cname in customer_rows if cname in maggi_buyer_names}
    maggi_variant_ids = [vid for (pn, _), vid in variant_id_map.items() if pn == "Maggi"]

    # --------------------------------------------------------
    # 7. SIMULATION
    # --------------------------------------------------------
    print(f"\n⏳ Simulating {DAYS_TO_SIMULATE} days of transactions...")

    start_date = now - timedelta(days=DAYS_TO_SIMULATE)

    inventory = {}
    for prod_name, category, variant_name, price, opening_stock in REAL_PRODUCTS:
        vid = variant_id_map.get((prod_name, variant_name))
        if vid:
            inventory[vid] = float(opening_stock)

    cust_debt = {cid: 0.0 for cid in customer_ids}

    sale_id_counter = c.execute("SELECT IFNULL(MAX(id), 0) FROM credit_sale").fetchone()[0]
    inv_id_counter = c.execute("SELECT IFNULL(MAX(id), 0) FROM purchase_invoice").fetchone()[0]

    sales_q, items_q, purchases_q, p_items_q, payments_q = [], [], [], [], []
    BATCH_SIZE = 5

    for day in range(DAYS_TO_SIMULATE):
        current_date = start_date + timedelta(days=day)
        date_str = current_date.strftime("%Y-%m-%d %H:%M:%S")
        day_of_month = current_date.day
        is_salary_week = day_of_month in SALARY_DAYS
        is_weekend = current_date.weekday() >= 5

        tx_count = int(rng.normal(DAILY_TX_AVG * (1.3 if is_weekend else 1.0), 8))
        tx_count = max(tx_count, 10)

        potential = rng.choice(customer_ids, size=min(int(tx_count * 1.5), len(customer_ids)), replace=False)
        valid_cids = []
        for cid in potential:
            if len(valid_cids) >= tx_count:
                break
            if cid in churn_map and current_date > churn_map[cid]:
                continue
            if cid in slow_map and current_date > slow_map[cid] and rng.random() < 0.7:
                continue
            valid_cids.append(cid)

        restock_needs = []

        for cid in valid_cids:
            sale_id_counter += 1
            sales_q.append((sale_id_counter, int(cid), date_str))

            basket_vids = []

            if cid in lays_buyer_ids and lays_variant_ids:
                basket_vids.append(int(rng.choice(lays_variant_ids)))

            if cid in maggi_buyer_ids and maggi_variant_ids:
                basket_vids.append(int(rng.choice(maggi_variant_ids)))

            if combo_vid_pairs and rng.random() < 0.35:
                pair = combo_vid_pairs[rng.integers(0, len(combo_vid_pairs))]
                basket_vids.append(int(rng.choice(pair[0])))
                basket_vids.append(int(rng.choice(pair[1])))

            extra = rng.integers(0, 3)
            if extra > 0:
                basket_vids.extend([int(v) for v in rng.choice(all_variant_ids, size=int(extra))])

            if not basket_vids:
                basket_vids.append(int(rng.choice(all_variant_ids)))

            basket_vids = list(dict.fromkeys(basket_vids))

            total_bill = 0.0
            for vid in basket_vids:
                qty = float(rng.integers(1, 4))
                price = variant_price_map[vid]
                total_bill += qty * price
                items_q.append((sale_id_counter, vid, qty, price))

                if vid in inventory:
                    inventory[vid] -= qty
                    if inventory[vid] < 5:
                        restock_qty = float(30 + rng.integers(0, 30))
                        inventory[vid] += restock_qty
                        restock_needs.append((vid, restock_qty, price * 0.72))

            if not is_credit_customer[cid]:
                payments_q.append((int(cid), date_str, float(total_bill)))
            else:
                cust_debt[cid] += total_bill
                if cust_debt[cid] > CREDIT_LIMIT:
                    excess = cust_debt[cid] - CREDIT_LIMIT
                    pay_amt = min(excess + float(rng.uniform(300, 1000)), cust_debt[cid])
                    cust_debt[cid] -= pay_amt
                    payments_q.append((int(cid), date_str, float(pay_amt)))
                elif is_salary_week and cust_debt[cid] > 200:
                    if rng.random() < 0.80:
                        payments_q.append((int(cid), date_str, float(cust_debt[cid])))
                        cust_debt[cid] = 0.0

        if restock_needs:
            supp_batches = {}
            for vid, qty, cost in restock_needs:
                pname = vid_to_product.get(vid, "").lower()
                assigned_sid = None
                for kw, sid in supplier_map.items():
                    if kw in pname:
                        assigned_sid = sid
                        break
                if assigned_sid is None:
                    assigned_sid = int(rng.choice(supplier_ids))
                supp_batches.setdefault(assigned_sid, []).append((vid, qty, cost))

            for sid, items in supp_batches.items():
                inv_id_counter += 1
                total_amt = sum(x[1] * x[2] for x in items)
                inv_date = (current_date - timedelta(hours=int(rng.integers(1, 24)))).strftime("%Y-%m-%d %H:%M:%S")
                purchases_q.append((inv_id_counter, int(sid), inv_date, float(total_amt)))
                for vid, qty, cost in items:
                    p_items_q.append((inv_id_counter, vid, float(qty), float(cost)))

        if day % BATCH_SIZE == 0 or day == DAYS_TO_SIMULATE - 1:
            if sales_q:
                c.executemany(
                    "INSERT INTO credit_sale (id, customer_id, sale_date) VALUES (?, ?, ?)",
                    sales_q
                )
                c.executemany(
                    "INSERT INTO credit_sale_item (sale_id, variant_id, quantity, price_at_sale) VALUES (?, ?, ?, ?)",
                    items_q
                )
                sales_q.clear()
                items_q.clear()
            if payments_q:
                c.executemany(
                    "INSERT INTO payment (customer_id, payment_date, amount) VALUES (?, ?, ?)",
                    payments_q
                )
                payments_q.clear()
            if purchases_q:
                c.executemany(
                    "INSERT INTO purchase_invoice (id, supplier_id, invoice_date, total_amount) VALUES (?, ?, ?, ?)",
                    purchases_q
                )
                c.executemany(
                    "INSERT INTO purchase_item (invoice_id, variant_id, quantity, unit_cost) VALUES (?, ?, ?, ?)",
                    p_items_q
                )
                purchases_q.clear()
                p_items_q.clear()
            conn.commit()
            print(f"   🗓️  Day {day + 1}/{DAYS_TO_SIMULATE} committed.")

    # --------------------------------------------------------
    # 8. FINALIZE
    # --------------------------------------------------------
    print("\n💾 Finalizing balances and stock levels...")

    c.executemany(
        "UPDATE customer SET balance = ? WHERE id = ?",
        [(round(b, 2), cid) for cid, b in cust_debt.items() if b > 0]
    )
    c.executemany(
        "UPDATE product_variant SET current_stock = ? WHERE id = ?",
        [(max(0.0, round(s, 1)), vid) for vid, s in inventory.items()]
    )
    conn.commit()

    # --------------------------------------------------------
    # 9. SUMMARY
    # --------------------------------------------------------
    total_sales = c.execute("SELECT COUNT(*) FROM credit_sale").fetchone()[0]
    total_items = c.execute("SELECT COUNT(*) FROM credit_sale_item").fetchone()[0]
    total_invoices = c.execute("SELECT COUNT(*) FROM purchase_invoice").fetchone()[0]
    low_stock = c.execute(
        "SELECT COUNT(*) FROM product_variant WHERE current_stock < 15"
    ).fetchone()[0]

    print("\n" + "=" * 55)
    print("✅ SEED COMPLETE — Summary")
    print("=" * 55)
    print(f"   Products   : {len(product_id_map)} ({len(variant_id_map)} variants)")
    print(f"   Customers  : {len(customer_rows)}")
    print(f"   Suppliers  : {len(supplier_rows)}")
    print(f"   Sales      : {total_sales} transactions")
    print(f"   Items sold : {total_items} line items")
    print(f"   Purchases  : {total_invoices} supplier invoices")
    print(f"   Low stock  : {low_stock} variants below 15 units ⚠️")
    print(f"   Duration   : {time.time() - start_time:.1f}s")
    print("=" * 55)

    print("\n🔧 Optimizing database...")
    conn.execute("VACUUM;")
    conn.execute("ANALYZE;")
    conn.close()
    print("✅ Done. Run the app and start testing.\n")


if __name__ == "__main__":
    seed_data()