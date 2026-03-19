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
    payment_mode TEXT NOT NULL DEFAULT 'Cash',
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

  db.exec(`
    CREATE TABLE IF NOT EXISTS model_registry (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      model_id TEXT UNIQUE NOT NULL,
      task_type TEXT NOT NULL CHECK(task_type IN ('churn', 'forecast', 'market_basket')),
      algorithm TEXT NOT NULL,
      model_version TEXT NOT NULL,
      trained_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      trained_rows INTEGER NOT NULL,
      data_window_months INTEGER DEFAULT 24,
      feature_version TEXT DEFAULT 'v1',
      file_path TEXT NOT NULL,
      metrics_json TEXT NOT NULL,
      is_active INTEGER DEFAULT 0 CHECK(is_active IN (0,1)),
      promoted_at TIMESTAMP,
      replaced_by TEXT,
      evaluation_status TEXT CHECK(evaluation_status IN ('pending', 'approved', 'rejected')),
      evaluation_notes TEXT,
      FOREIGN KEY (replaced_by) REFERENCES model_registry(model_id)
    );

    CREATE TABLE IF NOT EXISTS dataset_snapshots (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      model_id TEXT NOT NULL,
      task_type TEXT NOT NULL,
      start_date DATE NOT NULL,
      end_date DATE NOT NULL,
      row_count INTEGER NOT NULL,
      feature_version TEXT,
      feature_hash TEXT,
      missing_rate REAL,
      outlier_rate REAL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      FOREIGN KEY (model_id) REFERENCES model_registry(model_id)
    );

    CREATE TABLE IF NOT EXISTS prediction_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      date DATE NOT NULL,
      task_type TEXT NOT NULL,
      model_version TEXT NOT NULL,
      total_predictions INTEGER,
      avg_prediction REAL,
      high_risk_count INTEGER,
      p25 REAL,
      p50 REAL,
      p75 REAL,
      p95 REAL,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      UNIQUE(date, task_type, model_version) ON CONFLICT REPLACE
    );

    CREATE TABLE IF NOT EXISTS analytics_snapshot (
      model_name TEXT PRIMARY KEY,
      data TEXT NOT NULL,
      saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_model_task_active ON model_registry(task_type, is_active);
    CREATE INDEX IF NOT EXISTS idx_model_trained_at ON model_registry(trained_at DESC);
    CREATE INDEX IF NOT EXISTS idx_snapshot_model ON dataset_snapshots(model_id);
    CREATE INDEX IF NOT EXISTS idx_pred_log_date ON prediction_log(date DESC);
  `);

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