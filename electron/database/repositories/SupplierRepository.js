const { getDB } = require('../db_manager');

// Helper to get Local SQLite-ready date string
const getLocalTime = () => {
  const d = new Date();
  const local = new Date(d.getTime() - (d.getTimezoneOffset() * 60000));
  return local.toISOString().slice(0, 19).replace('T', ' ');
};

module.exports = {
  // --- SUPPLIER MANAGEMENT ---

  // SMART SORTED PAGINATION
  getPaginated({ page = 1, limit = 50, search = "" } = {}) {
    const offset = (page - 1) * limit;
    const term = `%${search}%`;
    const prefix = `${search}%`;
    const wordStart = `% ${search}%`;

    return getDB().prepare(`
      SELECT *,
        CASE 
          WHEN name LIKE ? THEN 1
          WHEN name LIKE ? THEN 2
          ELSE 3
        END as match_priority
      FROM supplier
      WHERE (name LIKE ? OR mobile LIKE ?)
      ORDER BY match_priority ASC, name ASC 
      LIMIT ? OFFSET ?
    `).all(prefix, wordStart, term, term, limit, offset);
  },

  getList() {
    return getDB().prepare('SELECT id, name FROM supplier ORDER BY name ASC').all();
  },

  // SMART SEARCH MINIMAL
  getSearchMinimal({ search = "", limit = 20 } = {}) {
    const term = `%${search}%`;
    const prefix = `${search}%`;
    const wordStart = `% ${search}%`;

    return getDB().prepare(`
      SELECT id, name, mobile, address,
        CASE 
          WHEN name LIKE ? THEN 1
          WHEN name LIKE ? THEN 2
          ELSE 3
        END as match_priority
      FROM supplier
      WHERE (name LIKE ? OR mobile LIKE ?)
      ORDER BY match_priority ASC, name ASC 
      LIMIT ?
    `).all(prefix, wordStart, term, term, limit);
  },

  getCount({ search = "" } = {}) {
    const term = `%${search}%`;
    const result = getDB().prepare(`
      SELECT COUNT(*) as count 
      FROM supplier 
      WHERE (name LIKE ? OR mobile LIKE ?)
    `).get(term, term);
    return result.count;
  },

  getDeleted() {
    return [];
  },

  create(name, mobile, address) {
    try {
      const info = getDB().prepare('INSERT INTO supplier (name, mobile, address) VALUES (?, ?, ?)').run(name, mobile, address);
      return { id: info.lastInsertRowid, name, mobile, address };
    } catch (e) { return { error: e.message }; }
  },

  update(id, name, mobile, address) {
    try {
      getDB().prepare('UPDATE supplier SET name = ?, mobile = ?, address = ? WHERE id = ?').run(name, mobile, address, id);
      return { success: true };
    } catch (e) { return { error: e.message }; }
  },

  softDelete(id) {
    try {
      getDB().prepare('DELETE FROM supplier WHERE id = ?').run(id);
      return { success: true };
    } catch (e) { return { error: e.message }; }
  },

  restore(id) {
    return { error: "Cannot restore permanently deleted supplier" };
  },

  // 1. GET SINGLE SUPPLIER
  getById(id) {
    return getDB().prepare('SELECT * FROM supplier WHERE id = ?').get(id);
  },

  // ---------------------------------------------------------
  // PURCHASE MANAGEMENT (MATCHING DB SCREENSHOT)
  // ---------------------------------------------------------

  getPurchasesPaginated({ page = 1, limit = 50 } = {}) {
    const offset = (page - 1) * limit;
    return getDB().prepare(`
      SELECT 
        pi.id, 
        pi.supplier_id, 
        pi.invoice_date, 
        pi.total_amount, 
        pi.reference_number, 
        s.name as supplier_name
      FROM purchase_invoice pi
      LEFT JOIN supplier s ON pi.supplier_id = s.id
      ORDER BY pi.invoice_date DESC
      LIMIT ? OFFSET ?
    `).all(limit, offset);
  },

  // 2. GET PAGINATED PURCHASES FOR A SPECIFIC SUPPLIER
  getPurchasesBySupplierPaginated(supplierId, page = 1, limit = 50) {
    const offset = (page - 1) * limit;
    return getDB().prepare(`
      SELECT 
        pi.id, 
        pi.invoice_date as invoicedate, 
        pi.total_amount as totalamount, 
        pi.reference_number as referencenumber, 
        (SELECT COUNT(*) FROM purchase_item WHERE invoice_id = pi.id) as itemcount
      FROM purchase_invoice pi 
      WHERE pi.supplier_id = ? 
      ORDER BY pi.invoice_date DESC 
      LIMIT ? OFFSET ?
    `).all(supplierId, limit, offset);
  },

  createPurchaseInvoice(supplierId, items, totalAmount, date) {
    const db = getDB();
    try {
      const tx = db.transaction((supplierId, items, totalAmount, date) => {
        const finalDate = date ? date : getLocalTime();
        
        // Corrected: purchase_invoice, supplier_id, invoice_date, total_amount
        const info = db.prepare('INSERT INTO purchase_invoice (supplier_id, total_amount, invoice_date) VALUES (?, ?, ?)').run(supplierId, totalAmount, finalDate);
        const invoiceId = info.lastInsertRowid;

        // Corrected: purchase_item, invoice_id, variant_id, unit_cost
        const insertItem = db.prepare('INSERT INTO purchase_item (invoice_id, variant_id, quantity, unit_cost) VALUES (?, ?, ?, ?)');
        
        // Corrected: product_variant, current_stock
        const updateStock = db.prepare('UPDATE product_variant SET current_stock = current_stock + ? WHERE id = ?');

        for (const item of items) {
          insertItem.run(invoiceId, item.variantId, item.quantity, item.price);
          updateStock.run(item.quantity, item.variantId);
        }

        return { success: true, invoiceId };
      });

      return tx(supplierId, items, totalAmount, date);
    } catch (e) { return { error: e.message }; }
  },

  deletePurchase(id) {
    const db = getDB();
    try {
      const tx = db.transaction((id) => {
        // Corrected: purchase_item, invoice_id, variant_id
        const items = db.prepare('SELECT variant_id, quantity FROM purchase_item WHERE invoice_id = ?').all(id);
        
        // Corrected: product_variant, current_stock
        const revertStock = db.prepare('UPDATE product_variant SET current_stock = current_stock - ? WHERE id = ?');

        for (const item of items) {
          revertStock.run(item.quantity, item.variant_id);
        }

        // Corrected: purchase_invoice
        db.prepare('DELETE FROM purchase_invoice WHERE id = ?').run(id);
      });

      tx(id);
      return { success: true };
    } catch (e) { return { error: e.message }; }
  },

  getInvoiceDetails(id) {
    const db = getDB();
    
    // Corrected: purchase_invoice, supplier_id
    const invoice = db.prepare(`
      SELECT pi.*, s.name as supplier_name 
      FROM purchase_invoice pi 
      LEFT JOIN supplier s ON pi.supplier_id = s.id 
      WHERE pi.id = ?
    `).get(id);

    if (!invoice) return null;

    // Corrected: purchase_item, product_variant, invoice_id, variant_id, product_id
    const items = db.prepare(`
      SELECT pi.*, p.name as product_name, v.name as variant_name
      FROM purchase_item pi
      JOIN product_variant v ON pi.variant_id = v.id
      JOIN product p ON v.product_id = p.id
      WHERE pi.invoice_id = ?
    `).all(id);

    // Normalize keys for frontend (Frontend expects camelCase or specific names)
    return { 
      id: invoice.id,
      suppliername: invoice.supplier_name,
      invoicedate: invoice.invoice_date,
      totalamount: invoice.total_amount,
      items: items.map(i => ({
        productname: i.product_name,
        variantname: i.variant_name,
        quantity: i.quantity,
        unitcost: i.unit_cost,
        ...i
      }))
    };
  },

  getBySupplierId(id) {
    // Admin/Debug helper - Corrected names
    return getDB().prepare(`
      SELECT pi.*, s.name as supplier_name, 
      (SELECT COUNT(*) FROM purchase_item WHERE invoice_id = pi.id) as item_count
      FROM purchase_invoice pi 
      LEFT JOIN supplier s ON pi.supplier_id = s.id 
      WHERE pi.supplier_id = ? 
      ORDER BY pi.invoice_date DESC
    `).all(id);
  }
};
