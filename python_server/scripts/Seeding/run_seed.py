#!/usr/bin/env python3
"""
run_seed.py  —  NexusRetailOS 10-Year Data Seed  ★ MASTER RUNNER ★
══════════════════════════════════════════════════════════════════════
  Just run this one file.  It imports and calls the other three.

  Usage:
      python run_seed.py

  All three scripts must be in the same directory as run_seed.py:
      run_seed.py            ← YOU ARE HERE
      gen_master_data.py     ← Step 1: products / customers / suppliers
      gen_transactions.py    ← Step 2: 10-year daily simulation
      gen_validate.py        ← Step 3: ML-compatibility checks

  Database written to:
      Windows : %APPDATA%\\NexusRetailOS\\nexus.db
      Linux   : ~/.config/NexusRetailOS/nexus.db
      Override: set env var  NEXUS_USER_DATA=/your/path

  ⏱  Expected runtime:
      Step 1  — ~1–3 min      (product / customer / supplier generation)
      Step 2  — ~25–60 min    (10-year daily transaction simulation)
      Step 3  — ~15 sec       (validation queries)

  ⚠  Requirements:
      pip install numpy
      (That's it.  sqlite3 is stdlib.)

  ⚠  Re-seeding:
      Delete nexus.db and re-run.  Scripts detect existing data and skip.
══════════════════════════════════════════════════════════════════════
"""

import sys
import os
import time

# ─── Make sure sibling scripts are importable ────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

# ─── Dependency check ────────────────────────────────────────────────────
def check_deps():
    missing = []
    try:
        import numpy
    except ImportError:
        missing.append("numpy")

    if missing:
        print("❌  Missing Python packages. Install with:")
        print(f"       pip install {' '.join(missing)}")
        sys.exit(1)

# ─── Import steps ────────────────────────────────────────────────────────
def import_steps():
    """Import all three step modules with helpful error messages."""
    try:
        import gen_master_data
    except ImportError as e:
        print(f"❌  Cannot import gen_master_data.py — {e}")
        print("   Ensure gen_master_data.py is in the same folder as run_seed.py")
        sys.exit(1)

    try:
        import gen_transactions
    except ImportError as e:
        print(f"❌  Cannot import gen_transactions.py — {e}")
        sys.exit(1)

    try:
        import gen_validate
    except ImportError as e:
        print(f"❌  Cannot import gen_validate.py — {e}")
        sys.exit(1)

    return gen_master_data, gen_transactions, gen_validate


# ─── Banner ──────────────────────────────────────────────────────────────
BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          NexusRetailOS — 10-Year Data Seed                   ║
║   5,000 products  ·  10,000 customers  ·  1,000 suppliers    ║
║   3,650 days  ·  ~1.8M sales  ·  ~9M items  ·  real Indian  ║
╚══════════════════════════════════════════════════════════════╝
"""


def main():
    check_deps()
    gm, gt, gv = import_steps()

    print(BANNER)
    wall_start = time.time()

    # ── STEP 1: Master Data ───────────────────────────────────────────────
    print("━" * 64)
    print("  STEP 1 / 3  —  Master Data  (products, customers, suppliers)")
    print("━" * 64)
    t1 = time.time()
    try:
        gm.main()
    except Exception as e:
        print(f"\n❌  STEP 1 FAILED: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    print(f"  ⏱  Step 1 finished in {time.time()-t1:.1f}s\n")

    # ── STEP 2: Transactions ──────────────────────────────────────────────
    print("━" * 64)
    print("  STEP 2 / 3  —  Transaction Simulation  (10 years, ~30–60 min)")
    print("━" * 64)
    t2 = time.time()
    try:
        gt.main()
    except Exception as e:
        print(f"\n❌  STEP 2 FAILED: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)
    print(f"  ⏱  Step 2 finished in {(time.time()-t2)/60:.1f} min\n")

    # ── STEP 3: Validate ──────────────────────────────────────────────────
    print("━" * 64)
    print("  STEP 3 / 3  —  Validation  (ML-compatibility checks)")
    print("━" * 64)
    t3 = time.time()
    try:
        gv.main()
    except SystemExit as e:
        if e.code != 0:
            print(f"\n⚠️  Validation completed with failures (exit code {e.code}).")
            print("   The database is still usable — review hints above.")
        # Don't re-raise; we still want the final summary
    except Exception as e:
        print(f"\n❌  STEP 3 FAILED: {e}")
        import traceback; traceback.print_exc()
    print(f"  ⏱  Step 3 finished in {time.time()-t3:.1f}s\n")

    # ── All done ──────────────────────────────────────────────────────────
    total = time.time() - wall_start
    print("╔══════════════════════════════════════════════════════════════╗")
    print(f"║  🎉  ALL STEPS COMPLETE  —  Total time: {total/60:.1f} min")
    print("║")
    print("║  Open NexusRetailOS and the data will be ready.")
    print("║  All 4 ML models (XGBoost, FP-Growth, Prophet, Monte Carlo)")
    print("║  will have 10 years of realistic Indian retail data.")
    print("╚══════════════════════════════════════════════════════════════╝")


if __name__ == "__main__":
    main()
