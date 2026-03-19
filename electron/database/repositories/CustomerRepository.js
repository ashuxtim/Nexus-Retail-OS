const { getDB } = require('../db_manager');
const { assertPositiveNumber } = require('../utils/validate');

module.exports = {
  getAll() { return getDB().prepare('SELECT * FROM customer').all(); },
  
  // --- NEW: FETCH SINGLE CUSTOMER (Optimized) ---
  getById(id) {
    return getDB().prepare('SELECT * FROM customer WHERE id = ?').get(id);
  },
  // ----------------------------------------------

  getPaginated(limit, offset, search = "") {
    const searchTerm = `%${search}%`;
    const rows = getDB().prepare(`SELECT * FROM customer WHERE name LIKE ? OR mobile LIKE ? ORDER BY name ASC LIMIT ? OFFSET ?`).all(searchTerm, searchTerm, limit, offset);
    const count = getDB().prepare("SELECT COUNT(*) as total FROM customer WHERE name LIKE ? OR mobile LIKE ?").get(searchTerm, searchTerm);
    return { data: rows, total: count.total };
  },

  create(name, mobile, address) {
    try {
      const info = getDB().prepare('INSERT INTO customer (name, mobile, address) VALUES (?, ?, ?)').run(name, mobile, address);
      return { id: info.lastInsertRowid, name, mobile, address, balance: 0 };
    } catch (e) { return { error: "Customer name already exists" }; }
  },

  update(id, name, mobile, address) {
    try {
      getDB().prepare('UPDATE customer SET name = ?, mobile = ?, address = ? WHERE id = ?').run(name, mobile, address, id);
      return { success: true };
    } catch (e) { return { error: e.message }; }
  },

  delete(id) {
    try {
      getDB().prepare('DELETE FROM customer WHERE id = ?').run(id);
      return { success: true };
    } catch (e) { return { error: e.message }; }
  },

  getStats() {
  const db = getDB();
  const creditRes = db.prepare('SELECT SUM(balance) as total_credit FROM customer WHERE balance > 0').get();
  
  // ✅ FIX: Return "outstandingbalance" field name + increase limit
  const topDebtors = db.prepare(`
    SELECT 
      name, 
      mobile, 
      balance as outstandingbalance
    FROM customer 
    WHERE balance > 0 
    ORDER BY balance DESC 
    LIMIT 50
  `).all();
  
  return { credit: creditRes?.total_credit || 0, topDebtors };
},


  getDueCustomers() {
      const db = getDB();
      const today = new Date().toLocaleDateString('en-CA'); 
      return db.prepare(`
          SELECT id, name, balance, next_payment_date 
          FROM customer 
          WHERE next_payment_date IS NOT NULL 
          AND next_payment_date <= ? 
          AND balance > 0
          ORDER BY next_payment_date ASC
      `).all(today);
  },

  processCollection(customerId, amount, nextDate) {
      const db = getDB();
      try {
          const tx = db.transaction(() => {
              assertPositiveNumber(amount, 'amount');
              const customer = db.prepare('SELECT balance FROM customer WHERE id = ?').get(customerId);
              if (amount > customer.balance) {
                  throw new Error(`Payment of ${amount} exceeds outstanding balance of ${customer.balance}`);
              }
              if (amount > 0) {
                  db.prepare('INSERT INTO payment (customer_id, amount) VALUES (?, ?)').run(customerId, amount);
              }
              db.prepare('UPDATE customer SET next_payment_date = ? WHERE id = ?').run(nextDate, customerId);
          });
          tx();
          return { success: true };
      } catch(e) { return { error: e.message }; }
  }
};