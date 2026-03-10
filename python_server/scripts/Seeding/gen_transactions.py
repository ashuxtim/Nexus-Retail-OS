#!/usr/bin/env python3
"""
gen_transactions.py  —  NexusRetailOS 10-Year Seed  (Step 2 of 3)
Reads:   nexus_seed_maps.json  (written by gen_master_data.py)
Writes:  credit_sale, credit_sale_item, payment, purchase_invoice, purchase_item
Finalizes: customer.balance (bulk UPDATE), product_variant.current_stock

Run standalone:  python gen_transactions.py
Or via master:   from gen_transactions import main; main()

Expected runtime: 20–50 minutes depending on hardware.
Progress printed every 365 days (1 year).
"""

import os, sys, json, sqlite3, time, math
import numpy as np
import random
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════════
#  PATH RESOLUTION  (mirrors gen_master_data.py)
# ═══════════════════════════════════════════════════════════════════════════
if "NEXUS_USER_DATA" in os.environ:
    BASE_DIR = os.environ["NEXUS_USER_DATA"]
elif sys.platform == "win32":
    BASE_DIR = os.path.join(os.getenv("APPDATA"), "NexusRetailOS")
else:
    BASE_DIR = os.path.join(os.path.expanduser("~"), ".config", "NexusRetailOS")

DB_PATH   = os.path.join(BASE_DIR, "nexus.db")
MAPS_PATH = os.path.join(BASE_DIR, "nexus_seed_maps.json")

PAYMENT_MODES = ['Cash', 'UPI', 'Card', 'Bank Transfer']
PAYMENT_WEIGHTS = [50, 30, 15, 5]

RNG_SEED    = 42
TOTAL_DAYS  = 3650
BATCH_DAYS  = 30   # commit every N days

# ═══════════════════════════════════════════════════════════════════════════
#  LOAD MAPS
# ═══════════════════════════════════════════════════════════════════════════
def load_maps():
    if not os.path.exists(MAPS_PATH):
        raise FileNotFoundError(
            f"nexus_seed_maps.json not found at {MAPS_PATH}.\n"
            "Run gen_master_data.py first."
        )
    with open(MAPS_PATH) as f:
        raw = json.load(f)

    # Convert string keys → int where needed
    maps = dict(raw)
    maps["variant_price_map"]       = {int(k): v for k, v in raw["variant_price_map"].items()}
    maps["variant_opening_stock"]   = {int(k): v for k, v in raw["variant_opening_stock"].items()}
    maps["variant_to_product_name"] = {int(k): v for k, v in raw["variant_to_product_name"].items()}
    maps["variant_to_category"]     = {int(k): v for k, v in raw["variant_to_category"].items()}
    maps["variant_reorder_point"]   = {int(k): v for k, v in raw["variant_reorder_point"].items()}
    maps["credit_limits"]           = {int(k): v for k, v in raw["credit_limits"].items()}
    maps["customer_join_day"]       = {int(k): v for k, v in raw["customer_join_day"].items()}
    maps["customer_segments"]       = {int(k): v for k, v in raw["customer_segments"].items()}
    maps["churn_days"]              = {int(k): v for k, v in raw["churn_days"].items()}
    maps["temp_churn"]              = {int(k): v for k, v in raw["temp_churn"].items()}
    maps["supplier_category_map"]   = {int(k): v for k, v in raw["supplier_category_map"].items()}
    maps["category_to_variant_ids"] = {k: [int(x) for x in v] for k, v in raw["category_to_variant_ids"].items()}
    maps["product_name_to_variant_ids"] = {k: [int(x) for x in v] for k, v in raw["product_name_to_variant_ids"].items()}
    maps["all_variant_ids"]         = [int(x) for x in raw["all_variant_ids"]]
    maps["customer_ids"]            = [int(x) for x in raw["customer_ids"]]
    maps["credit_customer_ids"]     = [int(x) for x in raw["credit_customer_ids"]]
    maps["supplier_ids"]            = [int(x) for x in raw["supplier_ids"]]
    # Combo pairs: list of [[vid,...],[vid,...]]
    maps["combo_pairs"] = [
        [[int(x) for x in pa], [int(x) for x in pb]]
        for pa, pb in raw["combo_pairs"]
    ]
    return maps


# ═══════════════════════════════════════════════════════════════════════════
#  PRE-COMPUTE NUMPY STATE ARRAYS  (vectorized eligibility per day)
# ═══════════════════════════════════════════════════════════════════════════
def build_state(maps, rng):
    cids        = np.array(maps["customer_ids"], dtype=np.int64)
    n           = len(cids)
    credit_set  = set(maps["credit_customer_ids"])

    # visit lambda per day per segment
    SEG_LAMBDA = {"loyal": 0.26, "credit": 0.16, "occasional": 0.07, "at_risk": 0.12}

    lambda_arr    = np.array([SEG_LAMBDA.get(maps["customer_segments"].get(int(c), "occasional"), 0.07) for c in cids], dtype=np.float64)
    join_arr      = np.array([maps["customer_join_day"].get(int(c), 0) for c in cids], dtype=np.int32)
    churn_arr     = np.array([maps["churn_days"].get(int(c), 9999) for c in cids], dtype=np.int32)
    tc_start_arr  = np.array([maps["temp_churn"].get(int(c), [-1, -1])[0] for c in cids], dtype=np.int32)
    tc_end_arr    = np.array([maps["temp_churn"].get(int(c), [-1, -1])[1] for c in cids], dtype=np.int32)
    is_credit_arr = np.array([1 if int(c) in credit_set else 0 for c in cids], dtype=np.int8)

    # At-risk customers: lambda decays over simulation
    at_risk_mask = np.array(
        [1 if maps["customer_segments"].get(int(c), "") == "at_risk" else 0 for c in cids], dtype=np.int8
    )

    state = {
        "cids":          cids,
        "lambda_arr":    lambda_arr,
        "join_arr":      join_arr,
        "churn_arr":     churn_arr,
        "tc_start_arr":  tc_start_arr,
        "tc_end_arr":    tc_end_arr,
        "is_credit_arr": is_credit_arr,
        "at_risk_mask":  at_risk_mask,
        # Running credit balances (in-memory, written to DB at end)
        "cust_debt":     {int(c): 0.0 for c in cids},
        # Inventory (variant_id → current float stock)
        "inventory":     dict(maps["variant_opening_stock"]),
        # ID counters (we INSERT with explicit ids to avoid autoincrement conflicts)
        "sale_counter":  0,
        "inv_counter":   0,
        # Per-supplier invoice sequence
        "inv_seq":       {},
    }
    return state


# ═══════════════════════════════════════════════════════════════════════════
#  DAILY TRANSACTION COUNT  — S-Curve (logistic) + modifiers
# ═══════════════════════════════════════════════════════════════════════════
def daily_tx_count(day_idx, current_date, rng):
    """Returns integer transaction target for this day."""
    L  = 1000.0    # max capacity
    k  = 0.0012    # growth steepness
    t0 = 1825.0    # inflection at year 5

    base = L / (1.0 + math.exp(-k * (day_idx - t0)))
    # base: ~152 at day 0  →  ~848 at day 3649

    m = current_date.month
    d = current_date.day
    wd = current_date.weekday()   # 0=Mon … 6=Sun

    # Weekend +30%
    if wd >= 5:
        base *= 1.30

    # Monthly salary week boost (days 1-7) +20%
    if d <= 7:
        base *= 1.20

    # Festival boosts
    if (m == 10 and d >= 15) or (m == 11 and d <= 15):
        base *= 1.45   # Diwali
    elif m == 3 and 5 <= d <= 25:
        base *= 1.30   # Holi
    elif m == 1 and d <= 10:
        base *= 1.25   # New Year
    elif m in [6, 7] and 10 <= d <= 25:
        base *= 1.20   # Eid approximate

    # COVID suppression: Apr 2020 ≈ day 1490  →  Oct 2020 ≈ day 1675
    if 1490 <= day_idx <= 1675:
        base *= 0.38
    elif 1675 < day_idx <= 1900:
        recovery = (day_idx - 1675) / 225.0
        base *= (0.38 + 0.62 * recovery)

    # Noise ±10%
    noise = float(rng.normal(0, base * 0.10))
    count = int(base + noise)
    return max(40, min(1100, count))


# ═══════════════════════════════════════════════════════════════════════════
#  HISTORICAL PRICE  —  deflate price ~7% per year for old records
# ═══════════════════════════════════════════════════════════════════════════
def historical_price(current_price, years_ago, rng):
    """Price N years ago was lower due to inflation."""
    if years_ago <= 0:
        return round(float(current_price), 2)
    inflation = float(rng.uniform(0.063, 0.078))
    price = current_price / ((1.0 + inflation) ** years_ago)
    # Snap to nearest ₹0.50 for realism
    price = round(price * 2) / 2.0
    return max(1.0, round(price, 2))


# ═══════════════════════════════════════════════════════════════════════════
#  BASKET BUILDER  —  combo-aware, category-affinity, seasonal
# ═══════════════════════════════════════════════════════════════════════════
# Pre-built combo lookup: product_name → (prob, partner_vids_list)
STRONG_COMBOS = [
    # (product_keyword_A, product_keyword_B, probability)
    ("Maggi",    "Britannia",    0.38),
    ("Maggi",    "Amul",         0.35),
    ("Maggi",    "Tata Salt",    0.28),
    ("Lays",     "Coca Cola",    0.40),
    ("Lays",     "Pepsi",        0.35),
    ("Lays",     "Kurkure",      0.30),
    ("Kurkure",  "Pepsi",        0.32),
    ("Sprite",   "Haldiram",     0.25),
    ("Britannia","Mother Dairy", 0.35),
    ("Parle",    "Amul",         0.28),
    ("Tata Salt","Aashirvaad",   0.40),
    ("Fortune",  "Aashirvaad",   0.35),
    ("Colgate",  "Lux",          0.22),
    ("Top Ramen","Yippee",       0.28),
    ("Biscuit",  "Amul",         0.25),
]

CAT_AFFINITY = [
    # If basket has cat_A, add item from cat_B with given prob
    ("Snacks",       "Beverages",         0.52),
    ("Dairy",        "Bakery",            0.42),
    ("Staples",      "Staples",           0.30),
    ("Personal Care","Cleaning",          0.35),
    ("Instant Food", "Dairy",             0.30),
    ("Bakery",       "Dairy",             0.38),
    ("Confectionery","Beverages",         0.28),
]


def build_basket(cid, day_idx, current_date, maps, rng):
    """Return list of unique variant_ids for this customer's basket."""
    basket = []
    all_vids     = maps["all_variant_ids"]
    cat_vids     = maps["category_to_variant_ids"]
    prod_vids    = maps["product_name_to_variant_ids"]
    categories   = maps["categories"]

    # 1. Preferred category (deterministic per customer + slight drift over years)
    # Sticky primary category per customer (never rotates)
    pref_cat_idx    = cid % len(categories)
    pref_cat        = categories[pref_cat_idx]
    # Sticky secondary category (adjacent — gives cross-category signal)
    secondary_cat   = categories[(pref_cat_idx + 1) % len(categories)]

    pref_vids = cat_vids.get(pref_cat, [])
    if pref_vids:
        n_pref = int(rng.integers(2, 5))   # slightly more from preferred cat
        for _ in range(n_pref):
            basket.append(int(rng.choice(pref_vids)))

    sec_vids = cat_vids.get(secondary_cat, [])
    if sec_vids and rng.random() < 0.55:   # 55% chance to also buy from secondary
        basket.append(int(rng.choice(sec_vids)))

    # 2. Combo affinity
    basket_products = set()
    for vid in basket:
        pname = maps["variant_to_product_name"].get(vid, "")
        basket_products.add(pname.lower())

    basket_cats = set(maps["variant_to_category"].get(v, "") for v in basket)

    # Also match on category name so combos fire even without exact brand match
    basket_cats_lower = set(c.lower() for c in basket_cats)

    for kw_a, kw_b, prob in STRONG_COMBOS:
        a_match = any(kw_a.lower() in bp for bp in basket_products) or \
                any(kw_a.lower() in bc for bc in basket_cats_lower)
        if a_match:
            if rng.random() < prob:
                partner_vids = []
                for pname, vids_list in prod_vids.items():
                    if kw_b.lower() in pname.lower():
                        partner_vids.extend(vids_list)
                if partner_vids:
                    basket.append(int(rng.choice(partner_vids)))

    # 3. Category affinity
    
    for cat_a, cat_b, prob in CAT_AFFINITY:
        if cat_a in basket_cats and rng.random() < prob:
            vids_b = cat_vids.get(cat_b, [])
            if vids_b:
                basket.append(int(rng.choice(vids_b)))

    # Random items scoped to preferred + secondary category only (not all 10k)
    scoped_pool = pref_vids + sec_vids if sec_vids else pref_vids
    if not scoped_pool:
        scoped_pool = all_vids

    n_random = int(rng.integers(1, 3))   # reduced from 2-6 to 1-2
    for _ in range(n_random):
        basket.append(int(rng.choice(scoped_pool)))

    # One truly random item (keeps some noise, but controlled)
    if rng.random() < 0.25:
        basket.append(int(rng.choice(all_vids)))

    # 5. Seasonal boost
    m = current_date.month
    if m in [4, 5, 6]:            # Summer → more beverages
        bev = cat_vids.get("Beverages", [])
        if bev and rng.random() < 0.45:
            basket.append(int(rng.choice(bev)))
    elif m in [11, 12, 1]:        # Winter → more staples/dairy
        sta = cat_vids.get("Staples", [])
        if sta and rng.random() < 0.35:
            basket.append(int(rng.choice(sta)))
        dai = cat_vids.get("Dairy", [])
        if dai and rng.random() < 0.30:
            basket.append(int(rng.choice(dai)))
    elif m in [10, 11]:           # Diwali → confectionery + staples
        conf = cat_vids.get("Confectionery", [])
        if conf and rng.random() < 0.40:
            basket.append(int(rng.choice(conf)))

    # 6. Deduplicate, ensure ≥1 item, cap at 18
    basket = list(dict.fromkeys(basket))
    if not basket:
        basket = [int(rng.choice(all_vids))]
    return basket[:18]


# ═══════════════════════════════════════════════════════════════════════════
#  PAYMENT HANDLER
# ═══════════════════════════════════════════════════════════════════════════
def handle_payment(cid, total_bill, current_date, maps, state, rng, payments_batch):
    """
    Decides payment amount. Updates state['cust_debt'] in-place.
    Appends to payments_batch if a payment is made.
    """
    is_credit = int(cid) in set(maps["credit_customer_ids"])

    if not is_credit:
        # Cash customer: always pays in full at time of purchase
        t = current_date
        dstr = f"{t.strftime('%Y-%m-%d')} {rng.integers(8,21):02d}:{rng.integers(0,60):02d}:{rng.integers(0,60):02d}"
        payments_batch.append((int(cid), dstr, round(float(total_bill), 2), random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[0]))
        return

    # Credit customer: add to running debt
    state["cust_debt"][int(cid)] += total_bill
    debt         = state["cust_debt"][int(cid)]
    limit        = maps["credit_limits"].get(int(cid), 15000.0)
    m_day        = current_date.day
    is_sal_week  = m_day <= 7
    is_fest_mo   = current_date.month in [10, 11, 1, 3]

    pay_amount   = 0.0
    t            = current_date
    dstr         = f"{t.strftime('%Y-%m-%d')} {rng.integers(8,21):02d}:{rng.integers(0,60):02d}:00"

    # Rule 1: Exceeded credit limit → force immediate partial payment
    if debt > limit:
        excess     = debt - limit
        extra      = float(rng.uniform(300, 2500))
        pay_amount = min(excess + extra, debt)

    # Rule 2: Salary week + significant debt → high probability of clearance
    elif is_sal_week and debt > 400:
        prob = 0.72 + (0.10 if is_fest_mo else 0.0)
        if rng.random() < prob:
            fraction   = float(rng.uniform(0.50, 1.00))
            pay_amount = round(debt * fraction, 2)

    # Rule 3: Hard ceiling — debt > ₹80,000 → emergency sweep
    if debt > 80000:
        target_after = float(rng.uniform(10000, 25000))
        pay_amount   = max(pay_amount, debt - target_after)

    if pay_amount > 0:
        pay_amount = min(round(pay_amount, 2), debt)
        state["cust_debt"][int(cid)] -= pay_amount
        state["cust_debt"][int(cid)]  = max(0.0, state["cust_debt"][int(cid)])
        payments_batch.append((int(cid), dstr, pay_amount, random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[0]))


def handle_spontaneous_payments(day_idx, current_date, maps, state, rng, payments_batch):
    """
    8% daily chance: credit customer visits only to pay their debt.
    Festival months boost to 14%.
    """
    is_fest = current_date.month in [10, 11, 1, 3]
    prob    = 0.14 if is_fest else 0.08
    t       = current_date
    base_dstr = t.strftime("%Y-%m-%d")

    for cid in maps["credit_customer_ids"]:
        debt = state["cust_debt"].get(int(cid), 0.0)
        if debt < 100.0:
            continue
        if rng.random() < prob:
            fraction   = float(rng.uniform(0.25, 1.00))
            pay_amount = round(min(debt * fraction, debt), 2)
            if pay_amount < 1.0:
                continue
            state["cust_debt"][int(cid)] -= pay_amount
            state["cust_debt"][int(cid)]  = max(0.0, state["cust_debt"][int(cid)])
            dstr = f"{base_dstr} {rng.integers(9,18):02d}:{rng.integers(0,60):02d}:00"
            payments_batch.append((int(cid), dstr, pay_amount, random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[0]))


def handle_yearend_sweep(current_date, maps, state, rng, payments_batch):
    """Dec 31 each year: high-balance customers pay down 60-90%."""
    dstr = current_date.strftime("%Y-%m-%d 23:59:00")
    for cid in maps["credit_customer_ids"]:
        debt = state["cust_debt"].get(int(cid), 0.0)
        if debt > 15000:
            fraction   = float(rng.uniform(0.60, 0.92))
            pay_amount = round(debt * fraction, 2)
            state["cust_debt"][int(cid)] -= pay_amount
            state["cust_debt"][int(cid)]  = max(0.0, state["cust_debt"][int(cid)])
            payments_batch.append((int(cid), dstr, pay_amount, random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[0]))


# ═══════════════════════════════════════════════════════════════════════════
#  RESTOCK → PURCHASE INVOICES
# ═══════════════════════════════════════════════════════════════════════════
def group_restocks_into_invoices(restock_needs, current_date, state, maps, rng,
                                  invoices_batch, p_items_batch):
    """
    Group restock items by supplier → one purchase_invoice per supplier.
    restock_needs: list of (variant_id, qty, unit_cost)
    """
    # Deduplicate by variant (keep max qty)
    vmap = {}
    for vid, qty, cost in restock_needs:
        if vid not in vmap or qty > vmap[vid][0]:
            vmap[vid] = (qty, cost)

    # Assign variant → supplier by category match
    sup_batches = {}
    for vid, (qty, cost) in vmap.items():
        cat = maps["variant_to_category"].get(int(vid), "")
        assigned = None
        for sid, cats in maps["supplier_category_map"].items():
            if cat in cats:
                assigned = int(sid)
                break
        if assigned is None:
            assigned = int(rng.choice(maps["supplier_ids"]))
        sup_batches.setdefault(assigned, []).append((vid, qty, cost))

    for sid, items in sup_batches.items():
        state["inv_counter"] += 1
        inv_id    = state["inv_counter"]
        total_amt = sum(q * c for _, q, c in items)

        # Invoice arrives before shop opens
        inv_hour  = int(rng.integers(4, 8))
        inv_time  = current_date.replace(
            hour=inv_hour,
            minute=int(rng.integers(0, 60)),
            second=int(rng.integers(0, 60))
        )
        inv_dstr  = inv_time.strftime("%Y-%m-%d %H:%M:%S")

        # Reference number
        seq       = state["inv_seq"].get(sid, 0) + 1
        state["inv_seq"][sid] = seq
        ref_no    = f"INV-{inv_time.year}{inv_time.month:02d}-{sid:04d}-{seq:05d}"

        invoices_batch.append((inv_id, sid, inv_dstr, round(float(total_amt), 2), ref_no))
        for vid, qty, cost in items:
            p_items_batch.append((inv_id, int(vid), float(qty), float(cost)))


# ═══════════════════════════════════════════════════════════════════════════
#  FLUSH BATCH TO DB
# ═══════════════════════════════════════════════════════════════════════════
def flush_batches(conn, c, sales_q, items_q, payments_q, invoices_q, p_items_q):
    if sales_q:
        c.executemany(
            "INSERT INTO credit_sale (id, customer_id, sale_date) VALUES (?,?,?)",
            sales_q
        )
        c.executemany(
            "INSERT INTO credit_sale_item (sale_id, variant_id, quantity, price_at_sale) VALUES (?,?,?,?)",
            items_q
        )
    if payments_q:
        c.executemany(
            "INSERT INTO payment (customer_id, payment_date, amount, payment_mode) VALUES (?,?,?,?)",
            payments_q
        )
    if invoices_q:
        c.executemany(
            "INSERT INTO purchase_invoice (id, supplier_id, invoice_date, total_amount, reference_number) VALUES (?,?,?,?,?)",
            invoices_q
        )
        c.executemany(
            "INSERT INTO purchase_item (invoice_id, variant_id, quantity, unit_cost) VALUES (?,?,?,?)",
            p_items_q
        )
    conn.commit()
    sales_q.clear();  items_q.clear();  payments_q.clear()
    invoices_q.clear(); p_items_q.clear()


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN SIMULATION LOOP
# ═══════════════════════════════════════════════════════════════════════════
def main():
    t0  = time.time()
    rng = np.random.default_rng(RNG_SEED)

    print("=" * 64)
    print("  NexusRetailOS — STEP 2: Transaction Simulation (10 years)")
    print(f"  DB: {DB_PATH}")
    print("=" * 64)

    # ── Guard ──────────────────────────────────────────────────────────────
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-128000;")
    conn.execute("PRAGMA foreign_keys=OFF;")

    existing_sales = conn.execute("SELECT COUNT(*) FROM credit_sale").fetchone()[0]
    if existing_sales > 1000:
        print(f"\n⚠️  Already {existing_sales:,} sales in DB. Skipping simulation.")
        print("   Delete nexus.db and re-run gen_master_data.py to re-seed.")
        conn.close()
        return

    # ── Load maps & build state ────────────────────────────────────────────
    print("\n📂  Loading maps…")
    maps  = load_maps()
    state = build_state(maps, rng)

    cids          = state["cids"]
    lambda_arr    = state["lambda_arr"]
    join_arr      = state["join_arr"]
    churn_arr     = state["churn_arr"]
    tc_start_arr  = state["tc_start_arr"]
    tc_end_arr    = state["tc_end_arr"]
    is_credit_arr = state["is_credit_arr"]
    at_risk_mask  = state["at_risk_mask"]
    n_cust        = len(cids)

    credit_id_set = set(maps["credit_customer_ids"])
    all_vids_arr  = np.array(maps["all_variant_ids"], dtype=np.int64)
    n_vids        = len(all_vids_arr)

    # Start date = 10 years ago from today
    START_DATE = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=TOTAL_DAYS)
    print(f"   Simulation: {START_DATE.strftime('%Y-%m-%d')} → {(START_DATE + timedelta(days=TOTAL_DAYS-1)).strftime('%Y-%m-%d')}")
    print(f"   Customers : {n_cust:,}  |  Variants: {n_vids:,}  |  Days: {TOTAL_DAYS:,}")
    print(f"\n⏳  Simulating… (progress every 365 days)\n")

    c = conn.cursor()

    # Batch lists
    sales_q    = []
    items_q    = []
    payments_q = []
    invoices_q = []
    p_items_q  = []

    year_sales = 0
    year_items = 0
    total_sales = 0

    # ── Day loop ───────────────────────────────────────────────────────────
    for day_idx in range(TOTAL_DAYS):
        current_date = START_DATE + timedelta(days=day_idx)
        years_ago    = (TOTAL_DAYS - day_idx) / 365.0

        # ── Vectorised eligibility mask ────────────────────────────────────
        eff_lambda = lambda_arr.copy()

        # At-risk customers: linear decay from full to 15% of original
        if np.any(at_risk_mask):
            decay_factor = max(0.15, 1.0 - (day_idx / TOTAL_DAYS) * 0.85)
            eff_lambda  += at_risk_mask * (eff_lambda * (decay_factor - 1.0))

        # COVID suppression of visit probability
        if 1490 <= day_idx <= 1675:
            eff_lambda *= 0.40
        elif 1675 < day_idx <= 1900:
            rec = (day_idx - 1675) / 225.0
            eff_lambda *= (0.40 + 0.60 * rec)

        eligible_mask = (
            (join_arr <= day_idx) &
            (churn_arr > day_idx) &
            ~((tc_start_arr <= day_idx) & (tc_end_arr >= day_idx))
        )

        rand_vals    = rng.random(n_cust)
        visitor_mask = eligible_mask & (rand_vals < eff_lambda)

        # Sample up to daily target
        target       = daily_tx_count(day_idx, current_date, rng)
        visitor_idxs = np.where(visitor_mask)[0]

        if len(visitor_idxs) > target:
            visitor_idxs = rng.choice(visitor_idxs, size=target, replace=False)
        elif len(visitor_idxs) < int(target * 0.6) and len(visitor_idxs) < n_cust:
            # Supplement from eligible non-visitors to approach target
            eligible_idxs  = np.where(eligible_mask)[0]
            non_visitor    = np.setdiff1d(eligible_idxs, visitor_idxs)
            shortfall      = min(int(target * 0.6) - len(visitor_idxs), len(non_visitor))
            if shortfall > 0:
                extra = rng.choice(non_visitor, size=shortfall, replace=False)
                visitor_idxs = np.concatenate([visitor_idxs, extra])

        # ── Per-buyer loop ─────────────────────────────────────────────────
        restock_needs = []

        for idx in visitor_idxs:
            cid = int(cids[idx])

            state["sale_counter"] += 1
            sale_id = state["sale_counter"]

            # Sale timestamp within shop hours (8 AM – 9 PM)
            sale_hour   = int(rng.integers(8, 21))
            sale_min    = int(rng.integers(0, 60))
            sale_sec    = int(rng.integers(0, 60))
            sale_dt     = current_date.replace(hour=sale_hour, minute=sale_min, second=sale_sec)
            sale_dstr   = sale_dt.strftime("%Y-%m-%d %H:%M:%S")

            sales_q.append((sale_id, cid, sale_dstr))

            # Build basket
            basket = build_basket(cid, day_idx, current_date, maps, rng)

            total_bill = 0.0
            for vid in basket:
                qty   = float(rng.integers(1, 5))
                cprice = maps["variant_price_map"].get(vid, 20.0)
                price  = historical_price(cprice, years_ago, rng)
                total_bill += qty * price
                items_q.append((sale_id, vid, qty, price))
                year_items += 1

                # Inventory update
                old_stock = state["inventory"].get(vid, 0.0)
                new_stock = old_stock - qty
                state["inventory"][vid] = new_stock

                # Restock trigger
                rp = maps["variant_reorder_point"].get(vid, 8.0)
                if new_stock < rp:
                    restock_qty  = float(rng.integers(40, 130))
                    unit_cost    = round(cprice * float(rng.uniform(0.65, 0.78)), 2)
                    restock_needs.append((vid, restock_qty, unit_cost))
                    state["inventory"][vid] = new_stock + restock_qty

            # Payment decision
            handle_payment(cid, total_bill, sale_dt, maps, state, rng, payments_q)
            year_sales += 1
            total_sales += 1

        # Spontaneous debt payments
        handle_spontaneous_payments(day_idx, current_date, maps, state, rng, payments_q)

        # Year-end balance sweep
        if current_date.month == 12 and current_date.day == 31:
            handle_yearend_sweep(current_date, maps, state, rng, payments_q)

        # Restock → invoices
        if restock_needs:
            group_restocks_into_invoices(
                restock_needs, current_date, state, maps, rng, invoices_q, p_items_q
            )

        # Flush every BATCH_DAYS
        if (day_idx + 1) % BATCH_DAYS == 0:
            flush_batches(conn, c, sales_q, items_q, payments_q, invoices_q, p_items_q)

        # Annual progress report
        if (day_idx + 1) % 365 == 0:
            year_num  = (day_idx + 1) // 365
            elapsed   = time.time() - t0
            remaining = elapsed / (day_idx + 1) * (TOTAL_DAYS - day_idx - 1)
            print(
                f"   ✅ Year {year_num:2d} complete | Day {day_idx+1:4d}/{TOTAL_DAYS} | "
                f"Sales this year: {year_sales:6,} | "
                f"ETA: {remaining/60:.1f} min"
            )
            year_sales = 0
            year_items = 0

    # Final flush for remaining days
    flush_batches(conn, c, sales_q, items_q, payments_q, invoices_q, p_items_q)

    # ── Finalise balances & stock ──────────────────────────────────────────
    print("\n💾  Finalising customer balances (bulk UPDATE)…")
    balance_updates = [
        (round(max(0.0, b), 2), cid)
        for cid, b in state["cust_debt"].items()
    ]
    c.executemany("UPDATE customer SET balance = ? WHERE id = ?", balance_updates)
    conn.commit()

    print("💾  Finalising product stock levels…")
    FAST_MOVER_KWS = [
        "maggi","lays","kurkure","coca cola","pepsi","sprite","frooti","maaza",
        "amul","britannia","bisleri","thums up","mountain dew","yippee","top ramen",
    ]
    stock_updates = []
    for vid, raw_stock in state["inventory"].items():
        pname = maps["variant_to_product_name"].get(int(vid), "").lower()
        is_fast = any(kw in pname for kw in FAST_MOVER_KWS)
        if is_fast:
            # Intentionally low → triggers stockout alerts in Monte Carlo
            final_stock = float(rng.integers(3, 20))
        else:
            final_stock = max(0.0, round(float(raw_stock), 1))
        stock_updates.append((final_stock, int(vid)))

    c.executemany("UPDATE product_variant SET current_stock = ? WHERE id = ?", stock_updates)
    conn.commit()

    # ── Build indexes now (AFTER all inserts — much faster) ───────────────
    print("📑  Creating indexes (post-insert, faster)…")
    for sql in [
        "CREATE INDEX IF NOT EXISTS idx_credit_sale_customer_date ON credit_sale(customer_id, sale_date DESC);",
        "CREATE INDEX IF NOT EXISTS idx_sale_date ON credit_sale(sale_date);",
        "CREATE INDEX IF NOT EXISTS idx_item_sale ON credit_sale_item(sale_id);",
        "CREATE INDEX IF NOT EXISTS idx_sale_item_variant ON credit_sale_item(variant_id);",
        "CREATE INDEX IF NOT EXISTS idx_payment_customer_date ON payment(customer_id, payment_date DESC);",
        "CREATE INDEX IF NOT EXISTS idx_customer_balance ON customer(balance);",
        "CREATE INDEX IF NOT EXISTS idx_customer_payment_date ON customer(next_payment_date);",
        "CREATE INDEX IF NOT EXISTS idx_customer_name ON customer(name);",
        "CREATE INDEX IF NOT EXISTS idx_customer_mobile ON customer(mobile);",
        "CREATE INDEX IF NOT EXISTS idx_purchase_invoice_date_desc ON purchase_invoice(invoice_date DESC, supplier_id);",
        "CREATE INDEX IF NOT EXISTS idx_purchase_invoice_supplier_date ON purchase_invoice(supplier_id, invoice_date DESC);",
        "CREATE INDEX IF NOT EXISTS idx_purchase_item_invoice ON purchase_item(invoice_id);",
        "CREATE INDEX IF NOT EXISTS idx_purchase_item_variant ON purchase_item(variant_id);",
        "CREATE INDEX IF NOT EXISTS idx_supplier_name ON supplier(name);",
        "CREATE INDEX IF NOT EXISTS idx_supplier_mobile ON supplier(mobile);",
        "CREATE INDEX IF NOT EXISTS idx_supplier_is_deleted ON supplier(is_deleted);",
        "CREATE INDEX IF NOT EXISTS idx_product_name ON product(name);",
        "CREATE INDEX IF NOT EXISTS idx_variant_name ON product_variant(name);",
        "CREATE INDEX IF NOT EXISTS idx_variant_product ON product_variant(product_id);",
    ]:
        conn.execute(sql)
    conn.commit()

    # ── VACUUM + ANALYZE ───────────────────────────────────────────────────
    print("🔧  Running VACUUM…  (this may take a few minutes)")
    conn.execute("VACUUM;")
    print("🔧  Running ANALYZE…")
    conn.execute("ANALYZE;")
    conn.commit()

    # ── Summary ────────────────────────────────────────────────────────────
    total_s = c.execute("SELECT COUNT(*) FROM credit_sale").fetchone()[0]
    total_i = c.execute("SELECT COUNT(*) FROM credit_sale_item").fetchone()[0]
    total_p = c.execute("SELECT COUNT(*) FROM payment").fetchone()[0]
    total_v = c.execute("SELECT COUNT(*) FROM purchase_invoice").fetchone()[0]
    elapsed = time.time() - t0

    conn.close()

    print(f"\n{'=' * 64}")
    print(f"  ✅  STEP 2 COMPLETE  ({elapsed/60:.1f} min)")
    print(f"     Sales     : {total_s:>12,}")
    print(f"     Items sold: {total_i:>12,}")
    print(f"     Payments  : {total_p:>12,}")
    print(f"     Invoices  : {total_v:>12,}")
    print(f"{'=' * 64}\n")


if __name__ == "__main__":
    main()
