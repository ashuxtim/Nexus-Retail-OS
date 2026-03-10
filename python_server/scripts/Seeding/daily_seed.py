#!/usr/bin/env python3
"""
daily_seed.py  —  NexusRetailOS Daily Transaction Seeder
═══════════════════════════════════════════════════════════════════
Inserts one day of realistic sales for TODAY into nexus.db.

Volume is determined by the S-curve position relative to the
10-year seed start date (read from the DB's earliest sale).
At year 10 this produces ~900–1,000 transactions per day with
correct weekend/festival/salary-week modifiers.

Usage:
    python daily_seed.py            # seeds today
    python daily_seed.py --date 2026-03-10  # seeds a specific date (backfill)
    python daily_seed.py --dry-run  # prints stats without writing to DB

Requirements:
    numpy  (already installed)
    nexus_seed_maps.json must exist in the NexusRetailOS config dir
    (written by gen_master_data.py — present if you ran the 10-year seed)

Safe to run multiple times:
    Checks if today already has sales and skips if so.
═══════════════════════════════════════════════════════════════════
"""

import os, sys, json, sqlite3, time, math, argparse
import numpy as np
import random
from datetime import datetime, timedelta, date

# ═══════════════════════════════════════════════════════════════════════════
#  PATH RESOLUTION
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

# ═══════════════════════════════════════════════════════════════════════════
#  COMBO / AFFINITY TABLES  (must match gen_transactions.py)
# ═══════════════════════════════════════════════════════════════════════════
STRONG_COMBOS = [
    ("Maggi","Britannia",0.38), ("Maggi","Amul",0.35), ("Maggi","Tata Salt",0.28),
    ("Lays","Coca Cola",0.40),  ("Lays","Pepsi",0.35), ("Lays","Kurkure",0.30),
    ("Kurkure","Pepsi",0.32),   ("Sprite","Haldiram",0.25),
    ("Britannia","Mother Dairy",0.35), ("Parle","Amul",0.28),
    ("Tata Salt","Aashirvaad",0.40),   ("Fortune","Aashirvaad",0.35),
    ("Colgate","Lux",0.22),            ("Top Ramen","Yippee",0.28),
]
CAT_AFFINITY = [
    ("Snacks","Beverages",0.52),   ("Dairy","Bakery",0.42),
    ("Staples","Staples",0.30),    ("Personal Care","Cleaning",0.35),
    ("Instant Food","Dairy",0.30), ("Bakery","Dairy",0.38),
    ("Confectionery","Beverages",0.28),
]
FAST_MOVER_KWS = [
    "maggi","lays","kurkure","coca cola","pepsi","sprite","frooti","maaza",
    "amul","britannia","bisleri","thums up","mountain dew","yippee","top ramen",
]

# ═══════════════════════════════════════════════════════════════════════════
#  LOAD MAPS
# ═══════════════════════════════════════════════════════════════════════════
def load_maps():
    if not os.path.exists(MAPS_PATH):
        raise FileNotFoundError(
            f"nexus_seed_maps.json not found at {MAPS_PATH}\n"
            "Run gen_master_data.py (part of the 10-year seed) first."
        )
    with open(MAPS_PATH) as f:
        raw = json.load(f)

    maps = dict(raw)
    maps["variant_price_map"]           = {int(k): v for k, v in raw["variant_price_map"].items()}
    maps["variant_to_product_name"]     = {int(k): v for k, v in raw["variant_to_product_name"].items()}
    maps["variant_to_category"]         = {int(k): v for k, v in raw["variant_to_category"].items()}
    maps["variant_reorder_point"]       = {int(k): v for k, v in raw["variant_reorder_point"].items()}
    maps["credit_limits"]               = {int(k): v for k, v in raw["credit_limits"].items()}
    maps["customer_join_day"]           = {int(k): v for k, v in raw["customer_join_day"].items()}
    maps["customer_segments"]           = {int(k): v for k, v in raw["customer_segments"].items()}
    maps["churn_days"]                  = {int(k): v for k, v in raw["churn_days"].items()}
    maps["temp_churn"]                  = {int(k): v for k, v in raw["temp_churn"].items()}
    maps["supplier_category_map"]       = {int(k): v for k, v in raw["supplier_category_map"].items()}
    maps["category_to_variant_ids"]     = {k: [int(x) for x in v] for k, v in raw["category_to_variant_ids"].items()}
    maps["product_name_to_variant_ids"] = {k: [int(x) for x in v] for k, v in raw["product_name_to_variant_ids"].items()}
    maps["all_variant_ids"]             = [int(x) for x in raw["all_variant_ids"]]
    maps["customer_ids"]                = [int(x) for x in raw["customer_ids"]]
    maps["credit_customer_ids"]         = [int(x) for x in raw["credit_customer_ids"]]
    maps["supplier_ids"]                = [int(x) for x in raw["supplier_ids"]]
    maps["combo_pairs"] = [
        [[int(x) for x in pa], [int(x) for x in pb]]
        for pa, pb in raw["combo_pairs"]
    ]
    return maps


# ═══════════════════════════════════════════════════════════════════════════
#  DETERMINE DAY INDEX  relative to the 10-year seed start date
#  Reads the earliest sale_date from the DB so this is always accurate.
# ═══════════════════════════════════════════════════════════════════════════
def get_day_index(conn, target_date: date) -> int:
    """
    Returns how many days after the first-ever sale target_date falls.
    This places target_date correctly on the S-curve.
    """
    row = conn.execute("SELECT MIN(DATE(sale_date)) FROM credit_sale").fetchone()[0]
    if not row:
        raise RuntimeError("No existing sales in DB. Run the 10-year seed first.")
    seed_start = datetime.strptime(row, "%Y-%m-%d").date()
    delta = (target_date - seed_start).days
    return delta   # e.g. 3650 if seeding exactly 10 years after start


# ═══════════════════════════════════════════════════════════════════════════
#  DAILY TRANSACTION COUNT  — S-curve + modifiers
# ═══════════════════════════════════════════════════════════════════════════
def daily_tx_count(day_idx: int, current_date: datetime, rng) -> int:
    L, k, t0 = 1000.0, 0.0012, 1825.0
    base = L / (1.0 + math.exp(-k * (day_idx - t0)))

    m, d, wd = current_date.month, current_date.day, current_date.weekday()

    if wd >= 5:  base *= 1.30   # Weekend
    if d  <= 7:  base *= 1.20   # Salary week

    # Festival boosts
    if (m == 10 and d >= 15) or (m == 11 and d <= 15): base *= 1.45  # Diwali
    elif m == 3  and  5 <= d <= 25: base *= 1.30   # Holi
    elif m == 1  and  d <= 10:      base *= 1.25   # New Year
    elif m in [6,7] and 10 <= d <= 25: base *= 1.20  # Eid

    noise = float(rng.normal(0, base * 0.08))
    return max(40, min(1100, int(base + noise)))


# ═══════════════════════════════════════════════════════════════════════════
#  ELIGIBLE CUSTOMERS FOR TODAY
# ═══════════════════════════════════════════════════════════════════════════
def get_eligible_customers(maps, day_idx: int, rng) -> list:
    """
    Returns list of customer_ids who can visit today.
    Applies join_day, permanent churn, temp churn, and visit lambda.
    """
    SEG_LAMBDA = {"loyal":0.26,"credit":0.16,"occasional":0.07,"at_risk":0.12}

    eligible = []
    for cid in maps["customer_ids"]:
        # Must have joined
        if day_idx < maps["customer_join_day"].get(cid, 0):
            continue
        # Permanent churn
        if day_idx > maps["churn_days"].get(cid, 9999):
            continue
        # Temp churn
        tc = maps["temp_churn"].get(cid)
        if tc and tc[0] <= day_idx <= tc[1]:
            continue
        eligible.append(cid)

    # Apply at-risk decay to lambda
    buyers = []
    for cid in eligible:
        seg = maps["customer_segments"].get(cid, "occasional")
        lam = SEG_LAMBDA.get(seg, 0.07)
        if seg == "at_risk":
            lam = max(0.03, lam * (1.0 - day_idx / (3650 * 1.5)))
        if rng.random() < lam:
            buyers.append(cid)

    return buyers


# ═══════════════════════════════════════════════════════════════════════════
#  BASKET BUILDER
# ═══════════════════════════════════════════════════════════════════════════
def build_basket(cid: int, day_idx: int, current_date: datetime, maps, rng) -> list:
    all_vids  = maps["all_variant_ids"]
    cat_vids  = maps["category_to_variant_ids"]
    prod_vids = maps["product_name_to_variant_ids"]
    categories= maps["categories"]
    basket    = []
    m         = current_date.month

    # 1. Preferred category (1-3 items)
    pref_cat_idx  = cid % len(categories)
    pref_cat      = categories[pref_cat_idx]
    secondary_cat = categories[(pref_cat_idx + 1) % len(categories)]
    pv       = cat_vids.get(pref_cat, [])
    sec_vids = cat_vids.get(secondary_cat, [])
    if pv:
        for _ in range(int(rng.integers(2, 5))):
            basket.append(int(rng.choice(pv)))
    if sec_vids and rng.random() < 0.55:
        basket.append(int(rng.choice(sec_vids)))

    # 2. Combo affinity
    b_prods = set(maps["variant_to_product_name"].get(v, "").lower() for v in basket)
    for kw_a, kw_b, prob in STRONG_COMBOS:
        if any(kw_a.lower() in bp for bp in b_prods) and rng.random() < prob:
            partner = []
            for pname, vlist in prod_vids.items():
                if kw_b.lower() in pname.lower():
                    partner.extend(vlist)
            if partner:
                basket.append(int(rng.choice(partner)))

    # 3. Category affinity
    b_cats = set(maps["variant_to_category"].get(v, "") for v in basket)
    for cat_a, cat_b, prob in CAT_AFFINITY:
        if cat_a in b_cats and rng.random() < prob:
            vb = cat_vids.get(cat_b, [])
            if vb:
                basket.append(int(rng.choice(vb)))

    # 4. Random extras (2-6)
    scoped_pool = pv + sec_vids if sec_vids else pv
    if not scoped_pool:
        scoped_pool = all_vids
    for _ in range(int(rng.integers(1, 3))):
        basket.append(int(rng.choice(scoped_pool)))
    if rng.random() < 0.25:
        basket.append(int(rng.choice(all_vids)))

    # 5. Seasonal
    if m in [4, 5, 6]:
        bev = cat_vids.get("Beverages", [])
        if bev and rng.random() < 0.45:
            basket.append(int(rng.choice(bev)))
    elif m in [11, 12, 1]:
        sta = cat_vids.get("Staples", [])
        if sta and rng.random() < 0.35:
            basket.append(int(rng.choice(sta)))
    elif m in [10, 11]:
        conf = cat_vids.get("Confectionery", [])
        if conf and rng.random() < 0.40:
            basket.append(int(rng.choice(conf)))

    basket = list(dict.fromkeys(basket))
    if not basket:
        basket = [int(rng.choice(all_vids))]
    return basket[:18]


# ═══════════════════════════════════════════════════════════════════════════
#  PAYMENT HANDLER  — reads live balance from DB state
# ═══════════════════════════════════════════════════════════════════════════
def handle_payment(cid, total_bill, current_date, maps, live_balances,
                   credit_set, rng, payments_q):
    if cid not in credit_set:
        # Cash customer — full payment immediately
        dstr = current_date.strftime("%Y-%m-%d %H:%M:%S")
        payments_q.append((cid, dstr, round(float(total_bill), 2), random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[0]))
        return

    # Add to running balance
    live_balances[cid] = live_balances.get(cid, 0.0) + total_bill
    debt  = live_balances[cid]
    limit = maps["credit_limits"].get(cid, 15000.0)
    m_day = current_date.day
    is_sw = m_day <= 7
    is_fm = current_date.month in [10, 11, 1, 3]

    pay_amount = 0.0
    dstr       = current_date.strftime("%Y-%m-%d %H:%M:%S")

    if debt > limit:
        excess     = debt - limit
        pay_amount = min(excess + float(rng.uniform(300, 2500)), debt)

    elif is_sw and debt > 400:
        prob = 0.72 + (0.10 if is_fm else 0.0)
        if rng.random() < prob:
            pay_amount = round(debt * float(rng.uniform(0.5, 1.0)), 2)

    if debt > 80000:
        target_after = float(rng.uniform(10000, 25000))
        pay_amount   = max(pay_amount, debt - target_after)

    if pay_amount > 0:
        pay_amount = min(round(pay_amount, 2), debt)
        live_balances[cid] -= pay_amount
        live_balances[cid]  = max(0.0, live_balances[cid])
        payments_q.append((cid, dstr, pay_amount, random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[0]))


# ═══════════════════════════════════════════════════════════════════════════
#  SPONTANEOUS PAYMENTS  — credit customers paying without buying
# ═══════════════════════════════════════════════════════════════════════════
def handle_spontaneous_payments(current_date, maps, live_balances,
                                 credit_set, rng, payments_q):
    is_fest = current_date.month in [10, 11, 1, 3]
    prob    = 0.14 if is_fest else 0.08
    dbase   = current_date.strftime("%Y-%m-%d")

    sp_rand = rng.random(len(maps["credit_customer_ids"]))
    sp_frac = rng.random(len(maps["credit_customer_ids"]))

    for si, sp_cid in enumerate(maps["credit_customer_ids"]):
        debt = live_balances.get(sp_cid, 0.0)
        if debt < 100.0 or sp_rand[si] >= prob:
            continue
        pay_amount = round(min(debt * float(sp_frac[si] * 0.75 + 0.25), debt), 2)
        if pay_amount < 1.0:
            continue
        live_balances[sp_cid] -= pay_amount
        live_balances[sp_cid]  = max(0.0, live_balances[sp_cid])
        h = int(rng.integers(9, 18))
        mn = int(rng.integers(0, 60))
        payments_q.append((sp_cid, f"{dbase} {h:02d}:{mn:02d}:00", pay_amount, random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[0]))


# ═══════════════════════════════════════════════════════════════════════════
#  RESTOCK → PURCHASE INVOICES
# ═══════════════════════════════════════════════════════════════════════════
def create_invoices(restock_map, current_date, maps, inv_counter,
                    inv_seq, rng, invoices_q, p_items_q):
    sup_batches = {}
    for vid, (qty, cost) in restock_map.items():
        cat      = maps["variant_to_category"].get(vid, "")
        assigned = None
        for sid_k, cats in maps["supplier_category_map"].items():
            if cat in cats:
                assigned = sid_k
                break
        if assigned is None:
            assigned = int(rng.choice(maps["supplier_ids"]))
        sup_batches.setdefault(assigned, []).append((vid, qty, cost))

    for sid, items in sup_batches.items():
        inv_counter += 1
        seq          = inv_seq.get(sid, 0) + 1
        inv_seq[sid] = seq
        ih           = int(rng.integers(4, 8))
        idt          = current_date.replace(
            hour=ih, minute=int(rng.integers(0, 60)), second=0
        )
        total_amt = sum(q * c for _, q, c in items)
        ref_no    = f"INV-{idt.year}{idt.month:02d}-{sid:04d}-{seq:05d}"

        invoices_q.append((
            inv_counter, sid,
            idt.strftime("%Y-%m-%d %H:%M:%S"),
            round(float(total_amt), 2),
            ref_no
        ))
        for vid, qty, cost in items:
            p_items_q.append((inv_counter, int(vid), float(qty), float(cost)))

    return inv_counter


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="NexusRetailOS daily transaction seeder")
    parser.add_argument(
        "--date", type=str, default=None,
        help="Date to seed in YYYY-MM-DD format (default: today)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Simulate and print stats without writing to the database"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Insert even if sales already exist for this date"
    )
    args = parser.parse_args()

    t0 = time.time()

    # ── Resolve target date ────────────────────────────────────────────────
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
    else:
        target_date = date.today()

    target_dt = datetime(target_date.year, target_date.month, target_date.day)

    print("=" * 60)
    print(f"  NexusRetailOS — Daily Seed")
    print(f"  Date    : {target_date}")
    print(f"  DB      : {DB_PATH}")
    print(f"  Dry run : {args.dry_run}")
    print("=" * 60)

    # ── Connect ────────────────────────────────────────────────────────────
    if not os.path.exists(DB_PATH):
        print(f"\n❌  Database not found: {DB_PATH}")
        print("   Run the 10-year seed first (run_seed.py or run_seed_fast.py)")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-64000;")
    conn.execute("PRAGMA foreign_keys=OFF;")
    c = conn.cursor()

    # ── Guard: already seeded today? ──────────────────────────────────────
    date_str_check = target_date.strftime("%Y-%m-%d")
    existing = c.execute(
        "SELECT COUNT(*) FROM credit_sale WHERE DATE(sale_date) = ?",
        (date_str_check,)
    ).fetchone()[0]

    if existing > 0 and not args.force:
        print(f"\n⚠️   Already {existing:,} sales on {date_str_check}.")
        print("   Skipping. Use --force to insert anyway.")
        conn.close()
        return

    # ── Load maps ──────────────────────────────────────────────────────────
    print("\n📂  Loading maps…")
    maps = load_maps()

    # ── Get day index on S-curve ───────────────────────────────────────────
    day_idx = get_day_index(conn, target_date)
    print(f"   S-curve day index : {day_idx} (day 0 = first sale in DB)")

    # ── Compute expected volume ────────────────────────────────────────────
    # Use date-seeded RNG so the same date always gives the same volume
    date_seed = int(target_date.strftime("%Y%m%d"))
    rng       = np.random.default_rng(date_seed)

    target_tx = daily_tx_count(day_idx, target_dt, rng)
    print(f"   Target tx volume  : {target_tx:,}")

    # ── Read live state from DB ────────────────────────────────────────────
    print("   Reading live balances & stock…", end=" ", flush=True)

    # Current customer balances (live, not from maps)
    rows = c.execute("SELECT id, balance FROM customer").fetchall()
    live_balances = {r[0]: float(r[1]) for r in rows}

    # Current inventory (live)
    rows = c.execute("SELECT id, current_stock FROM product_variant").fetchall()
    live_inventory = {r[0]: float(r[1]) for r in rows}

    # Max existing IDs (so we don't collide with existing PKs)
    max_sale_id = c.execute("SELECT IFNULL(MAX(id), 0) FROM credit_sale").fetchone()[0]
    max_inv_id  = c.execute("SELECT IFNULL(MAX(id), 0) FROM purchase_invoice").fetchone()[0]
    sale_counter = max_sale_id
    inv_counter  = max_inv_id

    # Current invoice sequences per supplier
    rows = c.execute("""
        SELECT supplier_id, COUNT(*)
        FROM purchase_invoice
        WHERE DATE(invoice_date) = ?
        GROUP BY supplier_id
    """, (date_str_check,)).fetchall()
    inv_seq = {r[0]: r[1] for r in rows}

    print("✅")

    # ── Get eligible buyers ────────────────────────────────────────────────
    credit_set = set(maps["credit_customer_ids"])
    buyers     = get_eligible_customers(maps, day_idx, rng)

    # Cap / supplement to hit target
    if len(buyers) > target_tx:
        buyers = [int(x) for x in rng.choice(buyers, size=target_tx, replace=False)]
    elif len(buyers) < int(target_tx * 0.7):
        # Pull in extra random eligible customers to approach target
        all_eligible = [
            cid for cid in maps["customer_ids"]
            if day_idx >= maps["customer_join_day"].get(cid, 0)
            and day_idx <= maps["churn_days"].get(cid, 9999)
        ]
        non_buyers = [c for c in all_eligible if c not in set(buyers)]
        shortfall  = min(int(target_tx * 0.7) - len(buyers), len(non_buyers))
        if shortfall > 0:
            buyers += [int(x) for x in rng.choice(non_buyers, size=shortfall, replace=False)]

    # Guarantee all buyer IDs are plain Python int — never numpy int64
    # (numpy int64 inserted into SQLite becomes BLOB, breaking pandas groupby in churn model)
    buyers = [int(x) for x in buyers]

    print(f"   Eligible buyers   : {len(buyers):,}")

    # ── Simulate ──────────────────────────────────────────────────────────
    sales_q    = []
    items_q    = []
    payments_q = []
    invoices_q = []
    p_items_q  = []
    restock_map = {}

    hours   = rng.integers(8,  21, len(buyers))
    minutes = rng.integers(0,  60, len(buyers))
    seconds = rng.integers(0,  60, len(buyers))

    total_revenue = 0.0

    for bi, cid in enumerate(buyers):
        sale_counter += 1
        sale_id = sale_counter

        sale_dt   = target_dt.replace(
            hour=int(hours[bi]), minute=int(minutes[bi]), second=int(seconds[bi])
        )
        sale_dstr = sale_dt.strftime("%Y-%m-%d %H:%M:%S")
        sales_q.append((sale_id, cid, sale_dstr))

        basket     = build_basket(cid, day_idx, target_dt, maps, rng)
        total_bill = 0.0

        for vid in basket:
            qty    = float(rng.integers(1, 5))
            price  = round(float(maps["variant_price_map"].get(vid, 20.0)), 2)
            total_bill += qty * price
            items_q.append((sale_id, vid, qty, price))

            # Inventory update
            live_inventory[vid] = live_inventory.get(vid, 0.0) - qty
            rp = maps["variant_reorder_point"].get(vid, 8.0)
            if live_inventory[vid] < rp:
                rqty = float(rng.integers(40, 130))
                cost = round(price * float(rng.uniform(0.65, 0.78)), 2)
                if vid not in restock_map or rqty > restock_map[vid][0]:
                    restock_map[vid] = (rqty, cost)
                live_inventory[vid] += rqty

        total_revenue += total_bill
        handle_payment(
            cid, total_bill, sale_dt, maps,
            live_balances, credit_set, rng, payments_q
        )

    # Spontaneous debt payments
    handle_spontaneous_payments(
        target_dt, maps, live_balances, credit_set, rng, payments_q
    )

    # Year-end sweep
    if target_date.month == 12 and target_date.day == 31:
        ye_rand = rng.random(len(maps["credit_customer_ids"]))
        for yi, ye_cid in enumerate(maps["credit_customer_ids"]):
            debt = live_balances.get(ye_cid, 0.0)
            if debt > 15000:
                frac = float(ye_rand[yi] * 0.32 + 0.60)
                pa   = round(debt * frac, 2)
                live_balances[ye_cid] -= pa
                live_balances[ye_cid]  = max(0.0, live_balances[ye_cid])
                payments_q.append((
                    ye_cid,
                    target_date.strftime("%Y-%m-%d 23:59:00"),
                    pa,
                    random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[0]
                ))

    # Create invoices from restocks
    if restock_map:
        inv_counter = create_invoices(
            restock_map, target_dt, maps,
            inv_counter, inv_seq, rng,
            invoices_q, p_items_q
        )

    # ── Stats preview ──────────────────────────────────────────────────────
    avg_basket = len(items_q) / len(sales_q) if sales_q else 0
    print(f"\n{'─' * 60}")
    print(f"  📊  Preview for {date_str_check}")
    print(f"{'─' * 60}")
    print(f"  Sales       : {len(sales_q):,}")
    print(f"  Items sold  : {len(items_q):,}")
    print(f"  Avg basket  : {avg_basket:.1f} items")
    print(f"  Payments    : {len(payments_q):,}")
    print(f"  Invoices    : {len(invoices_q):,}")
    print(f"  Revenue     : ₹{total_revenue:,.2f}")
    print(f"{'─' * 60}")

    if args.dry_run:
        print("\n  [DRY RUN] Nothing written to database.")
        conn.close()
        return

    # ── Write to DB ────────────────────────────────────────────────────────
    print("\n💾  Writing to database…", end=" ", flush=True)

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

    # ── Bulk-update live balances (mirrors trigger behaviour) ──────────────
    # Only update customers whose balance changed today
    changed_cids = set(r[0] for r in payments_q) | set(r[0] for r in sales_q)
    balance_updates = [
        (round(max(0.0, live_balances.get(cid, 0.0)), 2), cid)
        for cid in changed_cids
    ]
    if balance_updates:
        c.executemany("UPDATE customer SET balance = ? WHERE id = ?", balance_updates)

    # ── Update stock for restocked variants ───────────────────────────────
    if restock_map:
        stock_updates = [
            (round(max(0.0, live_inventory.get(vid, 0.0)), 1), vid)
            for vid in restock_map
        ]
        c.executemany(
            "UPDATE product_variant SET current_stock = ? WHERE id = ?",
            stock_updates
        )

    conn.commit()
    conn.execute("ANALYZE;")
    conn.close()

    elapsed = time.time() - t0
    print("✅")
    print(f"\n{'=' * 60}")
    print(f"  ✅  Daily seed complete for {date_str_check}  ({elapsed:.1f}s)")
    print(f"      {len(sales_q):,} sales  ·  {len(items_q):,} items  ·  ₹{total_revenue:,.0f} revenue")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
