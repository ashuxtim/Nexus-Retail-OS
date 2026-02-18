const { getDB } = require('../db_manager');

module.exports = {
  // TRANSACTIONAL: Standard Sale
  createSale(customerId, items) {
    const db = getDB();
    try {
      const tx = db.transaction((customerId, items) => {
        const saleId = db.prepare('INSERT INTO credit_sale (customer_id) VALUES (?)').run(customerId).lastInsertRowid;
        const insertItem = db.prepare('INSERT INTO credit_sale_item (sale_id, variant_id, quantity, price_at_sale) VALUES (?, ?, ?, ?)');
        const updateStock = db.prepare('UPDATE product_variant SET current_stock = current_stock - ? WHERE id = ?');

        for (const item of items) {
          insertItem.run(saleId, item.variant, item.quantity, item.price_at_sale);
          updateStock.run(item.quantity, item.variant);
        }
        return saleId;
      });
      return { success: true, saleId: tx(customerId, items) };
    } catch (e) { return { error: e.message }; }
  },

  createFullTransaction(customerId, items, paidAmount, nextPaymentDate, paymentMode = 'Cash') {
    const db = getDB();
    try {
      const tx = db.transaction(() => {
        // 1. Create Sale
        const saleId = db.prepare('INSERT INTO credit_sale (customer_id) VALUES (?)').run(customerId).lastInsertRowid;
        const insertItem = db.prepare('INSERT INTO credit_sale_item (sale_id, variant_id, quantity, price_at_sale) VALUES (?, ?, ?, ?)');
        const updateStock = db.prepare('UPDATE product_variant SET current_stock = current_stock - ? WHERE id = ?');

        for (const item of items) {
          insertItem.run(saleId, item.variant, item.quantity, item.price_at_sale);
          updateStock.run(item.quantity, item.variant);
        }

        // 2. Record Payment (With Mode)
        if (paidAmount > 0) {
          db.prepare('INSERT INTO payment (customer_id, amount, payment_mode) VALUES (?, ?, ?)').run(customerId, paidAmount, paymentMode);
        }

        // 3. Update Promise Date
        if (nextPaymentDate) {
          db.prepare('UPDATE customer SET next_payment_date = ? WHERE id = ?').run(nextPaymentDate, customerId);
        }
      });
      tx();
      return { success: true };
    } catch(e) { return { error: e.message }; }
  },

  getDaybookData(dateStr) {
    const db = getDB();
    const selectedDate = dateStr || new Date().toISOString().split('T')[0];
    const startOfDay = `${selectedDate} 00:00:00`;
    const endOfDay = `${selectedDate} 23:59:59`;

    const cashIn = db.prepare(`SELECT SUM(amount) as total FROM payment WHERE payment_date BETWEEN ? AND ?`).get(startOfDay, endOfDay).total || 0;
    const cashOut = db.prepare(`SELECT SUM(total_amount) as total FROM purchase_invoice WHERE invoice_date BETWEEN ? AND ?`).get(startOfDay, endOfDay).total || 0;
    
    // Note: purchase_invoice and invoice_date match your schema
    
    const totalSales = db.prepare(`SELECT SUM(i.quantity * i.price_at_sale) as total FROM credit_sale_item i JOIN credit_sale s ON i.sale_id = s.id WHERE s.sale_date BETWEEN ? AND ?`).get(startOfDay, endOfDay).total || 0;

    const items = db.prepare(`
      SELECT (p.name || ' ' || v.name) as name, SUM(i.quantity) as qty, SUM(i.quantity * i.price_at_sale) as total
      FROM credit_sale_item i
      JOIN credit_sale s ON i.sale_id = s.id
      JOIN product_variant v ON i.variant_id = v.id
      JOIN product p ON v.product_id = p.id
      WHERE s.sale_date BETWEEN ? AND ?
      GROUP BY v.id ORDER BY total DESC
    `).all(startOfDay, endOfDay);

    return { date: selectedDate, cashIn, cashOut, totalSales, netCash: cashIn - cashOut, items };
  },

  deleteSale(id) {
    const db = getDB();
    try {
      const tx = db.transaction((id) => {
        const items = db.prepare('SELECT variant_id, quantity FROM credit_sale_item WHERE sale_id = ?').all(id);
        const restoreStock = db.prepare('UPDATE product_variant SET current_stock = current_stock + ? WHERE id = ?');
        
        for (const item of items) restoreStock.run(item.quantity, item.variant_id);
        
        db.prepare('DELETE FROM credit_sale WHERE id = ?').run(id);
      });
      tx(id);
      return { success: true };
    } catch (e) { return { error: e.message }; }
  },

  // 🔴 UPDATED: Returns Normalized Data for Frontend
  getByCustomer(customerId, limit, offset) {
    const db = getDB();
    let sql = 'SELECT * FROM credit_sale WHERE customer_id = ? ORDER BY sale_date DESC';
    const params = [customerId];
    if (limit) { sql += ' LIMIT ? OFFSET ?'; params.push(limit, offset || 0); }

    const sales = db.prepare(sql).all(...params);

    const getItems = db.prepare(`
      SELECT i.*, v.name as variant_name, p.name as product_name 
      FROM credit_sale_item i 
      JOIN product_variant v ON i.variant_id = v.id 
      JOIN product p ON v.product_id = p.id 
      WHERE i.sale_id = ?
    `);

    // Map to frontend-friendly structure
    return sales.map(sale => {
      const items = getItems.all(sale.id).map(item => ({ 
        ...item, 
        variant_name: `${item.product_name} (${item.variant_name})` 
      }));
      
      // Calculate total amount for this sale
      const totalAmount = items.reduce((sum, item) => sum + (item.quantity * item.price_at_sale), 0);

      return {
        id: sale.id,
        type: 'SALE',
        date: sale.sale_date,    // Normalized 'date'
        amount: totalAmount,     // Calculated total
        items: items
      };
    });
  },

  getLastSale() {
    const db = getDB();
    const sale = db.prepare('SELECT * FROM credit_sale ORDER BY id DESC LIMIT 1').get();
    if (!sale) return null;
    const customer = db.prepare('SELECT * FROM customer WHERE id = ?').get(sale.customer_id);
    const items = db.prepare(`SELECT i.quantity, i.price_at_sale, p.name as product_name, v.name as variant_name FROM credit_sale_item i JOIN product_variant v ON i.variant_id = v.id JOIN product p ON v.product_id = p.id WHERE i.sale_id = ?`).all(sale.id);
    return { ...sale, customer, items };
  },

  createPayment(customerId, amount) {
    try {
      getDB().prepare('INSERT INTO payment (customer_id, amount) VALUES (?, ?)').run(customerId, amount);
      return { success: true };
    } catch (e) { return { error: e.message }; }
  },

  updatePayment(id, newAmount) {
    const db = getDB();
    try {
      const old = db.prepare('SELECT customer_id, amount FROM payment WHERE id = ?').get(id);
      if(!old) throw new Error("Payment not found");
      const tx = db.transaction(() => {
        db.prepare('UPDATE customer SET balance = balance + ? WHERE id = ?').run(old.amount, old.customer_id);
        db.prepare('UPDATE payment SET amount = ? WHERE id = ?').run(newAmount, id);
        db.prepare('UPDATE customer SET balance = balance - ? WHERE id = ?').run(newAmount, old.customer_id);
      });
      tx();
      return { success: true };
    } catch(e) { return { error: e.message }; }
  },

  // 🔴 UPDATED: Returns Normalized Data for Frontend
  getPaymentsByCustomer(customerId, limit, offset) {
    const db = getDB();
    let sql = 'SELECT * FROM payment WHERE customer_id = ? ORDER BY payment_date DESC';
    const params = [customerId];
    if(limit) { sql += ' LIMIT ? OFFSET ?'; params.push(limit, offset || 0); }
    
    const payments = db.prepare(sql).all(...params);
    
    // Map to frontend-friendly structure
    return payments.map(pay => ({
      id: pay.id,
      type: 'PAYMENT',
      date: pay.payment_date,  // Normalized 'date'
      amount: pay.amount,
      items: null
    }));
  },

  deletePayment(id) {
    try {
      getDB().prepare('DELETE FROM payment WHERE id = ?').run(id);
      return { success: true };
    } catch(e) { return { error: e.message }; }
  }
};
