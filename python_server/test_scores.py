import os
import sqlite3
import chromadb
from sentence_transformers import SentenceTransformer

# Setup dummy db to pass vector_store init
conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS product_variant (id INTEGER PRIMARY KEY, product_id INTEGER, name TEXT, price REAL, current_stock REAL, unit TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS product (id INTEGER PRIMARY KEY, name TEXT, category TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS customer (id INTEGER PRIMARY KEY, name TEXT, mobile TEXT, address TEXT, balance REAL)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS supplier (id INTEGER PRIMARY KEY, name TEXT, mobile TEXT)''')
cursor.execute('''INSERT OR IGNORE INTO product (id, name, category) VALUES (1, 'Lays', 'Snacks')''')
cursor.execute('''INSERT OR IGNORE INTO product_variant (id, product_id, name, current_stock) VALUES (1, 1, 'Classic', 50)''')
cursor.execute('''INSERT OR IGNORE INTO product_variant (id, product_id, name, current_stock) VALUES (2, 1, 'Masala', 50)''')
conn.commit()
conn.close()

from vector_store import SmartSearchEngine
engine = SmartSearchEngine("db.sqlite3", base_dir=".")
engine.initialize()

import time
time.sleep(10) # wait for model load and embedding

res = engine.search("product", "Lays Classic", limit=3)
print("\n--- Testing Exact Match (Lays Classic) ---")
if "matches" in res:
    for m in res["matches"]:
        print(f"Match: {m['product_name']} {m['variant_name']} - Score: {m['similarity']}%")
else:
    print(res)

res = engine.search("product", "Laays Masala", limit=3)
print("\n--- Testing Partial Match (Laays Masala) ---")
if "matches" in res:
    for m in res["matches"]:
        print(f"Match: {m['product_name']} {m['variant_name']} - Score: {m['similarity']}%")

res = engine.search("product", "Potato Chips", limit=3)
print("\n--- Testing Concept (Potato Chips) ---")
if "matches" in res:
    for m in res["matches"]:
        print(f"Match: {m['product_name']} {m['variant_name']} - Score: {m['similarity']}%")
