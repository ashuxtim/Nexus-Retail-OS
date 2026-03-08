import requests
import json
import time

url = "http://127.0.0.1:8000/ask"

queries = [
    "how many types of chips and when will stock finish",
    "which cold drinks are running low",
    "customers who buy Lays, are any of them at churn risk",
    "what do people buy with Maggi",
    "find supplier for haldiram",
    "get ID for Ramesh Sharma"
]

for q in queries:
    print(f"\n========== QUERY: {q} ==========\n")
    try:
        res = requests.post(url, json={"text": q}, timeout=60)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text}")
    except Exception as e:
        print(f"Error: {e}")
