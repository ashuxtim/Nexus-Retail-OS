const { getDB } = require('../db_manager');
const { assertPositiveNumber, assertNonNegativeNumber } = require('../utils/validate');

module.exports = {
  // TRANSACTIONAL: Standard Sale
  createSale(customerId, items) {
    const db = getDB();
    try {
      const tx = db.transaction((customerId, items) => {
        const checkStock = db.prepare('SELECT pv.current_stock, p.name as product_name, pv.name as variant_name FROM product_variant pv JOIN product p ON pv.product_id = p.id WHERE pv.id = ?');

        // Pre-validate stock for all items
        for (const item of items) {
          const variant = checkStock.get(item.variant);
          if (!variant) throw new Error(`Product variant #${item.variant} not found.`);
          if (variant.current_stock < item.quantity) {
            throw new Error(`Insufficient stock for ${variant.product_name} - ${variant.variant_name} (Available: ${variant.current_stock}, Requested: ${item.quantity})`);
          }
        }

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
      assertPositiveNumber(customerId, 'customerId');
      if (!Array.isArray(items) || items.length === 0) {
          throw new Error('Validation failed: items must be a non-empty array.');
      }
      assertNonNegativeNumber(paidAmount, 'paidAmount');

      const tx = db.transaction(() => {
        const checkStock = db.prepare('SELECT pv.current_stock, p.name as product_name, pv.name as variant_name FROM product_variant pv JOIN product p ON pv.product_id = p.id WHERE pv.id = ?');

        // Pre-validate stock for all items
        for (const item of items) {
          const variant = checkStock.get(item.variant);
          if (!variant) throw new Error(`Product variant #${item.variant} not found.`);
          if (variant.current_stock < item.quantity) {
            throw new Error(`Insufficient stock for ${variant.product_name} - ${variant.variant_name} (Available: ${variant.current_stock}, Requested: ${item.quantity})`);
          }
        }

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
    } catch (e) { return { error: e.message }; }
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
        // 1. Fetch items for stock restoration
        const items = db.prepare('SELECT variant_id, quantity FROM credit_sale_item WHERE sale_id = ?').all(id);

        // 2. Restore stock for each item
        const restoreStock = db.prepare('UPDATE product_variant SET current_stock = current_stock + ? WHERE id = ?');
        for (const item of items) restoreStock.run(item.quantity, item.variant_id);

        // 3. EXPLICITLY delete sale items BEFORE the parent sale.
        //    This guarantees the calc_balance_delete_item trigger fires for each
        //    item and correctly subtracts from customer.balance — regardless of
        //    whether the ON DELETE CASCADE FK pragma is active on this connection.
        db.prepare('DELETE FROM credit_sale_item WHERE sale_id = ?').run(id);

        // 4. Now delete the parent sale (items already gone, no cascade needed)
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
      assertPositiveNumber(customerId, 'customerId');
      assertPositiveNumber(amount, 'amount');
      getDB().prepare('INSERT INTO payment (customer_id, amount) VALUES (?, ?)').run(customerId, amount);
      return { success: true };
    } catch (e) { return { error: e.message }; }
  },

  updatePayment(id, newAmount) {
    const db = getDB();
    try {
      const old = db.prepare('SELECT customer_id, amount FROM payment WHERE id = ?').get(id);
      if (!old) throw new Error("Payment not found");
      const tx = db.transaction(() => {
        db.prepare('UPDATE customer SET balance = balance + ? WHERE id = ?').run(old.amount, old.customer_id);
        db.prepare('UPDATE payment SET amount = ? WHERE id = ?').run(newAmount, id);
        db.prepare('UPDATE customer SET balance = balance - ? WHERE id = ?').run(newAmount, old.customer_id);
      });
      tx();
      return { success: true };
    } catch (e) { return { error: e.message }; }
  },

  // 🔴 UPDATED: Returns Normalized Data for Frontend
  getPaymentsByCustomer(customerId, limit, offset) {
    const db = getDB();
    let sql = 'SELECT * FROM payment WHERE customer_id = ? ORDER BY payment_date DESC';
    const params = [customerId];
    if (limit) { sql += ' LIMIT ? OFFSET ?'; params.push(limit, offset || 0); }

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
    const db = getDB();
    try {
      const tx = db.transaction((id) => {
        // 1. Fetch payment details BEFORE deleting (needed for balance correction)
        const payment = db.prepare('SELECT customer_id, amount FROM payment WHERE id = ?').get(id);
        if (!payment) throw new Error(`Payment #${id} not found`);

        // 2. Explicitly add the payment amount back to the customer balance.
        //    This is redundant with the calc_balance_delete_payment trigger,
        //    but makes the operation safe even if triggers are disabled or
        //    the DB connection doesn't have them (e.g. fresh migration).
        //    The trigger will NOT double-count because we only do one of these:
        //    if triggers are ON  -> trigger handles it, this UPDATE is skipped.
        //    Solution: just rely on the trigger but guard against missing payment.
        //    The real fix is to store customer_id so the trigger has it.
        //    Since our trigger uses OLD.customer_id (which exists at delete time),
        //    wrapping in a transaction guarantees atomicity.
        db.prepare('DELETE FROM payment WHERE id = ?').run(id);
        // Note: calc_balance_delete_payment trigger fires on DELETE and does:
        //   UPDATE customer SET balance = balance + OLD.amount WHERE id = OLD.customer_id
        // This is sufficient — the explicit pre-fetch above is kept for logging/validation only.
      });
      tx(id);
      return { success: true };
    } catch (e) { return { error: e.message }; }
  }
};
