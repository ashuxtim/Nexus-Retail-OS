# FILE: python_server/ai_engine/tools.py

import re
from sqlalchemy import text
from langchain_core.tools import tool

# --- GLOBAL CONTEXT (Injected from main.py) ---
RAW_ENGINE = None
SEARCH_ENGINE = None
ANALYTICS_CACHE = {}


def set_context(engine, search_engine_ref, analytics_cache_ref):
    """
    Injects dependencies so tools can access DB, Vector Store, and Cache.
    Call this from main.py during startup.
    """
    global RAW_ENGINE, SEARCH_ENGINE, ANALYTICS_CACHE
    RAW_ENGINE = engine
    SEARCH_ENGINE = search_engine_ref
    ANALYTICS_CACHE = analytics_cache_ref
    print("✅ AI Tools Context Loaded.")


# --- HELPER FUNCTIONS ---


def clean_number(val):
    if isinstance(val, (int, float)):
        return float(val)
    clean = re.sub(r"[^0-9.]", "", str(val))
    try:
        return float(clean)
    except:
        return 0.0


def get_safe_match(conn, table, name_col, search_name):
    """
    Smart matching logic to prevent accidental deletions.
    1. Try EXACT match (case insensitive).
    2. If not found, try LIKE match.
    3. If multiple found, ERROR out.
    4. SIBLING CHECK: Even after finding a unique match, check if other records
       share the same name prefix — prevents the LLM from resolving ambiguity silently.
    """
    # 1. Exact Match
    exact = conn.execute(
        text(
            f"SELECT id, {name_col} FROM {table} WHERE LOWER({name_col}) = LOWER(:name)"
        ),
        {"name": search_name},
    ).fetchall()

    if len(exact) == 1:
        matched_id, matched_name = exact[0]
        # Sibling check: are there others with a similar prefix?
        siblings = _find_siblings(conn, table, name_col, matched_name, matched_id)
        if siblings:
            all_names = [matched_name] + [s[1] for s in siblings]
            numbered = '\n'.join([f'  {i+1}. {n}' for i, n in enumerate(all_names)])
            raise ValueError(
                f"AMBIGUOUS — {len(all_names)} matching records found:\n{numbered}\nAsk the user which one they mean."
            )
        return matched_id

    if len(exact) > 1:
        names = ", ".join([r[1] for r in exact])
        raise ValueError(f"Ambiguous exact match. Found multiple: {names}")

    # 2. Fuzzy/Like Match — word-boundary prefix ("raj" matches "Raj Kumar" but NOT "Rajesh")
    fuzzy = conn.execute(
        text(
            f"SELECT id, {name_col} FROM {table} "
            f"WHERE LOWER({name_col}) LIKE LOWER(:prefix) "
            f"OR LOWER({name_col}) LIKE LOWER(:word_prefix)"
        ),
        {"prefix": f"{search_name}%", "word_prefix": f"% {search_name}%"},
    ).fetchall()

    if len(fuzzy) == 0:
        raise ValueError(f"No {table} found matching '{search_name}'")

    if len(fuzzy) > 1:
        numbered = '\n'.join([f'  {i+1}. {n}' for i, (_, n) in enumerate(fuzzy[:10])])
        raise ValueError(
            f"AMBIGUOUS — {len(fuzzy)} matching records found:\n{numbered}\nAsk the user which one they mean."
        )

    # Single fuzzy match — still do sibling check
    matched_id, matched_name = fuzzy[0]
    siblings = _find_siblings(conn, table, name_col, matched_name, matched_id)
    if siblings:
        all_names = [matched_name] + [s[1] for s in siblings]
        numbered = '\n'.join([f'  {i+1}. {n}' for i, n in enumerate(all_names)])
        raise ValueError(
            f"AMBIGUOUS — {len(all_names)} matching records found:\n{numbered}\nAsk the user which one they mean."
        )
    return matched_id


def _find_siblings(conn, table, name_col, matched_name, matched_id):
    """
    Check if other records share a common name prefix with the matched record.
    E.g., 'Rahul Kumar Oraon' and 'Rahul Kumar Kol' share 'Rahul Kumar'.
    """
    words = matched_name.strip().split()
    if len(words) < 2:
        return []

    # Build prefix from first N-1 words (e.g., "Rahul Kumar" from "Rahul Kumar Oraon")
    prefix = " ".join(words[:-1])
    if len(prefix) < 3:
        return []

    siblings = conn.execute(
        text(
            f"SELECT id, {name_col} FROM {table} "
            f"WHERE (LOWER({name_col}) LIKE LOWER(:prefix) OR LOWER({name_col}) LIKE LOWER(:word_prefix)) "
            f"AND id != :id"
        ),
        {"prefix": f"{prefix}%", "word_prefix": f"% {prefix}%", "id": matched_id},
    ).fetchall()
    return siblings



# --- SEARCH & ANALYTICS TOOLS ---


@tool
def search_catalog_tool(search_term: str, category: str = "product"):
    """
    SEARCH ENGINE. Use this FIRST when user asks 'Do we have X?' or 'Find X'.
    category: 'product' or 'customer'.
    """
    if not SEARCH_ENGINE:
        return "Search Engine is still loading..."
    return SEARCH_ENGINE.search(category, search_term, limit=10)


@tool
def search_supplier_tool(search_term: str):
    """
    Searches for suppliers by name. Use this before recording purchases.
    """
    try:
        if not RAW_ENGINE:
            return "Database not connected."
        with RAW_ENGINE.connect() as c:
            res = c.execute(
                text(
                    "SELECT name, mobile FROM supplier WHERE LOWER(name) LIKE LOWER(:name) LIMIT 5"
                ),
                {"name": f"%{search_term}%"},
            ).fetchall()
            if not res:
                return "No suppliers found."
            return "\n".join([f"- {r[0]} (Mobile: {r[1]})" for r in res])
    except Exception as e:
        return f"Error: {e}"


@tool
def check_churn_risk_tool():
    """Identifies customers at risk of leaving using cached ML predictions."""
    if not ANALYTICS_CACHE or not ANALYTICS_CACHE.get("churn_risk"):
        return "✨ No immediate churn risks detected or analytics pending."

    risks = ANALYTICS_CACHE.get("churn_risk", [])
    if not risks:
        return "✨ No immediate churn risks detected."

    sorted_risks = sorted(risks, key=lambda x: x["risk_score"], reverse=True)
    report = f"🤖 **AI Churn Report (Total At-Risk: {len(sorted_risks)}):**\n\n"
    for r in sorted_risks[:15]:
        report += f"🔴 **{r.get('name', 'Unknown')}** (Risk: {r['risk_score']}%)\n"
        report += f"   Reason: {r['trend']} • Inactive: {r['days_inactive']} days\n\n"
    return report


@tool
def get_market_insights_tool():
    """Returns 'Market Basket' patterns (e.g. Bread goes with Milk)."""
    if not ANALYTICS_CACHE:
        return "Analytics not initialized."
    return f"🛒 **Shopping Patterns:**\n{ANALYTICS_CACHE.get('market_basket', 'Analysis pending...')}"


# --- CUSTOMER CRUD TOOLS ---


@tool
def add_customer_tool(name: str, mobile: str, address: str = ""):
    """Adds a new customer. Checks for name and mobile duplicates first."""
    try:
        with RAW_ENGINE.connect() as c:
            # Check name duplicates (UNIQUE constraint on name)
            name_exists = c.execute(
                text("SELECT id, name FROM customer WHERE LOWER(name) = LOWER(:name)"),
                {"name": name},
            ).fetchone()
            if name_exists:
                return f"❌ Customer '{name_exists[1]}' already exists."

            # Check mobile duplicates
            if mobile:
                mob_exists = c.execute(
                    text("SELECT id, name FROM customer WHERE mobile = :mob"),
                    {"mob": mobile},
                ).fetchone()
                if mob_exists:
                    return f"❌ Mobile {mobile} is already assigned to '{mob_exists[1]}'."

            c.execute(
                text(
                    "INSERT INTO customer (name, mobile, address) VALUES (:name, :mobile, :address)"
                ),
                {"name": name, "mobile": mobile, "address": address},
            )
            c.commit()
        return f"✅ Added customer: {name}"
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def delete_customer_tool(name: str):
    """Deletes a customer by name. If the result contains 'AMBIGUOUS', you MUST show the full message to the user as-is (do NOT paraphrase it)."""
    try:
        with RAW_ENGINE.connect() as c:
            try:
                cid = get_safe_match(c, "customer", "name", name)
            except ValueError as ve:
                return f"❌ {str(ve)}"

            c.execute(text("DELETE FROM customer WHERE id = :id"), {"id": cid})
            c.commit()
        return f"✅ Deleted customer."
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def update_customer_details_tool(
    current_name: str, new_mobile: str = None, new_address: str = None
):
    """Updates customer details. If result contains 'AMBIGUOUS', show the full message to user as-is."""
    try:
        with RAW_ENGINE.connect() as c:
            try:
                cid = get_safe_match(c, "customer", "name", current_name)
            except ValueError as ve:
                return f"❌ {str(ve)}"

            clauses = []
            params = {"id": cid}
            if new_mobile:
                clauses.append("mobile = :mobile")
                params["mobile"] = new_mobile
            if new_address:
                clauses.append("address = :address")
                params["address"] = new_address
            if not clauses:
                return "❌ No changes requested."

            c.execute(
                text(f"UPDATE customer SET {', '.join(clauses)} WHERE id = :id"), params
            )
            c.commit()
        return f"✅ Updated {current_name}."
    except Exception as e:
        return f"❌ Error: {str(e)}"


# --- PRODUCT CRUD TOOLS ---


@tool
def add_product_tool(
    product_name: str,
    variant_name: str,
    category: str,
    price: str,
    initial_stock: str = "0",
):
    """Adds a new product/variant. Checks for duplicate variants."""
    try:
        price_val = clean_number(price)
        stock_val = clean_number(initial_stock)
        with RAW_ENGINE.connect() as c:
            pid_res = c.execute(
                text("SELECT id FROM product WHERE LOWER(name) = LOWER(:name)"),
                {"name": product_name},
            ).fetchone()
            if pid_res:
                prod_id = pid_res[0]
                # Check if variant already exists under this product
                var_exists = c.execute(
                    text(
                        "SELECT id FROM product_variant WHERE product_id = :pid AND LOWER(name) = LOWER(:vname)"
                    ),
                    {"pid": prod_id, "vname": variant_name},
                ).fetchone()
                if var_exists:
                    return f"❌ Variant '{variant_name}' already exists under '{product_name}'."
            else:
                prod_id = c.execute(
                    text("INSERT INTO product (name, category) VALUES (:name, :cat)"),
                    {"name": product_name, "cat": category},
                ).lastrowid

            c.execute(
                text(
                    "INSERT INTO product_variant (product_id, name, price, unit, current_stock) VALUES (:pid, :vname, :price, 'Unit', :stock)"
                ),
                {
                    "pid": prod_id,
                    "vname": variant_name,
                    "price": price_val,
                    "stock": stock_val,
                },
            )
            c.commit()
        return f"✅ Added {product_name} - {variant_name}."
    except Exception as e:
        return f"❌ Error: {str(e)}"


def get_safe_product_match(conn, product_name, variant_name=None):
    """
    Smart matching for products + variants with AMBIGUOUS disambiguation.
    Returns (variant_id, product_display_name) or raises ValueError.
    """
    if variant_name:
        res = conn.execute(
            text(
                "SELECT pv.id, p.name || ' - ' || pv.name FROM product_variant pv "
                "JOIN product p ON pv.product_id = p.id "
                "WHERE (LOWER(p.name) LIKE LOWER(:pname) OR LOWER(p.name) LIKE LOWER(:pname_word)) "
                "AND (LOWER(pv.name) LIKE LOWER(:vname) OR LOWER(pv.name) LIKE LOWER(:vname_word))"
            ),
            {"pname": f"{product_name}%", "pname_word": f"% {product_name}%",
             "vname": f"{variant_name}%", "vname_word": f"% {variant_name}%"},
        ).fetchall()
    else:
        res = conn.execute(
            text(
                "SELECT pv.id, p.name || ' - ' || pv.name FROM product_variant pv "
                "JOIN product p ON pv.product_id = p.id "
                "WHERE LOWER(p.name) LIKE LOWER(:pname) OR LOWER(p.name) LIKE LOWER(:pname_word)"
            ),
            {"pname": f"{product_name}%", "pname_word": f"% {product_name}%"},
        ).fetchall()

    if not res:
        raise ValueError(f"No product found matching '{product_name}'.")

    if len(res) > 1:
        numbered = '\n'.join([f'  {i+1}. {r[1]}' for i, r in enumerate(res[:10])])
        raise ValueError(
            f"AMBIGUOUS — {len(res)} matching products found:\n{numbered}\nAsk the user which one they mean."
        )

    return res[0][0], res[0][1]


@tool
def update_product_tool(
    product_name: str, variant_name: str, new_price: str = None, new_stock: str = None
):
    """Updates price or stock. If result contains 'AMBIGUOUS', show the full message to user as-is."""
    try:
        with RAW_ENGINE.connect() as c:
            try:
                vid, display = get_safe_product_match(c, product_name, variant_name)
            except ValueError as ve:
                return f"❌ {str(ve)}"

            clauses = []
            params = {"id": vid}
            if new_price is not None:
                clauses.append("price = :price")
                params["price"] = clean_number(new_price)
            if new_stock is not None:
                clauses.append("current_stock = :stock")
                params["stock"] = clean_number(new_stock)
            if not clauses:
                return "❌ No changes requested."
            c.execute(
                text(f"UPDATE product_variant SET {', '.join(clauses)} WHERE id = :id"),
                params,
            )
            c.commit()
        return f"✅ Updated {display}."
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def delete_product_tool(product_name: str, variant_name: str):
    """Deletes a product variant. If result contains 'AMBIGUOUS', show the full message to user as-is."""
    try:
        with RAW_ENGINE.connect() as c:
            try:
                vid, display = get_safe_product_match(c, product_name, variant_name)
            except ValueError as ve:
                return f"❌ {str(ve)}"

            c.execute(
                text("DELETE FROM product_variant WHERE id = :id"), {"id": vid}
            )
            c.commit()
        return f"✅ Deleted {display}."
    except Exception as e:
        return f"❌ Error: {str(e)}"


# --- TRANSACTION TOOLS ---


@tool
def record_sale_tool(customer_name: str, product_name: str, quantity: str):
    """Records a sale transaction."""
    try:
        qty_val = clean_number(quantity)
        with RAW_ENGINE.connect() as c:
            # 1. Safe Customer Match
            try:
                cid = get_safe_match(c, "customer", "name", customer_name)
            except ValueError as ve:
                return f"❌ Customer Error: {str(ve)}"

            # 2. Product Match (with ambiguity check)
            try:
                vid, display = get_safe_product_match(c, product_name)
            except ValueError as ve:
                return f"❌ Product Error: {str(ve)}"

            row = c.execute(
                text("SELECT price, current_stock FROM product_variant WHERE id = :id"),
                {"id": vid},
            ).fetchone()
            price, stock = row[0], row[1]
            if stock < qty_val:
                return f"❌ Insufficient stock for {display} ({stock})."

            sid = c.execute(
                text(
                    "INSERT INTO credit_sale (customer_id, sale_date) VALUES (:cid, date('now'))"
                ),
                {"cid": cid},
            ).lastrowid
            c.execute(
                text(
                    "INSERT INTO credit_sale_item (sale_id, variant_id, quantity, price_at_sale) VALUES (:sid, :vid, :qty, :price)"
                ),
                {"sid": sid, "vid": vid, "qty": qty_val, "price": price},
            )
            c.execute(
                text(
                    "UPDATE product_variant SET current_stock = current_stock - :qty WHERE id = :vid"
                ),
                {"qty": qty_val, "vid": vid},
            )
            c.commit()
        return f"✅ Sale recorded."
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def delete_last_sale_tool(customer_name: str):
    """Deletes the most recent sale for a customer."""
    try:
        with RAW_ENGINE.connect() as c:
            try:
                cid = get_safe_match(c, "customer", "name", customer_name)
            except ValueError as ve:
                return f"❌ Customer Error: {str(ve)}"

            sale_res = c.execute(
                text(
                    "SELECT id FROM credit_sale WHERE customer_id = :cid ORDER BY sale_date DESC LIMIT 1"
                ),
                {"cid": cid},
            ).fetchone()
            if not sale_res:
                return "❌ No recent sales."
            sid = sale_res[0]

            items = c.execute(
                text(
                    "SELECT variant_id, quantity FROM credit_sale_item WHERE sale_id = :sid"
                ),
                {"sid": sid},
            ).fetchall()
            for vid, qty in items:
                c.execute(
                    text(
                        "UPDATE product_variant SET current_stock = current_stock + :qty WHERE id = :vid"
                    ),
                    {"qty": qty, "vid": vid},
                )
            c.execute(text("DELETE FROM credit_sale WHERE id = :sid"), {"sid": sid})
            c.commit()
        return "✅ Deleted last sale."
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def record_purchase_tool(
    supplier_name: str, product_name: str, quantity: str, cost_price: str
):
    """Records a purchase from a supplier."""
    try:
        qty_val = clean_number(quantity)
        price_val = clean_number(cost_price)
        with RAW_ENGINE.connect() as c:
            # 1. Safe Supplier Match
            try:
                sid = get_safe_match(c, "supplier", "name", supplier_name)
            except ValueError as ve:
                return f"❌ Supplier Error: {str(ve)}"

            try:
                vid, _ = get_safe_product_match(c, product_name)
            except ValueError as ve:
                return f"❌ Product Error: {str(ve)}"

            c.execute(
                text(
                    "INSERT INTO purchase (supplier_id, variant_id, quantity, purchase_price, purchase_date) VALUES (:sid, :vid, :qty, :price, date('now'))"
                ),
                {"sid": sid, "vid": vid, "qty": qty_val, "price": price_val},
            )
            c.execute(
                text(
                    "UPDATE product_variant SET current_stock = current_stock + :qty WHERE id = :vid"
                ),
                {"qty": qty_val, "vid": vid},
            )
            c.commit()
        return "✅ Purchase recorded."
    except Exception as e:
        return f"❌ Error: {str(e)}"


@tool
def delete_last_purchase_tool(supplier_name: str):
    """Deletes the most recent purchase from a supplier."""
    try:
        with RAW_ENGINE.connect() as c:
            try:
                sid = get_safe_match(c, "supplier", "name", supplier_name)
            except ValueError as ve:
                return f"❌ Supplier Error: {str(ve)}"

            res = c.execute(
                text(
                    "SELECT id, variant_id, quantity FROM purchase WHERE supplier_id = :sid ORDER BY purchase_date DESC LIMIT 1"
                ),
                {"sid": sid},
            ).fetchone()
            if not res:
                return "❌ No recent purchases."
            pid, vid, qty = res

            c.execute(
                text(
                    "UPDATE product_variant SET current_stock = current_stock - :qty WHERE id = :vid"
                ),
                {"qty": qty, "vid": vid},
            )
            c.execute(text("DELETE FROM purchase WHERE id = :id"), {"id": pid})
            c.commit()
        return "✅ Purchase deleted."
    except Exception as e:
        return f"❌ Error: {str(e)}"
