const { parentPort, workerData } = require('worker_threads');
const Database = require('better-sqlite3');

const db = new Database(workerData.dbPath);
db.pragma('journal_mode = WAL');

// INVARIANT: Worker must remain stateless or explicitly clear state on RESET_CACHE
let internalCache = {};

parentPort.on('message', (task) => {
  try {
    if (task.type === 'SEARCH_GLOBAL') {
      handleSearch(task.payload, task.id);
    } else if (task.type === 'EXPORT_LEDGER') {
      handleExport(task.payload, task.id);
    } else if (task.type === 'SEARCH_SUPPLIERS') {
      handleSupplierSearch(task.payload, task.id);
    } else if (task.type === 'SEARCH_VARIANTS') {
      handleVariantSearch(task.payload, task.id);
    } else if (task.type === 'GET_DAYBOOK') {
      handleDaybook(task.payload, task.id);
    } else if (task.type === 'GET_DASHBOARD_STATS') {
      handleDashboardStats(task.id);
    } else if (task.type === 'GET_PRODUCTS') {
      handleGetProducts(task.payload, task.id);
    } else if (task.type === 'RESET_CACHE') {
      internalCache = {};
    }
  } catch (err) {
    if (task.type !== 'RESET_CACHE') {
      parentPort.postMessage({ id: task.id, error: err.message });
    } else {
      console.error("Worker Reset Error:", err);
    }
  }
});

function handleSearch(term, reqId) {
  const search = `%${term}%`;
  const prefix = `${term}%`;
  const exact = term;
  const LIMIT = 50;

  // OPTIMIZATION: Check if input is a valid number.
  // If 'term' is "apple", isNumeric is false, and numericVal is -1 (so it matches nothing safely).
  const isNumeric = !isNaN(parseFloat(term)) && isFinite(term);
  const numericVal = isNumeric ? term : -1;

  // 1. PRODUCTS
  // Removed CAST(v.price AS TEXT). Now uses direct numeric comparison if applicable.
  const products = db.prepare(`
    SELECT p.id as product_id, p.name as product_name, v.name as variant_name, v.price, v.current_stock, v.unit 
    FROM product_variant v 
    JOIN product p ON v.product_id = p.id 
    WHERE 
      p.name LIKE ? 
      OR v.name LIKE ? 
      OR (v.price = ? AND ? = 1)  -- Only check price if isNumeric is true (1)
      OR (p.id = ? AND ? = 1)     -- Only check ID if isNumeric is true (1)
    LIMIT ?
  `).all(prefix, prefix, numericVal, isNumeric ? 1 : 0, numericVal, isNumeric ? 1 : 0, LIMIT);

  // 2. CUSTOMERS
  const customers = db.prepare(`
    SELECT * FROM customer 
    WHERE name LIKE ? OR mobile LIKE ? OR address LIKE ? 
      OR (id = ? AND ? = 1)  -- ✅ Add this line
    LIMIT ?
  `).all(prefix, prefix, prefix, numericVal, isNumeric ? 1 : 0, LIMIT);


  // 3. SALES
  const sales = db.prepare(`
    SELECT s.id, s.sale_date, c.name as customer_name, SUM(i.quantity * i.price_at_sale) as total_amount, 
    GROUP_CONCAT(p.name || ' ' || v.name, ', ') as items_summary 
    FROM credit_sale s 
    JOIN customer c ON s.customer_id = c.id 
    JOIN credit_sale_item i ON s.id = i.sale_id 
    JOIN product_variant v ON i.variant_id = v.id 
    JOIN product p ON v.product_id = p.id 
    WHERE c.name LIKE ? OR s.sale_date LIKE ? OR (s.id = ? AND ? = 1)
    GROUP BY s.id 
    ORDER BY s.sale_date DESC LIMIT ?
  `).all(prefix, search, numericVal, isNumeric ? 1 : 0, LIMIT);

  // 4. PURCHASES
  const purchases = db.prepare(`
    SELECT
      pi.id as invoice_id,
      pi.invoice_date as purchase_date,
      s.name as supplier_name,
      p.name as product_name,
      v.name as variant_name,
      item.quantity,
      item.unit_cost as purchase_price
    FROM purchase_item item
    JOIN purchase_invoice pi ON item.invoice_id = pi.id
    LEFT JOIN supplier s ON pi.supplier_id = s.id AND s.is_deleted = 0
    JOIN product_variant v ON item.variant_id = v.id
    JOIN product p ON v.product_id = p.id
    WHERE
      s.name LIKE ? OR
      p.name LIKE ? OR
      v.name LIKE ? OR
      pi.invoice_date LIKE ? OR
      (pi.id = ? AND ? = 1)
    ORDER BY pi.invoice_date DESC
    LIMIT ?
  `).all(prefix, prefix, prefix, search, numericVal, isNumeric ? 1 : 0, LIMIT);

  parentPort.postMessage({ id: reqId, result: { products, customers, sales, purchases } });
}

function handleExport({ start, end }, reqId) {
  const startDate = start || '2000-01-01';
  const endDate = end || '2099-12-31';
  const sql = `SELECT 'Sale' as type, s.sale_date as date, s.id as transaction_id, c.name as customer_name, c.mobile as customer_mobile, c.address as customer_address, GROUP_CONCAT(p.name || ' (' || i.quantity || ')', '; ') as details, SUM(i.quantity * i.price_at_sale) as amount FROM credit_sale s JOIN customer c ON s.customer_id = c.id JOIN credit_sale_item i ON s.id = i.sale_id JOIN product_variant v ON i.variant_id = v.id JOIN product p ON v.product_id = p.id WHERE date(s.sale_date) BETWEEN ? AND ? GROUP BY s.id UNION ALL SELECT 'Payment' as type, pay.payment_date as date, pay.id as transaction_id, c.name as customer_name, c.mobile as customer_mobile, c.address as customer_address, 'Cash/Online Payment' as details, pay.amount as amount FROM payment pay JOIN customer c ON pay.customer_id = c.id WHERE date(pay.payment_date) BETWEEN ? AND ? ORDER BY date DESC`;
  const rows = db.prepare(sql).all(startDate, endDate, startDate, endDate);
  parentPort.postMessage({ id: reqId, result: rows });
}

function handleSupplierSearch({ search = "", limit = 20 }, reqId) {
  try {
    const term = `%${search}%`;
    const prefix = `${search}%`;
    const wordStart = `% ${search}%`;

    const results = db.prepare(`
      SELECT id, name, mobile, address,
      CASE
        WHEN name LIKE ? THEN 1         
        WHEN name LIKE ? THEN 2         
        ELSE 3                          
      END as match_priority
      FROM supplier
      WHERE is_deleted = 0 AND (name LIKE ? OR mobile LIKE ?)
      ORDER BY match_priority ASC, name ASC
      LIMIT ?
    `).all(prefix, wordStart, term, term, limit);

    parentPort.postMessage({ id: reqId, result: results });
  } catch (err) {
    console.error('Supplier search error:', err);
    parentPort.postMessage({ id: reqId, error: err.message });
  }
}

function handleVariantSearch({ query = "", limit = 50 }, reqId) {
  const search = `%${query}%`;

  // Same optimization here
  const isNumeric = !isNaN(parseFloat(query)) && isFinite(query);
  const numericVal = isNumeric ? query : -1;

  const results = db.prepare(`
    SELECT
      v.id,
      v.name as variant_name,
      v.price,
      v.current_stock,
      v.unit,
      p.id as product_id,
      p.name as product_name,
      p.category
    FROM product_variant v
    JOIN product p ON v.product_id = p.id
    WHERE
      p.name LIKE ? OR
      v.name LIKE ? OR
      (v.price = ? AND ? = 1) OR
      (p.id = ? AND ? = 1) OR
      (v.id = ? AND ? = 1)
    ORDER BY 
      CASE WHEN p.name LIKE ? THEN 0 ELSE 1 END,
      p.name ASC, 
      v.name ASC
    LIMIT ?
  `).all(search, search, numericVal, isNumeric ? 1 : 0, numericVal, isNumeric ? 1 : 0, numericVal, isNumeric ? 1 : 0, `${query}%`, limit);

  parentPort.postMessage({ id: reqId, result: results });
}

function handleDaybook({ dateStr }, reqId) {
  const selectedDate = dateStr || new Date().toISOString().split('T')[0];
  const startOfDay = `${selectedDate} 00:00:00`;
  const endOfDay = `${selectedDate} 23:59:59`;

  const cashIn = db.prepare(
    `SELECT SUM(amount) as total FROM payment WHERE payment_date BETWEEN ? AND ?`
  ).get(startOfDay, endOfDay).total || 0;

  const cashOut = db.prepare(
    `SELECT SUM(total_amount) as total FROM purchase_invoice WHERE invoice_date BETWEEN ? AND ?`
  ).get(startOfDay, endOfDay).total || 0;

  const totalSales = db.prepare(
    `SELECT SUM(i.quantity * i.price_at_sale) as total
     FROM credit_sale_item i
     JOIN credit_sale s ON i.sale_id = s.id
     WHERE s.sale_date BETWEEN ? AND ?`
  ).get(startOfDay, endOfDay).total || 0;

  const items = db.prepare(
    `SELECT (p.name || ' ' || v.name) as name,
            SUM(i.quantity) as qty,
            SUM(i.quantity * i.price_at_sale) as total
     FROM credit_sale_item i
     JOIN credit_sale s ON i.sale_id = s.id
     JOIN product_variant v ON i.variant_id = v.id
     JOIN product p ON v.product_id = p.id
     WHERE s.sale_date BETWEEN ? AND ?
     GROUP BY v.id ORDER BY total DESC`
  ).all(startOfDay, endOfDay);

  parentPort.postMessage({
    id: reqId,
    result: { date: selectedDate, cashIn, cashOut, totalSales, netCash: cashIn - cashOut, items }
  });
}

function handleDashboardStats(reqId) {
  const custStats = db.prepare(
    `SELECT SUM(balance) as total_credit FROM customer WHERE balance > 0`
  ).get();

  const topDebtors = db.prepare(`
    SELECT name, mobile, balance as outstanding_balance
    FROM customer
    WHERE balance > 0
    ORDER BY balance DESC
    LIMIT 50
  `).all();

  const prodCount = db.prepare(
    `SELECT COUNT(*) as c FROM product_variant`
  ).get().c;

  const custCount = db.prepare(
    `SELECT COUNT(*) as c FROM customer`
  ).get().c;

  const lowStock = db.prepare(`
    SELECT p.name as product_name, v.name as variant_name,
           v.current_stock as total_stock, p.category
    FROM product_variant v
    JOIN product p ON v.product_id = p.id
    WHERE v.current_stock <= 10
    ORDER BY v.current_stock ASC
    LIMIT 50
  `).all();

  parentPort.postMessage({
    id: reqId,
    result: {
      totaloutstandingcredit: custStats?.total_credit || 0,
      totalproductvariants: prodCount || 0,
      totalcustomers: custCount || 0,
      low_stock_items: lowStock,
      top_customers_by_credit: topDebtors
    }
  });
}

function handleGetProducts({ page = 1, limit = 100, search = "" }, reqId) {
  const offset = (page - 1) * limit;
  const searchTerm = `%${search}%`;
  const startTerm = `${search}%`;

  const products = db.prepare(`
    SELECT DISTINCT p.* FROM product p
    LEFT JOIN product_variant v ON p.id = v.product_id
    WHERE p.name LIKE ? OR v.name LIKE ? OR p.category LIKE ?
    ORDER BY
      CASE WHEN p.name LIKE ? THEN 0 ELSE 1 END,
      p.name ASC
    LIMIT ? OFFSET ?
  `).all(searchTerm, searchTerm, searchTerm, startTerm, limit, offset);

  if (products.length === 0) {
    return parentPort.postMessage({ id: reqId, result: [] });
  }

  const productIds = products.map(p => p.id);
  const placeholders = productIds.map(() => '?').join(',');
  const variants = db.prepare(
    `SELECT * FROM product_variant WHERE product_id IN (${placeholders})`
  ).all(...productIds);

  const result = products.map(p => ({
    ...p,
    variants: variants.filter(v => v.product_id === p.id)
  }));

  parentPort.postMessage({ id: reqId, result });
}