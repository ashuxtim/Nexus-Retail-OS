#!/usr/bin/env python3
"""
flex_seed.py  —  NexusRetailOS Universal Seed Script
═══════════════════════════════════════════════════════════════════════════════
  One script. All scenarios. Just edit the CONFIG block at the top.

  Usage:
      python flex_seed.py             # uses CONFIG values below
      python flex_seed.py --dry-run   # preview without writing

  What it does:
    1. Optionally inserts NEW customers / suppliers / products into your DB
       (generates realistic Indian names — no faker)
    2. Simulates DAYS days of transactions starting from START_FROM
    3. Volume follows the S-curve position relative to your existing data
    4. Reads all IDs + live balances + live stock from DB — never stale

  Scenarios:
    • Monthly growth top-up  →  DAYS=30, NEW_CUSTOMERS=10
    • Fresh DB quick test    →  DAYS=30 (works on empty DB with master seed run)
    • Backfill missed days   →  DAYS=7,  START_FROM="auto"
    • Festival window test   →  DAYS=30, START_FROM="2025-10-15"
    • Big user growth spike  →  DAYS=30, NEW_CUSTOMERS=200, NEW_SUPPLIERS=20
═══════════════════════════════════════════════════════════════════════════════
"""

import os, sys, json, sqlite3, time, math, argparse
import numpy as np
import random
from datetime import datetime, timedelta, date
from itertools import product as iproduct

# ╔══════════════════════════════════════════════════════════════════════════╗
# ║                        ★  EDIT THIS BLOCK  ★                           ║
# ╠══════════════════════════════════════════════════════════════════════════╣

DAYS = 30  # How many days to simulate

NEW_CUSTOMERS = 10  # New customers to INSERT before simulation (0 = none)
NEW_SUPPLIERS = 0  # New suppliers to INSERT before simulation (0 = none)
NEW_PRODUCTS = 0  # New products+variants to INSERT before simulation (0 = none)

# When to start simulating:
#   "auto"       → picks up the day after the last sale in your DB
#   "YYYY-MM-DD" → specific date (e.g. "2025-10-15" for Diwali window)
START_FROM = "auto"

# ╚══════════════════════════════════════════════════════════════════════════╝

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
MAPS_PATH = os.path.join(BASE_DIR, "nexus_seed_maps.json")

PAYMENT_MODES = ["Cash", "UPI", "Card", "Bank Transfer"]
PAYMENT_WEIGHTS = [50, 30, 15, 5]

HERE = os.path.dirname(os.path.abspath(__file__))


# ═══════════════════════════════════════════════════════════════════════════
#  NAME & PRODUCT BANKS
#  Tries to import from gen_master_data.py (same folder).
#  Falls back to inline banks if not found — fully self-contained.
# ═══════════════════════════════════════════════════════════════════════════
def _load_name_banks():
    """Load FIRST_NAMES, LAST_NAMES, CITY_AREAS, SUPPLIER_KEYWORDS,
    SUPPLIER_SUFFIXES, CATALOG from gen_master_data.py if available."""
    if HERE not in sys.path:
        sys.path.insert(0, HERE)
    try:
        import gen_master_data as gm

        print("   ✅ Name banks loaded from gen_master_data.py")
        return (
            gm.FIRST_NAMES,
            gm.LAST_NAMES,
            gm.CITY_AREAS,
            gm.SUPPLIER_KEYWORDS,
            gm.SUPPLIER_SUFFIXES,
            gm.CATALOG,
        )
    except (ImportError, AttributeError):
        print("   ⚠️  gen_master_data.py not found — using inline name banks")
        return (
            _FIRST_NAMES,
            _LAST_NAMES,
            _CITY_AREAS,
            _SUPPLIER_KEYWORDS,
            _SUPPLIER_SUFFIXES,
            _CATALOG,
        )


# ── Inline fallback name banks (subset — enough for realistic generation) ─
_FIRST_NAMES = [
    "Aarav",
    "Aditya",
    "Ajay",
    "Akash",
    "Amit",
    "Anand",
    "Anil",
    "Anjali",
    "Ankita",
    "Anupama",
    "Arjun",
    "Ashish",
    "Ashok",
    "Atul",
    "Ayesha",
    "Bharat",
    "Deepa",
    "Deepak",
    "Deepika",
    "Divya",
    "Fatima",
    "Gaurav",
    "Gauri",
    "Geeta",
    "Gopal",
    "Harish",
    "Hemant",
    "Isha",
    "Jaya",
    "Jyoti",
    "Karan",
    "Kartik",
    "Kavita",
    "Kiran",
    "Lalit",
    "Lakshmi",
    "Manoj",
    "Manish",
    "Maya",
    "Meena",
    "Mohit",
    "Mukesh",
    "Naresh",
    "Naveen",
    "Neha",
    "Nikhil",
    "Nitin",
    "Pankaj",
    "Pooja",
    "Priya",
    "Rahul",
    "Rajesh",
    "Rajiv",
    "Rakesh",
    "Ravi",
    "Rekha",
    "Ritesh",
    "Rohan",
    "Rohit",
    "Sachin",
    "Sanjay",
    "Santosh",
    "Satish",
    "Seema",
    "Shanti",
    "Shreya",
    "Sneha",
    "Sonal",
    "Sudha",
    "Sunil",
    "Sunita",
    "Suresh",
    "Swati",
    "Tara",
    "Usha",
    "Vandana",
    "Varsha",
    "Vijay",
    "Vikram",
    "Vinod",
    "Vishal",
    "Vivek",
    "Yash",
    "Yogesh",
    "Zara",
    "Abhishek",
    "Ankit",
    "Aryan",
    "Chirag",
    "Dev",
    "Harsh",
    "Ishan",
    "Kabir",
    "Mayur",
    "Neeraj",
    "Pranav",
    "Raghav",
    "Rishabh",
    "Sameer",
    "Shubham",
    "Aditi",
    "Alka",
    "Amita",
    "Anita",
    "Asha",
    "Babita",
    "Bhavna",
    "Chhaya",
    "Durga",
    "Ekta",
    "Garima",
    "Harshita",
    "Ishita",
    "Juhi",
    "Khushi",
    "Lavanya",
    "Mansi",
    "Nidhi",
    "Pallavi",
    "Pari",
    "Prachi",
    "Ridhi",
    "Riya",
    "Sakshi",
    "Shivangi",
    "Simran",
    "Smriti",
    "Tanvi",
    "Vaishnavi",
    "Yashvi",
]
_LAST_NAMES = [
    "Agarwal",
    "Ahuja",
    "Ansari",
    "Arora",
    "Bajaj",
    "Banerjee",
    "Bansal",
    "Batra",
    "Bhatt",
    "Bose",
    "Chauhan",
    "Chawla",
    "Datta",
    "Dave",
    "Desai",
    "Deshpande",
    "Dubey",
    "Dutta",
    "Gandhi",
    "Garg",
    "Ghosh",
    "Goswami",
    "Goyal",
    "Gupta",
    "Iyer",
    "Jain",
    "Jaiswal",
    "Jha",
    "Joshi",
    "Kapur",
    "Kapoor",
    "Kaur",
    "Khanna",
    "Kohli",
    "Kumar",
    "Lal",
    "Malhotra",
    "Mehta",
    "Mishra",
    "Modi",
    "Mohan",
    "Mukherjee",
    "Nair",
    "Nath",
    "Pandey",
    "Patel",
    "Pathak",
    "Patil",
    "Paul",
    "Pillai",
    "Prasad",
    "Rajput",
    "Rao",
    "Rastogi",
    "Rawat",
    "Reddy",
    "Roy",
    "Sahoo",
    "Saxena",
    "Shah",
    "Sharma",
    "Shukla",
    "Singh",
    "Sinha",
    "Soni",
    "Srivastava",
    "Thakur",
    "Tiwari",
    "Tripathi",
    "Varma",
    "Verma",
    "Yadav",
    "Bajpai",
    "Bhardwaj",
    "Bhatia",
    "Bhattacharya",
    "Bisht",
    "Das",
    "Dhawan",
    "Dixit",
    "Goel",
    "Grover",
    "Gulati",
    "Handa",
    "Kadam",
    "Kashyap",
    "Kulkarni",
    "Mathur",
    "Mehra",
    "Menon",
    "Nagpal",
    "Naik",
    "Oberoi",
    "Patel",
    "Puri",
    "Raina",
    "Saraf",
    "Sethi",
    "Shinde",
    "Subramaniam",
    "Suri",
    "Talwar",
    "Taneja",
    "Tyagi",
    "Upadhyay",
    "Vaidya",
    "Narayanan",
    "Krishnan",
    "Balaji",
    "Venkatesh",
    "Ramachandran",
    "Chatterjee",
    "Sarkar",
]
_CITY_AREAS = [
    "Rohini Delhi",
    "Lajpat Nagar Delhi",
    "Dwarka Delhi",
    "Pitampura Delhi",
    "Mayur Vihar Delhi",
    "Vasant Kunj Delhi",
    "Saket Delhi",
    "Nehru Place Delhi",
    "Laxmi Nagar Delhi",
    "Karol Bagh Delhi",
    "Malviya Nagar Delhi",
    "Hauz Khas Delhi",
    "Andheri Mumbai",
    "Bandra Mumbai",
    "Borivali Mumbai",
    "Thane Mumbai",
    "Mulund Mumbai",
    "Koramangala Bengaluru",
    "Indiranagar Bengaluru",
    "Whitefield Bengaluru",
    "Banjara Hills Hyderabad",
    "Madhapur Hyderabad",
    "Kukatpally Hyderabad",
    "Kothrud Pune",
    "Aundh Pune",
    "Baner Pune",
    "Wakad Pune",
    "Hadapsar Pune",
    "Anna Nagar Chennai",
    "T Nagar Chennai",
    "Adyar Chennai",
    "Velachery Chennai",
    "Salt Lake Kolkata",
    "New Town Kolkata",
    "Satellite Ahmedabad",
    "Adajan Surat",
    "Vaishali Nagar Jaipur",
    "Hazratganj Lucknow",
    "Gomti Nagar Lucknow",
    "Boring Road Patna",
    "Vijay Nagar Indore",
    "Dharampeth Nagpur",
]
_SUPPLIER_KEYWORDS = [
    "Agro Fresh",
    "Apex Distribution",
    "Balram Traders",
    "Bengal Agro",
    "Bharati Enterprises",
    "Choice Agencies",
    "City Fresh Supply",
    "Classic Traders",
    "Continental Foods",
    "Crown Agencies",
    "Devi Marketing",
    "Diamond Supply",
    "Eastern Traders",
    "Elite Distribution",
    "Empire Wholesale",
    "Excel Trading",
    "Fortune Traders",
    "Galaxy Distribution",
    "Ganesh Agencies",
    "Global Mart",
    "Goodluck Traders",
    "Green Valley Foods",
    "Gupta Brothers",
    "Hanuman Enterprises",
    "Happy Traders",
    "Hari Om Supply",
    "Ideal Distributors",
    "Imperial Supply",
    "India Fresh",
    "Indus Traders",
    "Jagdamba Supply",
    "Jai Hind Agencies",
    "Jay Ambe Supply",
    "Joshi Brothers",
    "Kamal Enterprises",
    "Kapil Traders",
    "Kaveri Agro",
    "Kesari Supply",
    "Kiran Trading",
    "Krishna Agencies",
    "Kumar Brothers",
    "Laxmi Enterprises",
    "Mahalaxmi Supply",
    "Mahesh Traders",
    "Maruti Enterprises",
    "Metro Distribution",
    "Milan Traders",
    "Modern Agencies",
    "Mohit Trading",
    "National Foods",
    "Navkar Agencies",
    "New India Traders",
    "Noble Distributors",
    "Northern Supply",
    "Om Sai Agencies",
    "Padmavati Enterprises",
    "Paramount Supply",
    "Patel Brothers",
    "Pioneer Distribution",
    "Pooja Enterprises",
    "Pragati Traders",
    "Prasad Supply",
    "Premium Agencies",
    "Prince Trading",
    "Priya Enterprises",
    "Punjab Fresh",
    "Rajdhani Supply",
    "Rajesh Agencies",
    "Ram Janaki Enterprises",
    "Rashmi Trading",
    "Royal Traders",
    "Sai Krupa Supply",
    "Sainath Agencies",
    "Samarth Distribution",
    "Sanjay Traders",
    "Santosh Enterprises",
    "Saraswati Agro",
    "Sarv Mangal Supply",
    "Satya Sai Agencies",
    "Sharma Brothers",
    "Shiv Shakti Supply",
    "Shivam Distribution",
    "Singh Brothers",
    "Star Agencies",
    "Subhash Trading",
    "Sudarshan Supply",
    "Suresh Brothers",
    "Swastik Supply",
    "Tirupati Supply",
    "Trimurti Distribution",
    "United Supply",
    "Usha Enterprises",
    "Vaibhav Trading",
    "Vardhan Supply",
    "Vijay Agencies",
    "Vikram Traders",
    "Vinayak Supply",
    "Vishnu Enterprises",
    "Western Traders",
    "Yadav Brothers",
    "Yogesh Agencies",
    "Zones Distribution",
]
_SUPPLIER_SUFFIXES = [
    "Distributors",
    "Traders",
    "Agencies",
    "Pvt Ltd",
    "Enterprises",
    "Distribution Hub",
    "Wholesale Depot",
    "& Co",
    "Trading Company",
    "Suppliers",
]
_CATALOG = {
    "Snacks": {
        "brands": [
            "Lays",
            "Kurkure",
            "Bingo",
            "Haldiram",
            "Bikaji",
            "Too Yumm",
            "Uncle Chips",
            "Balaji",
            "Yellow Diamond",
            "Cornitos",
        ],
        "lines": [
            "Classic Salted",
            "Masala Munch",
            "Cream Onion",
            "Magic Masala",
            "Tomato Tango",
            "Peri Peri",
            "Pudina Fresh",
            "Spicy Treat",
            "Bhujia Mix",
            "Chaat Masala",
        ],
        "sizes": [("26g Pack", 10.0), ("52g Pack", 20.0), ("90g Pack", 30.0)],
        "unit": "Pack",
    },
    "Beverages": {
        "brands": [
            "Coca Cola",
            "Pepsi",
            "Sprite",
            "Thums Up",
            "Fanta",
            "Maaza",
            "Frooti",
            "Bisleri",
            "Sting",
            "Appy Fizz",
        ],
        "lines": [
            "Regular",
            "Diet Zero",
            "Mango Flavour",
            "Orange Flavour",
            "Lemon Lime",
            "Cola Original",
            "Mixed Fruit",
            "Energy Original",
        ],
        "sizes": [("330ml Can", 40.0), ("600ml Bottle", 50.0), ("2L Bottle", 95.0)],
        "unit": "Bottle",
    },
    "Dairy": {
        "brands": ["Amul", "Mother Dairy", "Nestle", "Heritage", "Vijaya", "Nandini"],
        "lines": [
            "Full Cream Milk",
            "Toned Milk",
            "Butter Salted",
            "Fresh Paneer",
            "Set Curd",
            "Sweet Lassi",
        ],
        "sizes": [("500ml Pouch", 30.0), ("1L Pack", 58.0), ("200g Pack", 50.0)],
        "unit": "Pack",
    },
    "Bakery": {
        "brands": ["Britannia", "Parle", "Sunfeast", "Priyagold", "Anmol"],
        "lines": [
            "Marie Gold",
            "Glucose Biscuit",
            "Butter Cookies",
            "Cream Sandwich",
            "Brown Bread Loaf",
            "Atta Biscuit",
        ],
        "sizes": [("150g Pack", 30.0), ("250g Pack", 45.0), ("400g Pack", 80.0)],
        "unit": "Pack",
    },
    "Instant Food": {
        "brands": ["Maggi", "Yippee", "Top Ramen", "Wai Wai", "Chings Secret"],
        "lines": [
            "2 Minute Noodles",
            "Masala Noodles",
            "Cup Noodles Spicy",
            "Hakka Noodles",
            "Curry Noodles",
        ],
        "sizes": [("70g Pack", 12.0), ("140g Pack", 24.0)],
        "unit": "Pack",
    },
    "Staples": {
        "brands": [
            "Aashirvaad",
            "Fortune",
            "Tata Salt",
            "Patanjali",
            "India Gate",
            "Tata Tea",
        ],
        "lines": [
            "Wheat Flour Atta",
            "Basmati Rice Long",
            "Toor Dal Yellow",
            "Sunflower Oil Refined",
            "Iodized Salt Fine",
            "Tea Dust Premium",
        ],
        "sizes": [("1kg Pack", 120.0), ("2kg Pack", 220.0), ("5kg Pack", 500.0)],
        "unit": "kg",
    },
    "Personal Care": {
        "brands": [
            "Lux",
            "Dove",
            "Dettol",
            "Colgate",
            "Pantene",
            "Parachute",
            "Nivea",
            "Himalaya Herbals",
        ],
        "lines": [
            "Rose Soap",
            "Antibacterial Soap",
            "Strong Teeth Toothpaste",
            "Damage Repair Shampoo",
            "Hair Oil Coconut",
            "Daily Moisturiser",
        ],
        "sizes": [("100g", 55.0), ("200ml", 90.0), ("500ml", 180.0)],
        "unit": "Pack",
    },
    "Cleaning": {
        "brands": ["Surf Excel", "Ariel", "Vim", "Harpic", "Lizol", "Mortein"],
        "lines": [
            "Washing Powder Regular",
            "Dishwash Bar Lemon",
            "Floor Cleaner Pine",
            "Toilet Cleaner Blue",
            "Mosquito Coil",
        ],
        "sizes": [("500g Pack", 65.0), ("1kg Pack", 120.0), ("1L Bottle", 80.0)],
        "unit": "Pack",
    },
}

# ═══════════════════════════════════════════════════════════════════════════
#  COMBO / AFFINITY TABLES
# ═══════════════════════════════════════════════════════════════════════════
STRONG_COMBOS = [
    ("Maggi", "Britannia", 0.38),
    ("Maggi", "Amul", 0.35),
    ("Maggi", "Tata Salt", 0.28),
    ("Lays", "Coca Cola", 0.40),
    ("Lays", "Pepsi", 0.35),
    ("Lays", "Kurkure", 0.30),
    ("Kurkure", "Pepsi", 0.32),
    ("Sprite", "Haldiram", 0.25),
    ("Britannia", "Mother Dairy", 0.35),
    ("Parle", "Amul", 0.28),
    ("Tata Salt", "Aashirvaad", 0.40),
    ("Fortune", "Aashirvaad", 0.35),
    ("Colgate", "Lux", 0.22),
    ("Top Ramen", "Yippee", 0.28),
]
CAT_AFFINITY = [
    ("Snacks", "Beverages", 0.52),
    ("Dairy", "Bakery", 0.42),
    ("Staples", "Staples", 0.30),
    ("Personal Care", "Cleaning", 0.35),
    ("Instant Food", "Dairy", 0.30),
    ("Bakery", "Dairy", 0.38),
    ("Confectionery", "Beverages", 0.28),
]


# ═══════════════════════════════════════════════════════════════════════════
#  DB CONNECTION
# ═══════════════════════════════════════════════════════════════════════════
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA cache_size=-64000;")
    conn.execute("PRAGMA foreign_keys=OFF;")
    return conn


# ═══════════════════════════════════════════════════════════════════════════
#  GENERATE NEW CUSTOMERS
# ═══════════════════════════════════════════════════════════════════════════
def insert_new_customers(conn, count, rng, first_names, last_names, city_areas):
    if count <= 0:
        return []
    c = conn.cursor()

    # Fetch names already in DB to avoid collisions
    existing = set(r[0] for r in c.execute("SELECT name FROM customer").fetchall())

    new_rows = []
    attempts = 0
    while len(new_rows) < count and attempts < count * 30:
        attempts += 1
        fi = int(rng.integers(0, len(first_names)))
        li = int(rng.integers(0, len(last_names)))
        name = f"{first_names[fi]} {last_names[li]}"
        if name in existing:
            # Append a short numeric suffix to force uniqueness
            name = f"{name} {int(rng.integers(10, 99))}"
        if name not in existing:
            existing.add(name)
            prefix = int(
                rng.choice(
                    [70, 72, 74, 76, 78, 80, 82, 84, 86, 88, 90, 92, 94, 96, 98, 99]
                )
            )
            mobile = f"{prefix}{int(rng.integers(10000000, 99999999)):08d}"
            address = str(city_areas[int(rng.integers(0, len(city_areas)))])
            new_rows.append((name, mobile, address))

    c.executemany(
        "INSERT OR IGNORE INTO customer (name, mobile, address) VALUES (?,?,?)",
        new_rows,
    )
    conn.commit()

    # Return newly inserted IDs
    names_inserted = [r[0] for r in new_rows]
    if not names_inserted:
        return []
    placeholders = ",".join("?" * len(names_inserted))
    new_ids = [
        r[0]
        for r in c.execute(
            f"SELECT id FROM customer WHERE name IN ({placeholders})", names_inserted
        ).fetchall()
    ]
    print(f"   ✅ {len(new_ids)} new customers inserted.")
    return new_ids


# ═══════════════════════════════════════════════════════════════════════════
#  GENERATE NEW SUPPLIERS
# ═══════════════════════════════════════════════════════════════════════════
def insert_new_suppliers(conn, count, rng, keywords, suffixes, city_areas):
    if count <= 0:
        return []
    c = conn.cursor()

    existing = set(r[0] for r in c.execute("SELECT name FROM supplier").fetchall())
    new_rows = []
    kw_list = list(keywords)
    suf_list = list(suffixes)
    rng.shuffle(kw_list)

    for kw in kw_list:
        for suf in suf_list:
            if len(new_rows) >= count:
                break
            name = f"{kw} {suf}"
            if name not in existing:
                existing.add(name)
                mobile = f"9{int(rng.integers(100000000, 999999999)):09d}"
                address = str(city_areas[int(rng.integers(0, len(city_areas)))])
                new_rows.append((name, mobile, address))
        if len(new_rows) >= count:
            break

    c.executemany(
        "INSERT OR IGNORE INTO supplier (name, mobile, address) VALUES (?,?,?)",
        new_rows,
    )
    conn.commit()

    names_inserted = [r[0] for r in new_rows]
    if not names_inserted:
        return []
    placeholders = ",".join("?" * len(names_inserted))
    new_ids = [
        r[0]
        for r in c.execute(
            f"SELECT id FROM supplier WHERE name IN ({placeholders})", names_inserted
        ).fetchall()
    ]
    print(f"   ✅ {len(new_ids)} new suppliers inserted.")
    return new_ids


# ═══════════════════════════════════════════════════════════════════════════
#  GENERATE NEW PRODUCTS
# ═══════════════════════════════════════════════════════════════════════════
def insert_new_products(conn, count, rng, catalog):
    if count <= 0:
        return []
    c = conn.cursor()

    existing_products = set(
        r[0] for r in c.execute("SELECT name FROM product").fetchall()
    )
    new_product_rows = []  # (name, category)
    new_variant_rows = []  # (product_name, variant_name, price, unit, stock)
    inserted = 0

    categories = list(catalog.keys())
    for _ in range(count * 5):
        if inserted >= count:
            break
        cat_name = str(categories[int(rng.integers(0, len(categories)))])
        cat = catalog[cat_name]
        brands = cat["brands"]
        lines = cat["lines"]
        brand = brands[int(rng.integers(0, len(brands)))]
        line = lines[int(rng.integers(0, len(lines)))]
        pname = f"{brand} {line}"
        if pname in existing_products:
            continue
        existing_products.add(pname)
        new_product_rows.append((pname, cat_name))
        inserted += 1

        # Variants
        sizes = cat["sizes"]
        n_var = int(rng.integers(1, min(3, len(sizes)) + 1))
        for sname, base_price in sizes[:n_var]:
            price = round(base_price * float(rng.uniform(0.9, 1.3)), 2)
            stock = float(rng.integers(15, 60))
            new_variant_rows.append((pname, sname, price, cat["unit"], stock))

    c.executemany(
        "INSERT OR IGNORE INTO product (name, category) VALUES (?,?)", new_product_rows
    )
    conn.commit()

    # Fetch product IDs for newly inserted ones
    names_inserted = [r[0] for r in new_product_rows]
    if not names_inserted:
        return []
    placeholders = ",".join("?" * len(names_inserted))
    pid_map = {
        r[1]: r[0]
        for r in c.execute(
            f"SELECT id, name FROM product WHERE name IN ({placeholders})",
            names_inserted,
        ).fetchall()
    }

    variant_db_rows = [
        (pid_map[pname], vname, price, unit, stock)
        for pname, vname, price, unit, stock in new_variant_rows
        if pname in pid_map
    ]
    c.executemany(
        "INSERT INTO product_variant (product_id, name, price, unit, current_stock) VALUES (?,?,?,?,?)",
        variant_db_rows,
    )
    conn.commit()

    new_variant_ids = [
        r[0]
        for r in c.execute(
            f"SELECT id FROM product_variant WHERE product_id IN "
            f"(SELECT id FROM product WHERE name IN ({placeholders}))",
            names_inserted,
        ).fetchall()
    ]
    print(
        f"   ✅ {len(names_inserted)} new products, {len(new_variant_ids)} variants inserted."
    )
    return new_variant_ids


# ═══════════════════════════════════════════════════════════════════════════
#  LOAD LIVE STATE FROM DB
# ═══════════════════════════════════════════════════════════════════════════
def load_live_state(conn):
    c = conn.cursor()
    state = {}

    # All variant IDs + prices + reorder points
    rows = c.execute(
        "SELECT pv.id, pv.price, pv.current_stock, p.name, p.category FROM product_variant pv JOIN product p ON p.id = pv.product_id"
    ).fetchall()
    state["all_variant_ids"] = [r[0] for r in rows]
    state["variant_price_map"] = {r[0]: r[1] for r in rows}
    state["live_inventory"] = {r[0]: float(r[2]) for r in rows}
    state["variant_to_product_name"] = {r[0]: r[3] for r in rows}
    state["variant_to_category"] = {r[0]: r[4] for r in rows}
    state["variant_reorder_point"] = {
        r[0]: max(5.0, round(float(r[2]) * 0.18, 1)) for r in rows
    }

    # Category → variant IDs
    cat_vids = {}
    for vid, _, _, _, cat in rows:
        cat_vids.setdefault(cat, []).append(vid)
    state["category_to_variant_ids"] = cat_vids

    # Product → variant IDs
    prod_vids = {}
    for vid, _, _, pname, _ in rows:
        prod_vids.setdefault(pname, []).append(vid)
    state["product_name_to_variant_ids"] = prod_vids

    # Categories list
    state["categories"] = list(cat_vids.keys())

    # Customer IDs + live balances + segments (from maps if available)
    cust_rows = c.execute("SELECT id, balance FROM customer").fetchall()
    state["customer_ids"] = [r[0] for r in cust_rows]
    state["live_balances"] = {r[0]: float(r[1]) for r in cust_rows}

    # Supplier IDs
    state["supplier_ids"] = [
        r[0] for r in c.execute("SELECT id FROM supplier WHERE is_deleted=0").fetchall()
    ]

    # Max IDs
    state["max_sale_id"] = c.execute(
        "SELECT IFNULL(MAX(id),0) FROM credit_sale"
    ).fetchone()[0]
    state["max_inv_id"] = c.execute(
        "SELECT IFNULL(MAX(id),0) FROM purchase_invoice"
    ).fetchone()[0]

    return state


# ═══════════════════════════════════════════════════════════════════════════
#  LOAD MAPS  (customer behaviour metadata — segments, churn, credit limits)
# ═══════════════════════════════════════════════════════════════════════════
def load_maps_if_available():
    """
    Load nexus_seed_maps.json for customer behaviour metadata.
    If not available (e.g. fresh install), returns sensible defaults.
    """
    if not os.path.exists(MAPS_PATH):
        return None

    with open(MAPS_PATH) as f:
        raw = json.load(f)

    maps = {}
    maps["customer_segments"] = {
        int(k): v for k, v in raw.get("customer_segments", {}).items()
    }
    maps["churn_days"] = {int(k): v for k, v in raw.get("churn_days", {}).items()}
    maps["temp_churn"] = {int(k): v for k, v in raw.get("temp_churn", {}).items()}
    maps["customer_join_day"] = {
        int(k): v for k, v in raw.get("customer_join_day", {}).items()
    }
    maps["credit_limits"] = {int(k): v for k, v in raw.get("credit_limits", {}).items()}
    maps["credit_customer_ids"] = [int(x) for x in raw.get("credit_customer_ids", [])]
    maps["supplier_category_map"] = {
        int(k): v for k, v in raw.get("supplier_category_map", {}).items()
    }
    return maps


# ═══════════════════════════════════════════════════════════════════════════
#  DETERMINE START DATE & DAY INDEX
# ═══════════════════════════════════════════════════════════════════════════
def resolve_start(conn):
    c = conn.cursor()
    if START_FROM == "auto":
        row = c.execute("SELECT MAX(DATE(sale_date)) FROM credit_sale").fetchone()[0]
        if row:
            last_date = datetime.strptime(row, "%Y-%m-%d").date()
            start = last_date + timedelta(days=1)
        else:
            # Empty DB — start 30 days ago
            start = date.today() - timedelta(days=DAYS)
    else:
        start = datetime.strptime(START_FROM, "%Y-%m-%d").date()

    # Day index: days since first ever sale
    row = c.execute("SELECT MIN(DATE(sale_date)) FROM credit_sale").fetchone()[0]
    if row:
        seed_start = datetime.strptime(row, "%Y-%m-%d").date()
        base_day = (start - seed_start).days
    else:
        base_day = 3650  # assume year 10 position if no sales yet

    return start, base_day


# ═══════════════════════════════════════════════════════════════════════════
#  DAILY TX COUNT  — S-curve (same as all other scripts)
# ═══════════════════════════════════════════════════════════════════════════
def daily_tx_count(day_idx, current_date, rng):
    L, k, t0 = 1000.0, 0.0012, 1825.0
    base = L / (1.0 + math.exp(-k * (day_idx - t0)))
    m, d, wd = current_date.month, current_date.day, current_date.weekday()
    if wd >= 5:
        base *= 1.30
    if d <= 7:
        base *= 1.20
    if (m == 10 and d >= 15) or (m == 11 and d <= 15):
        base *= 1.45
    elif m == 3 and 5 <= d <= 25:
        base *= 1.30
    elif m == 1 and d <= 10:
        base *= 1.25
    elif m in [6, 7] and 10 <= d <= 25:
        base *= 1.20
    return max(40, min(1100, int(rng.normal(base, base * 0.08))))


# ═══════════════════════════════════════════════════════════════════════════
#  ELIGIBLE BUYERS FOR A DAY
# ═══════════════════════════════════════════════════════════════════════════
def get_buyers(customer_ids, day_idx, maps, rng, target):
    SEG_LAMBDA = {"loyal": 0.26, "credit": 0.16, "occasional": 0.07, "at_risk": 0.12}

    eligible = []
    for cid in customer_ids:
        if maps:
            if day_idx < maps["customer_join_day"].get(cid, 0):
                continue
            if day_idx > maps["churn_days"].get(cid, 9999):
                continue
            tc = maps["temp_churn"].get(cid)
            if tc and tc[0] <= day_idx <= tc[1]:
                continue
        eligible.append(cid)

    buyers = []
    for cid in eligible:
        seg = maps["customer_segments"].get(cid, "occasional") if maps else "occasional"
        lam = SEG_LAMBDA.get(seg, 0.07)
        if seg == "at_risk" and maps:
            lam = max(0.03, lam * (1.0 - day_idx / (3650 * 1.5)))
        if rng.random() < lam:
            buyers.append(cid)

    if len(buyers) > target:
        buyers = list(rng.choice(buyers, size=target, replace=False))
    elif len(buyers) < int(target * 0.65) and eligible:
        non_buyers = [c for c in eligible if c not in set(buyers)]
        shortfall = min(int(target * 0.65) - len(buyers), len(non_buyers))
        if shortfall > 0:
            buyers += list(rng.choice(non_buyers, size=shortfall, replace=False))

    return buyers


# ═══════════════════════════════════════════════════════════════════════════
#  BASKET BUILDER
# ═══════════════════════════════════════════════════════════════════════════
def build_basket(cid, day_idx, current_date, state, rng):
    all_vids = state["all_variant_ids"]
    cat_vids = state["category_to_variant_ids"]
    prod_vids = state["product_name_to_variant_ids"]
    categories = state["categories"]
    basket = []
    m = current_date.month

    # Preferred category
    pref_cat_idx = cid % len(categories)
    pref_cat = categories[pref_cat_idx]
    secondary_cat = categories[(pref_cat_idx + 1) % len(categories)]
    pv = cat_vids.get(pref_cat, [])
    sec_vids = cat_vids.get(secondary_cat, [])
    if pv:
        for _ in range(int(rng.integers(2, 5))):
            basket.append(int(pv[int(rng.integers(0, len(pv)))]))
    if sec_vids and rng.random() < 0.55:
        basket.append(int(sec_vids[int(rng.integers(0, len(sec_vids)))]))
    # Combo affinity
    b_prods = set(state["variant_to_product_name"].get(v, "").lower() for v in basket)
    for kw_a, kw_b, prob in STRONG_COMBOS:
        if any(kw_a.lower() in bp for bp in b_prods) and rng.random() < prob:
            partner = []
            for pname, vlist in prod_vids.items():
                if kw_b.lower() in pname.lower():
                    partner.extend(vlist)
            if partner:
                basket.append(int(partner[int(rng.integers(0, len(partner)))]))

    # Category affinity
    b_cats = set(state["variant_to_category"].get(v, "") for v in basket)
    for cat_a, cat_b, prob in CAT_AFFINITY:
        if cat_a in b_cats and rng.random() < prob:
            vb = cat_vids.get(cat_b, [])
            if vb:
                basket.append(int(vb[int(rng.integers(0, len(vb)))]))

    # Random extras
    scoped_pool = pv + sec_vids if sec_vids else pv
    if not scoped_pool:
        scoped_pool = all_vids
    for _ in range(int(rng.integers(1, 3))):
        basket.append(int(scoped_pool[int(rng.integers(0, len(scoped_pool)))]))
    if rng.random() < 0.25:
        basket.append(int(all_vids[int(rng.integers(0, len(all_vids)))]))

    # Seasonal
    if m in [4, 5, 6]:
        bev = cat_vids.get("Beverages", [])
        if bev and rng.random() < 0.45:
            basket.append(int(bev[int(rng.integers(0, len(bev)))]))
    elif m in [11, 12, 1]:
        sta = cat_vids.get("Staples", [])
        if sta and rng.random() < 0.35:
            basket.append(int(sta[int(rng.integers(0, len(sta)))]))
    elif m in [10, 11]:
        conf = cat_vids.get("Confectionery", [])
        if conf and rng.random() < 0.40:
            basket.append(int(conf[int(rng.integers(0, len(conf)))]))

    basket = list(dict.fromkeys(basket))
    if not basket:
        basket = [int(all_vids[int(rng.integers(0, len(all_vids)))])]
    return basket[:18]


# ═══════════════════════════════════════════════════════════════════════════
#  PAYMENT HANDLER
# ═══════════════════════════════════════════════════════════════════════════
def handle_payment(cid, total_bill, dt, state, maps, credit_set, rng, payments_q):
    if cid not in credit_set:
        payments_q.append(
            (
                cid,
                dt.strftime("%Y-%m-%d %H:%M:%S"),
                round(float(total_bill), 2),
                random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[0],
            )
        )
        return

    state["live_balances"][cid] = state["live_balances"].get(cid, 0.0) + total_bill
    debt = state["live_balances"][cid]
    limit = maps["credit_limits"].get(cid, 15000.0) if maps else 15000.0
    is_sw = dt.day <= 7
    is_fm = dt.month in [10, 11, 1, 3]
    pay = 0.0

    if debt > limit:
        pay = min(debt - limit + float(rng.uniform(300, 2500)), debt)
    elif is_sw and debt > 400:
        prob = 0.72 + (0.10 if is_fm else 0.0)
        if rng.random() < prob:
            pay = round(debt * float(rng.uniform(0.5, 1.0)), 2)
    if debt > 80000:
        pay = max(pay, debt - float(rng.uniform(10000, 25000)))

    if pay > 0:
        pay = min(round(pay, 2), debt)
        state["live_balances"][cid] -= pay
        state["live_balances"][cid] = max(0.0, state["live_balances"][cid])
        payments_q.append(
            (
                cid,
                dt.strftime("%Y-%m-%d %H:%M:%S"),
                pay,
                random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[0],
            )
        )


# ═══════════════════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="NexusRetailOS flex seeder")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview stats without writing to DB"
    )
    args = parser.parse_args()

    t0 = time.time()

    print("=" * 64)
    print("  NexusRetailOS — Flex Seed")
    print(f"  DB      : {DB_PATH}")
    print(
        f"  Config  : {DAYS} days | +{NEW_CUSTOMERS} customers | "
        f"+{NEW_SUPPLIERS} suppliers | +{NEW_PRODUCTS} products"
    )
    print(f"  Dry run : {args.dry_run}")
    print("=" * 64)

    if not os.path.exists(DB_PATH):
        print(f"\n❌  Database not found: {DB_PATH}")
        print("   Run the 10-year master seed first.")
        sys.exit(1)

    # ── Load name banks (from gen_master_data.py or inline) ───────────────
    print("\n📚  Loading name banks…")
    first_names, last_names, city_areas, sup_keywords, sup_suffixes, catalog = (
        _load_name_banks()
    )

    conn = get_conn()
    rng = np.random.default_rng(int(datetime.now().strftime("%Y%m%d%H%M")))

    # ── Step 1: Insert new entities ────────────────────────────────────────
    if not args.dry_run:
        if NEW_CUSTOMERS > 0 or NEW_SUPPLIERS > 0 or NEW_PRODUCTS > 0:
            print("\n➕  Inserting new entities…")

        if NEW_CUSTOMERS > 0:
            insert_new_customers(
                conn, NEW_CUSTOMERS, rng, first_names, last_names, city_areas
            )
        if NEW_SUPPLIERS > 0:
            insert_new_suppliers(
                conn, NEW_SUPPLIERS, rng, sup_keywords, sup_suffixes, city_areas
            )
        if NEW_PRODUCTS > 0:
            insert_new_products(conn, NEW_PRODUCTS, rng, catalog)
    else:
        if NEW_CUSTOMERS > 0:
            print(f"\n   [DRY RUN] Would insert {NEW_CUSTOMERS} new customers")
        if NEW_SUPPLIERS > 0:
            print(f"   [DRY RUN] Would insert {NEW_SUPPLIERS} new suppliers")
        if NEW_PRODUCTS > 0:
            print(f"   [DRY RUN] Would insert {NEW_PRODUCTS} new products")

    # ── Step 2: Load live state ────────────────────────────────────────────
    print("\n📂  Loading live state from DB…", end=" ", flush=True)
    state = load_live_state(conn)
    maps = load_maps_if_available()
    credit_set = (
        set(maps["credit_customer_ids"])
        if maps
        else set(
            cid
            for cid in state["customer_ids"]
            if state["live_balances"].get(cid, 0.0) > 0
        )
    )
    print(
        f"✅  {len(state['customer_ids']):,} customers | "
        f"{len(state['all_variant_ids']):,} variants | "
        f"{len(state['supplier_ids']):,} suppliers"
    )

    # ── Step 3: Resolve start date ─────────────────────────────────────────
    start_date, base_day_idx = resolve_start(conn)
    end_date = start_date + timedelta(days=DAYS - 1)
    print(f"\n📅  Simulating: {start_date} → {end_date}  ({DAYS} days)")
    print(f"   S-curve base day index: {base_day_idx}")

    # ── Step 4: Simulate ───────────────────────────────────────────────────
    print(f"\n⏳  Running simulation…\n")

    sale_counter = state["max_sale_id"]
    inv_counter = state["max_inv_id"]
    inv_seq = {}
    c = conn.cursor()

    all_sales_q = []
    all_items_q = []
    all_payments_q = []
    all_invoices_q = []
    all_p_items_q = []

    total_revenue = 0.0
    total_sales = 0
    total_items = 0

    for d in range(DAYS):
        current_date = datetime.combine(
            start_date + timedelta(days=d), datetime.min.time()
        )
        day_idx = base_day_idx + d

        # Skip if already seeded (unless force)
        date_str = current_date.strftime("%Y-%m-%d")
        existing_count = c.execute(
            "SELECT COUNT(*) FROM credit_sale WHERE DATE(sale_date)=?", (date_str,)
        ).fetchone()[0]
        if existing_count > 0:
            print(
                f"   ⏭️   {date_str} — already has {existing_count:,} sales, skipping"
            )
            continue

        target = daily_tx_count(day_idx, current_date, rng)
        buyers = get_buyers(state["customer_ids"], day_idx, maps, rng, target)

        sales_q = []
        items_q = []
        payments_q = []
        restock_map = {}

        hours = rng.integers(8, 21, max(1, len(buyers)))
        minutes = rng.integers(0, 60, max(1, len(buyers)))
        seconds = rng.integers(0, 60, max(1, len(buyers)))

        day_revenue = 0.0

        for bi, cid in enumerate(buyers):
            sale_counter += 1
            sale_id = sale_counter
            dt = current_date.replace(
                hour=int(hours[bi]), minute=int(minutes[bi]), second=int(seconds[bi])
            )
            sales_q.append((sale_id, cid, dt.strftime("%Y-%m-%d %H:%M:%S")))

            basket = build_basket(cid, day_idx, current_date, state, rng)
            total_bill = 0.0

            for vid in basket:
                qty = float(rng.integers(1, 5))
                price = round(float(state["variant_price_map"].get(vid, 20.0)), 2)
                total_bill += qty * price
                items_q.append((sale_id, vid, qty, price))
                total_items += 1

                state["live_inventory"][vid] = (
                    state["live_inventory"].get(vid, 0.0) - qty
                )
                rp = state["variant_reorder_point"].get(vid, 8.0)
                if state["live_inventory"][vid] < rp:
                    rqty = float(rng.integers(40, 130))
                    cost = round(price * float(rng.uniform(0.65, 0.78)), 2)
                    if vid not in restock_map or rqty > restock_map[vid][0]:
                        restock_map[vid] = (rqty, cost)
                    state["live_inventory"][vid] += rqty

            day_revenue += total_bill
            total_revenue += total_bill
            total_sales += 1

            handle_payment(
                cid, total_bill, dt, state, maps, credit_set, rng, payments_q
            )

        # Spontaneous payments
        sp_rand = rng.random(len(list(credit_set)))
        sp_frac = rng.random(len(list(credit_set)))
        is_fest = current_date.month in [10, 11, 1, 3]
        sp_prob = 0.14 if is_fest else 0.08
        for si, sp_cid in enumerate(list(credit_set)):
            debt = state["live_balances"].get(sp_cid, 0.0)
            if debt < 100.0 or sp_rand[si] >= sp_prob:
                continue
            pa = round(min(debt * float(sp_frac[si] * 0.75 + 0.25), debt), 2)
            if pa < 1.0:
                continue
            state["live_balances"][sp_cid] -= pa
            state["live_balances"][sp_cid] = max(0.0, state["live_balances"][sp_cid])
            h = int(rng.integers(9, 18))
            mn = int(rng.integers(0, 60))
            payments_q.append(
                (
                    sp_cid,
                    f"{date_str} {h:02d}:{mn:02d}:00",
                    pa,
                    random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[0],
                )
            )

        # Year-end sweep
        if current_date.month == 12 and current_date.day == 31:
            for ye_cid in list(credit_set):
                debt = state["live_balances"].get(ye_cid, 0.0)
                if debt > 15000:
                    frac = float(rng.uniform(0.60, 0.92))
                    pa = round(debt * frac, 2)
                    state["live_balances"][ye_cid] -= pa
                    state["live_balances"][ye_cid] = max(
                        0.0, state["live_balances"][ye_cid]
                    )
                    payments_q.append(
                        (
                            ye_cid,
                            f"{date_str} 23:59:00",
                            pa,
                            random.choices(PAYMENT_MODES, weights=PAYMENT_WEIGHTS, k=1)[
                                0
                            ],
                        )
                    )

        # Invoices from restocks
        invoices_q = []
        p_items_q = []
        for vid, (rqty, rcost) in restock_map.items():
            cat = state["variant_to_category"].get(vid, "")
            assigned = None
            if maps:
                for sid_k, cats in maps["supplier_category_map"].items():
                    if cat in cats:
                        assigned = sid_k
                        break
            if assigned is None:
                assigned = int(
                    state["supplier_ids"][
                        int(rng.integers(0, len(state["supplier_ids"])))
                    ]
                )
            inv_counter += 1
            seq = inv_seq.get(assigned, 0) + 1
            inv_seq[assigned] = seq
            ih = int(rng.integers(4, 8))
            ref = f"INV-{current_date.year}{current_date.month:02d}-{assigned:04d}-{seq:05d}"
            idt = current_date.replace(
                hour=ih, minute=int(rng.integers(0, 60)), second=0
            )
            invoices_q.append(
                (
                    inv_counter,
                    assigned,
                    idt.strftime("%Y-%m-%d %H:%M:%S"),
                    round(float(rqty * rcost), 2),
                    ref,
                )
            )
            p_items_q.append((inv_counter, int(vid), float(rqty), float(rcost)))

        # Accumulate
        all_sales_q.extend(sales_q)
        all_items_q.extend(items_q)
        all_payments_q.extend(payments_q)
        all_invoices_q.extend(invoices_q)
        all_p_items_q.extend(p_items_q)

        print(
            f"   📅  {date_str} — {len(sales_q):>4} sales | "
            f"₹{day_revenue:>10,.0f} | "
            f"day index {day_idx}"
        )

    # ── Step 5: Write ──────────────────────────────────────────────────────
    print(f"\n{'─' * 64}")
    print(
        f"  Total: {total_sales:,} sales | {total_items:,} items | ₹{total_revenue:,.0f}"
    )
    print(f"{'─' * 64}")

    if args.dry_run:
        print("\n  [DRY RUN] Nothing written to database.")
        conn.close()
        return

    print("\n💾  Writing to database…", end=" ", flush=True)

    if all_sales_q:
        c.executemany(
            "INSERT INTO credit_sale (id, customer_id, sale_date) VALUES (?,?,?)",
            all_sales_q,
        )
        c.executemany(
            "INSERT INTO credit_sale_item (sale_id, variant_id, quantity, price_at_sale) VALUES (?,?,?,?)",
            all_items_q,
        )
    if all_payments_q:
        c.executemany(
            "INSERT INTO payment (customer_id, payment_date, amount) VALUES (?,?,?)",
            all_payments_q,
        )
    if all_invoices_q:
        c.executemany(
            "INSERT INTO purchase_invoice (id, supplier_id, invoice_date, total_amount, reference_number) VALUES (?,?,?,?,?)",
            all_invoices_q,
        )
        c.executemany(
            "INSERT INTO purchase_item (invoice_id, variant_id, quantity, unit_cost) VALUES (?,?,?,?)",
            all_p_items_q,
        )

    # Bulk-update changed balances
    changed = set(r[0] for r in all_payments_q) | set(r[1] for r in all_sales_q)
    if changed:
        c.executemany(
            "UPDATE customer SET balance = ? WHERE id = ?",
            [
                (round(max(0.0, state["live_balances"].get(cid, 0.0)), 2), cid)
                for cid in changed
            ],
        )

    # Update restocked stock levels
    restocked_vids = set(r[2] for r in all_p_items_q)
    if restocked_vids:
        c.executemany(
            "UPDATE product_variant SET current_stock = ? WHERE id = ?",
            [
                (round(max(0.0, state["live_inventory"].get(vid, 0.0)), 1), vid)
                for vid in restocked_vids
            ],
        )

    conn.commit()
    conn.execute("ANALYZE;")
    conn.close()

    elapsed = time.time() - t0
    print("✅")
    print(f"\n{'=' * 64}")
    print(f"  ✅  Flex seed complete  ({elapsed:.1f}s)")
    print(
        f"      {DAYS} days | {total_sales:,} sales | "
        f"{total_items:,} items | ₹{total_revenue:,.0f}"
    )
    print(f"{'=' * 64}\n")


if __name__ == "__main__":
    main()
