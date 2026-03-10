# Seed today (normal daily use)
python daily_seed.py

# Preview without writing anything
python daily_seed.py --dry-run

# Backfill a missed day
python daily_seed.py --date 2026-03-08

# Force re-seed a day that already has data
python daily_seed.py --date 2026-03-09 --force

----------------------------------------------------

DAYS          = 30       # how many days to simulate
NEW_CUSTOMERS = 10       # new customers to insert before simulation
NEW_SUPPLIERS = 0        # new suppliers to insert
NEW_PRODUCTS  = 0        # new products + variants to insert
START_FROM    = "auto"   # "auto" or "2025-10-15"
