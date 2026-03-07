# 🐛 Nexus Retail OS — Full Audit Report

> **Date:** 2026-03-07  
> **Scope:** Electron layer, Python backend, React frontend, database schema  
> **Status:** Read-only audit — no files edited

---

## 🔴 CRITICAL (Will break the app, lose data, or create security holes)

### 1. Hardcoded Encryption Key in Source Code
**File:** `electron/database/repositories/SettingsRepository.js:5`  
```js
const ENCRYPTION_KEY = 'vOVH6sdmpNWjRRIqCc7rdxs01lwHzfr3';
```
**Why it breaks:** Anyone with access to the source code (GitHub, decompiled app) can decrypt all API keys. This is a **security vulnerability** — the key should be derived from a machine-specific secret (e.g., `electron-safeStorage`, OS keychain, or `crypto.scryptSync(machineId)`).

---

### 2. Deleting a Sale Does NOT Recalculate Customer Balance Correctly
**File:** `electron/database/repositories/SaleRepository.js:100-114`  
**Why it breaks:** When `deleteSale()` is called, it restores stock via `current_stock + quantity`, but relies on the `calc_balance_delete_item` trigger (in `db_manager.js:94`) to fix the customer's balance. **The trigger fires on `DELETE FROM credit_sale_item`**, which happens via `ON DELETE CASCADE` when the parent `credit_sale` row is deleted. This works **only if `foreign_keys = ON`** is set. If the DB connection ever loses that pragma (e.g., different connection), the cascade won't fire, and **customer balances become permanently wrong**.  
**Risk:** Data corruption — incorrect outstanding balances.

---

### 3. Deleting a Payment Does NOT Recalculate Balance
**File:** `electron/database/repositories/SaleRepository.js:203-208`  
```js
deletePayment(id) {
    getDB().prepare('DELETE FROM payment WHERE id = ?').run(id);
    return { success: true };
}
```
**Why it breaks:** The `calc_balance_delete_payment` trigger adds `OLD.amount` back to the customer's balance. But the payment record is already deleted, so **the `customer_id` is looked up from `OLD.customer_id`**. This actually works via the trigger. **HOWEVER** — there's no confirmation dialog, no undo capability, and the IPC handler at `main.js:898-903` doesn't update any cache. If the user deletes a ₹50,000 payment by mistake, there's **no way to recover**.

---

### 4. `deletePurchase()` Can Make Stock Go Negative
**File:** `electron/database/repositories/SupplierRepository.js:168-189`  
```js
const revertStock = db.prepare('UPDATE product_variant SET current_stock = current_stock - ? WHERE id = ?');
```
**Why it breaks:** If a purchase added 100 units, and 90 were already sold, deleting the purchase will set stock to `10 - 100 = -90`. There is **no stock guard** here (unlike the one added for sales). This creates **negative stock** — the exact issue the user explicitly asked to prevent.

---

### 5. `softDelete` Is Actually a HARD DELETE (Supplier)
**File:** `electron/database/repositories/SupplierRepository.js:86-91`  
```js
softDelete(id) {
    getDB().prepare('DELETE FROM supplier WHERE id = ?').run(id);
    return { success: true };
}
```
**Why it breaks:** Despite the function name `softDelete` and the schema having an `is_deleted` column (`supplier` table, `db_manager.js:45`), this performs a **permanent hard DELETE**. The `restore()` function also just returns `{ error: "Cannot restore permanently deleted supplier" }`. This means:
- All supplier data is irreversibly lost
- Any `purchase_invoice` records linked to the supplier will have `supplier_id` set to NULL (due to `ON DELETE SET NULL`)
- The UI at `supplier:get-deleted` returns `[]` always — the "deleted suppliers" feature is completely broken

---

### 6. `createFullTransaction` Doesn't Forward `paymentMode` 
**File:** `electron/main.js:929-936`  
```js
ipcMain.handle('sale:create-full', async (e, data) => {
    const result = SaleRepo.createFullTransaction(
        data.customerId, data.items, data.paidAmount, data.nextPaymentDate
    );
```
**Why it breaks:** The `createFullTransaction(customerId, items, paidAmount, nextPaymentDate, paymentMode)` accepts `paymentMode` as a 5th parameter, but the IPC handler **never passes `data.paymentMode`**. All payments will default to `'Cash'` regardless of what the user selects. Payment mode data is **silently lost**.

---

### 7. No Input Validation on Numeric Fields (Backend)
**Files:** All repositories  
**Why it breaks:** None of the repositories validate that `amount`, `price`, `quantity`, or `stock` are positive numbers. A malicious or buggy frontend call like `createPayment(customerId, -5000)` will **reduce the customer's balance by ₹5,000** (the trigger fires with negative amounts). Similarly, `createPurchaseInvoice` with negative quantities will **deduct stock** instead of adding it.

---

## 🟡 MEDIUM (Causes incorrect behavior, bad UX, or performance issues)

### 8. `customer:get-all` Loads ALL Customers at Once
**File:** `electron/main.js:810-813`  
```js
ipcMain.handle('customer:get-all', async () => {
    return { success: true, data: CustomerRepo.getAll() };
});
```
**Why it's a problem:** With 10,000+ customers, this returns **all records** with no pagination, no search, no limit. The paginated variant exists (`customer:get-paginated`) but `getAll()` is still used in several places.

---

### 9. No Caching for Products and Customers Reads
**File:** `electron/main.js:739-742, 810-813`  
**Why it's a problem:** Supplier reads use `cache.get/set` pattern, but product reads (`product:get-all`) and customer reads bypass the cache entirely. Every page load hits the database directly. For a POS with frequent page switches, this adds unnecessary I/O.

---

### 10. Duplicate Comment Line in `fetchPython`
**File:** `electron/main.js:388-389`  
```js
// Helper for Python Requests
// Helper for Python Requests
```
Minor but indicates copy-paste issues.

---

### 11. `processCollection` Doesn't Recalculate Balance Correctly
**File:** `electron/database/repositories/CustomerRepository.js:73-85`  
```js
if (amount > 0) {
    db.prepare('INSERT INTO payment (customer_id, amount) VALUES (?, ?)').run(customerId, amount);
}
db.prepare('UPDATE customer SET next_payment_date = ? WHERE id = ?').run(nextDate, customerId);
```
**Why it's a problem:** The payment insert triggers `calc_balance_insert_payment` which does `balance = balance - NEW.amount`. This is correct. But there's **no validation** that the payment amount doesn't exceed the customer's current balance (allowing someone to "overpay" and go into negative balance).

---

### 12. Worker `handleSearch` LIMIT is 1000 — Too Large
**File:** `electron/workers/dbWorker.js:35`  
```js
const LIMIT = 1000;
```
**Why it's a problem:** Searching for a common term like "a" could return 1000 products + 1000 customers + 1000 sales + 1000 purchases = **4000 records** passed via `postMessage`. This can block the UI thread on receiving/rendering.

---

### 13. Worker Doesn't Filter Deleted Suppliers in Global Search
**File:** `electron/workers/dbWorker.js:80-102`  
The purchases query joins `LEFT JOIN supplier s ON pi.supplier_id = s.id` but doesn't check `is_deleted`. However, since `softDelete` is actually doing a `DELETE` (Bug #5), this is currently moot — but if soft delete is fixed, search will return deleted supplier data.

---

### 14. `updateVariant` Only Updates Price & Stock — Not Name/Unit
**File:** `electron/database/repositories/ProductRepository.js:83-88`  
```js
updateVariant(id, price, stock) {
    db.prepare('UPDATE product_variant SET price = ?, current_stock = ? WHERE id = ?').run(price, stock, id);
}
```
**Why it's a problem:** If a user wants to rename a variant or change its unit, they **cannot** — they'd have to delete and recreate it, losing all sales history linked to that `variant_id`.

---

### 15. Safety Guard Defaults to CHAT for Errors
**File:** `python_server/ai_engine/safety.py:43-45`  
```python
except Exception as e:
    _logger.error(f"Intent classification failed: {e}")
    return "CHAT"
```
**Why it's a problem:** If the LLM is down/rate-limited, **all queries get classified as CHAT** instead of QUERY, meaning users get generic LLM responses instead of data-backed SQL answers. A safer default would be `"QUERY"` since the router can still handle queries without LLM.

---

### 16. AI Router Pattern `search_product` Catches Too Many Queries
**File:** `python_server/ai_engine/router.py:61`  
```python
(r"(?:search|find|do we have|check|look for|show me)\s+(.+?)(?:\s+product)?$", "search_product"),
```
**Why it's a problem:** "Show me how to increase sales" would match `show me` → extracted term = `"how to increase sales"` → treated as a product search instead of a strategic question. Although `COMPLEX_SIGNALS` catches most cases, edge cases like "show me dead stock analysis" could slip through.

---

### 17. Analytics Cache File Is World-Readable
**File:** `electron/main.js:576`  
```js
const cachePath = path.join(userDataPath, 'analytics_cache.json');
```
**Why it's a problem:** The analytics cache (containing sales data, customer info, revenue) is written as a plain JSON file with default permissions. On multi-user Linux systems, other users could read sensitive business data.

---

### 18. Agent Response Extraction Ignores Multi-Step Tool Outputs
**File:** `python_server/routes/ai_chat.py:56-70`  
```python
first_success = None
for msg in messages:
    if msg.type == "tool":
        if "✅" in content and not first_success:
            first_success = content
```
**Why it's a problem:** The agent returns the **first** tool message containing ✅, ignoring subsequent tool outputs. For multi-tool queries (e.g., business overview + market basket), only the first tool's output is returned. This was less of an issue after adding `get_business_overview_tool`, but individual tool queries that produce ✅ in early tool messages will swallow the final LLM synthesis.

---

### 19. CSV Export Doesn't Escape Commas in field values
**File:** `electron/main.js:450-454`  
```js
stream.write(`${row.date},${row.type},${row.transaction_id},"${safeName}",...`);
```
**Why it's a problem:** While `safeName` is quoted, `row.date`, `row.type`, `row.transaction_id`, and `row.amount` are **not quoted**. If any of these contain commas (unlikely but possible with custom dates), the CSV will be malformed. The `details` field is quoted but address is not consistently handled.

---

### 20. React `key` Warning in AI Chat Messages
**File:** `src/components/AiAssistant.jsx`  
**Why it's a problem:** Messages are keyed by array index (`key={idx}`). If messages are added/removed, React may re-render incorrectly. Should use a unique message ID.

---

## 🟢 LOW (Code quality, future-proofing, minor improvements)

### 21. `asyncio.get_event_loop()` Deprecation Warning
**File:** `python_server/core/startup.py:228`  
```python
asyncio.get_event_loop().run_in_executor(None, run_daily_model_validation)
```
**Why it's a problem:** `asyncio.get_event_loop()` is deprecated in Python 3.12+. Should use `asyncio.get_running_loop()` or `asyncio.ensure_future()`.

---

### 22. `FETCH_LIMIT = 20000` in AddSalePage
**File:** `src/pages/AddSalePage.jsx:25`  
```js
const FETCH_LIMIT = 20000;
```
**Why it's a problem:** Loads up to 20,000 products into memory on the add sale page. For large inventories, this causes **slow initial page load** and high memory usage.

---

### 23. `product_variant.current_stock` Is REAL (Float), Not INTEGER
**File:** `electron/database/db_manager.js:22`  
```sql
current_stock REAL DEFAULT 0
```
**Why it's a problem:** Floating-point stock (`0.5 kg`) makes sense for weight-based items, but can cause precision errors like `stock = 0.0000000001` instead of `0` after operations. All comparisons use `<=` which mitigates this, but it's worth noting.

---

### 24. No Database Backup Mechanism
**Why it's a problem:** The entire business runs on a single SQLite file (`nexus.db`). There's no backup system, no export-on-close, no periodic snapshots. A corrupt database = **total data loss**.

---

### 25. `payment` Table Missing `payment_mode` Column in Schema
**File:** `electron/database/db_manager.js:38-44`  
```sql
CREATE TABLE IF NOT EXISTS payment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    payment_date TEXT DEFAULT (datetime('now', 'localtime')),
    amount REAL NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customer(id) ON DELETE CASCADE
);
```
**Why it's a problem:** `SaleRepository.createFullTransaction` (line 61) inserts `payment_mode` column:
```js
db.prepare('INSERT INTO payment (customer_id, amount, payment_mode) VALUES (?, ?, ?)').run(...)
```
But the schema **doesn't define the `payment_mode` column**. SQLite allows this silently (dynamic typing), but the data is stored in an untyped column. A migration should properly add this column.

---

### 26. `category` Field Has No Validation or Standardization
**Why it's a problem:** Product categories are free-text strings. "Dairy", "dairy", "DAIRY", "dairy " are all different categories. The `get_revenue_comparison_tool` groups by `p.category`, so duplicate-but-different categories fragment the data.

---

### 27. Python `config.json` Settings Read Has Bare `except: pass`
**File:** `python_server/core/startup.py:84`  
```python
except:
    pass
```
**Why it's a problem:** Silently swallows all errors including `PermissionError`, `UnicodeDecodeError`, etc. Should at minimum log the error.

---

### 28. `preload.js` Exposes `on/off` Without Channel Whitelisting
**File:** `electron/preload.js:94-95`  
```js
on: (channel, func) => ipcRenderer.on(channel, (event, ...args) => func(...args)),
off: (channel, func) => ipcRenderer.removeListener(channel, func)
```
**Why it's a problem:** Any renderer-side code can listen on **any** IPC channel, not just whitelisted ones. A compromised renderer could listen to sensitive channels. Should whitelist allowed channels.

---

### 29. `migrationManager.js` Not Audited for SQL Injection
**File:** `electron/database/migrationManager.js`  
**Why it's a problem:** If migration files contain user-controlled content (unlikely but possible), raw SQL execution could be exploited. Migrations should be code-reviewed before deployment.

---

### 30. No Rate Limiting on IPC Handlers
**Why it's a problem:** A compromised or bugged renderer could spam IPC calls (e.g., `sale:create` 1000 times in a loop). No throttling or deduplication exists on any IPC handler.

---

### 31. `react-markdown` Code Block Rendering — `inline` Prop Deprecated
**File:** `src/components/AiAssistant.jsx`  
```jsx
code: ({ inline, children }) => inline ? (...) : (...)
```
**Why it's a problem:** `react-markdown` v9+ removed the `inline` prop from `code` components. The correct way is to check if the parent is `pre`. This may cause all code to render as block-level.

---

### 32. `purchase_item` Table Missing Foreign Key to `product_variant` ON DELETE
**File:** `electron/database/db_manager.js:54`  
```sql
FOREIGN KEY(variant_id) REFERENCES product_variant(id)
-- No ON DELETE clause
```
**Why it's a problem:** Deleting a product variant that has associated purchase items will fail silently or throw an error depending on the foreign_keys pragma. Should be `ON DELETE RESTRICT` to prevent deletion of variants with purchase history.

---

### 33. AI Tools Use `RAW_ENGINE.connect()` Without Pooling Controls
**File:** `python_server/ai_engine/tools.py` (multiple tools)  
```python
with RAW_ENGINE.connect() as c:
```
**Why it's a problem:** Each tool call opens a new connection. If multiple tools run concurrently (unlikely with ReAct but possible), SQLite's single-writer lock could cause `SQLITE_BUSY` errors. The `busy_timeout=5000` pragma mitigates this, but explicit connection pooling would be safer.

---

### 34. `Supplier.getPaginated` Doesn't Filter `is_deleted`
**File:** `electron/database/repositories/SupplierRepository.js:14-32`  
The main `getPaginated` query has no `WHERE is_deleted = 0` filter. Since `softDelete` actually hard-deletes (Bug #5), this is currently benign. But if soft-delete is properly implemented, deleted suppliers will appear in the list.

---

### 35. Missing Error Boundaries on Individual Route Components
**File:** `src/App.jsx`  
**Why it's a problem:** There's an `ErrorBoundary` component imported, but if it only wraps the top-level app, a crash on one page (e.g., DashboardPage) will blank the entire app. Individual route-level error boundaries would keep navigation working.

---

## 📊 Summary

| Category | Count | Examples |
|----------|-------|---------|
| 🔴 Critical | 7 | Hardcoded key, balance corruption, negative stock, soft-delete broken |
| 🟡 Medium | 13 | No caching, over-fetching, wrong default intent, CSV escaping |
| 🟢 Low | 15 | Deprecated APIs, missing backups, no rate limiting, code quality |
| **Total** | **35** | |

---

## 🎯 Recommended Fix Order

1. **🔴 #1** — Replace hardcoded encryption key with `electron-safeStorage`
2. **🔴 #4** — Add stock guard to `deletePurchase()` (prevent negative stock)
3. **🔴 #5** — Fix `softDelete` to actually set `is_deleted = 1` instead of DELETE
4. **🔴 #6** — Pass `paymentMode` in `sale:create-full` IPC handler
5. **🔴 #7** — Add input validation for amounts/quantities in all repos
6. **🟡 #25** — Add `payment_mode` column via migration
7. **🟡 #14** — Allow variant name/unit editing
8. **🟢 #24** — Add periodic SQLite backup (copy `nexus.db` to timestamped backup)
