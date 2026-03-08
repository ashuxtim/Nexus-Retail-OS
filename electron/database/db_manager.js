const Database = require('better-sqlite3');
const path = require('path');
const { app } = require('electron');

const dbPath = path.join(app.getPath('userData'), 'nexus.db');
let db;

function getDB() {
  if (!db) {
    db = new Database(dbPath);
    db.pragma('journal_mode = WAL');
    db.pragma('foreign_keys = ON');
  }
  return db;
}

function initSchema() {
  const db = getDB();
  
  // --- TABLES ---
  db.exec(`CREATE TABLE IF NOT EXISTS product (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, category TEXT);`);
  db.exec(`CREATE TABLE IF NOT EXISTS product_variant (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER NOT NULL, name TEXT NOT NULL, price REAL NOT NULL, unit TEXT, current_stock REAL DEFAULT 0, FOREIGN KEY(product_id) REFERENCES product(id) ON DELETE CASCADE);`);
  db.exec(`CREATE TABLE IF NOT EXISTS customer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    mobile TEXT,
    address TEXT,
    balance REAL DEFAULT 0,
    next_payment_date TEXT
  );`);
  db.exec(`CREATE TABLE IF NOT EXISTS credit_sale (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    sale_date TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY(customer_id) REFERENCES customer(id) ON DELETE CASCADE
  );`);
  db.exec(`CREATE TABLE IF NOT EXISTS credit_sale_item (id INTEGER PRIMARY KEY AUTOINCREMENT, sale_id INTEGER NOT NULL, variant_id INTEGER NOT NULL, quantity REAL NOT NULL, price_at_sale REAL NOT NULL, FOREIGN KEY(sale_id) REFERENCES credit_sale(id) ON DELETE CASCADE, FOREIGN KEY(variant_id) REFERENCES product_variant(id) ON DELETE RESTRICT);`);
  db.exec(`CREATE TABLE IF NOT EXISTS payment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    payment_date TEXT DEFAULT (datetime('now', 'localtime')),
    amount REAL NOT NULL,
    FOREIGN KEY(customer_id) REFERENCES customer(id) ON DELETE CASCADE
  );`);
  db.exec(`CREATE TABLE IF NOT EXISTS supplier (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL, mobile TEXT, address TEXT, is_deleted INTEGER DEFAULT 0);`);
  db.exec(`CREATE TABLE IF NOT EXISTS purchase_invoice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER,
    invoice_date TEXT DEFAULT (datetime('now', 'localtime')),
    total_amount REAL NOT NULL,
    reference_number TEXT,
    FOREIGN KEY(supplier_id) REFERENCES supplier(id) ON DELETE SET NULL
  );`);
  db.exec(`CREATE TABLE IF NOT EXISTS purchase_item (id INTEGER PRIMARY KEY AUTOINCREMENT, invoice_id INTEGER NOT NULL, variant_id INTEGER NOT NULL, quantity REAL NOT NULL, unit_cost REAL NOT NULL, FOREIGN KEY(invoice_id) REFERENCES purchase_invoice(id) ON DELETE CASCADE);`);
  db.exec(`CREATE TABLE IF NOT EXISTS app_settings (
    setting_key TEXT PRIMARY KEY,
    setting_value TEXT
  );`);

  // --- OPTIMIZED INDEXES ---
  const indexes = [
    // --- SALES & LEDGER INDEXES ---
    'CREATE INDEX IF NOT EXISTS idx_credit_sale_customer_date ON credit_sale(customer_id, sale_date DESC);',
    'CREATE INDEX IF NOT EXISTS idx_sale_date ON credit_sale(sale_date);',
    'CREATE INDEX IF NOT EXISTS idx_item_sale ON credit_sale_item(sale_id);',
    'CREATE INDEX IF NOT EXISTS idx_sale_item_variant ON credit_sale_item(variant_id);',
    
    // --- PAYMENT INDEXES ---
    'CREATE INDEX IF NOT EXISTS idx_payment_customer_date ON payment(customer_id, payment_date DESC);',
    
    // --- CUSTOMER INDEXES ---
    'CREATE INDEX IF NOT EXISTS idx_customer_balance ON customer(balance);',
    'CREATE INDEX IF NOT EXISTS idx_customer_payment_date ON customer(next_payment_date);',
    'CREATE INDEX IF NOT EXISTS idx_customer_name ON customer(name);',
    'CREATE INDEX IF NOT EXISTS idx_customer_mobile ON customer(mobile);',
    
    // --- PURCHASE INDEXES (Critical for PurchasesPage) ---
    'CREATE INDEX IF NOT EXISTS idx_purchase_invoice_date_desc ON purchase_invoice(invoice_date DESC, supplier_id);',
    'CREATE INDEX IF NOT EXISTS idx_purchase_invoice_supplier_date ON purchase_invoice(supplier_id, invoice_date DESC);',
    'CREATE INDEX IF NOT EXISTS idx_purchase_item_invoice ON purchase_item(invoice_id);',
    'CREATE INDEX IF NOT EXISTS idx_purchase_item_variant ON purchase_item(variant_id);',
    
    // --- SUPPLIER INDEXES ---
    'CREATE INDEX IF NOT EXISTS idx_supplier_name ON supplier(name);',
    'CREATE INDEX IF NOT EXISTS idx_supplier_mobile ON supplier(mobile);',
    'CREATE INDEX IF NOT EXISTS idx_supplier_is_deleted ON supplier(is_deleted);',
    
    // --- PRODUCT INDEXES ---
    'CREATE INDEX IF NOT EXISTS idx_product_name ON product(name);',
    'CREATE INDEX IF NOT EXISTS idx_variant_name ON product_variant(name);',
    'CREATE INDEX IF NOT EXISTS idx_variant_product ON product_variant(product_id);'
  ];
  
  indexes.forEach(idx => db.exec(idx));

  // --- TRIGGERS ---
  db.exec(`CREATE TRIGGER IF NOT EXISTS calc_balance_insert_item AFTER INSERT ON credit_sale_item BEGIN UPDATE customer SET balance = balance + (NEW.quantity * NEW.price_at_sale) WHERE id = (SELECT customer_id FROM credit_sale WHERE id = NEW.sale_id); END;`);
  db.exec(`CREATE TRIGGER IF NOT EXISTS calc_balance_delete_item AFTER DELETE ON credit_sale_item BEGIN UPDATE customer SET balance = balance - (OLD.quantity * OLD.price_at_sale) WHERE id = (SELECT customer_id FROM credit_sale WHERE id = OLD.sale_id); END;`);
  db.exec(`CREATE TRIGGER IF NOT EXISTS calc_balance_insert_payment AFTER INSERT ON payment BEGIN UPDATE customer SET balance = balance - NEW.amount WHERE id = NEW.customer_id; END;`);
  db.exec(`CREATE TRIGGER IF NOT EXISTS calc_balance_delete_payment AFTER DELETE ON payment BEGIN UPDATE customer SET balance = balance + OLD.amount WHERE id = OLD.customer_id; END;`);
}

module.exports = { getDB, initSchema, dbPath };