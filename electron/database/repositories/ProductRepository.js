const { getDB } = require('../db_manager');

module.exports = {
  getAll({ page = 1, limit = 100, search = "" } = {}) {
    const db = getDB();
    const offset = (page - 1) * limit;
    
    const searchTerm = `%${search}%`;
    const startTerm = `${search}%`;
    
    // CHANGED: Added "OR p.category LIKE ?" to the WHERE clause
    const products = db.prepare(`
      SELECT DISTINCT p.* FROM product p 
      LEFT JOIN product_variant v ON p.id = v.product_id 
      WHERE p.name LIKE ? OR v.name LIKE ? OR p.category LIKE ?
      ORDER BY 
        CASE WHEN p.name LIKE ? THEN 0 ELSE 1 END, 
        p.name ASC 
      LIMIT ? OFFSET ?`
    ).all(searchTerm, searchTerm, searchTerm, startTerm, limit, offset); 
    // ^ Note: Added "searchTerm" a third time in the .all() arguments above

    if (products.length === 0) return [];

    const productIds = products.map(p => p.id);
    const placeholders = productIds.map(() => '?').join(',');
    const variants = db.prepare(`SELECT * FROM product_variant WHERE product_id IN (${placeholders})`).all(...productIds);

    return products.map(p => ({ ...p, variants: variants.filter(v => v.product_id === p.id) }));
  },

  create(name, category) {
    try {
      const info = getDB().prepare('INSERT INTO product (name, category) VALUES (?, ?)').run(name, category);
      return { id: info.lastInsertRowid, name, category };
    } catch (e) { return { error: e.message }; }
  },

  // TRANSACTIONAL: Ensures partial data isn't saved if one part fails
  // TRANSACTIONAL: Checks if parent exists first. If so, adds variant to it. If not, creates both.
  createFull(productName, category, variantName, price, unit, stock) {
    const db = getDB();
    try {
      const tx = db.transaction(() => {
        let productId;
        
        // 1. Check if the Parent Product already exists
        const existingProduct = db.prepare('SELECT id FROM product WHERE name = ?').get(productName);

        if (existingProduct) {
          // Parent exists: Use its ID
          productId = existingProduct.id;
        } else {
          // Parent does not exist: Create it
          const pInfo = db.prepare('INSERT INTO product (name, category) VALUES (?, ?)').run(productName, category);
          productId = pInfo.lastInsertRowid;
        }

        // 2. Create the Variant linked to the found/created Product ID
        const vInfo = db.prepare('INSERT INTO product_variant (product_id, name, price, unit, current_stock) VALUES (?, ?, ?, ?, ?)').run(productId, variantName, price, unit, stock);
        
        return { productId: productId, variantId: vInfo.lastInsertRowid };
      });
      
      return tx();
    } catch (e) { return { error: e.message }; }
  },

  delete(id) {
    try {
        getDB().prepare('DELETE FROM product WHERE id = ?').run(id);
        return { success: true };
    } catch (e) { return { error: e.message }; }
  },

  // Variant Ops
  createVariant(productId, name, price, unit, stock) {
    try {
      const info = getDB().prepare('INSERT INTO product_variant (product_id, name, price, unit, current_stock) VALUES (?, ?, ?, ?, ?)').run(productId, name, price, unit, stock);
      return { id: info.lastInsertRowid, success: true };
    } catch (e) { return { error: e.message }; }
  },
  updateVariant(id, price, stock) {
    try {
      getDB().prepare('UPDATE product_variant SET price = ?, current_stock = ? WHERE id = ?').run(price, stock, id);
      return { success: true };
    } catch(e) { return { error: e.message }; }
  },
  deleteVariant(id) {
    try {
      getDB().prepare('DELETE FROM product_variant WHERE id = ?').run(id);
      return { success: true };
    } catch (e) { return { error: "Cannot delete variant with sales history." }; }
  },
  // NEW: Update Parent Product details
  update(id, name, category) {
    try {
      getDB().prepare('UPDATE product SET name = ?, category = ? WHERE id = ?').run(name, category, id);
      return { success: true };
    } catch (e) { return { error: e.message }; }
  }
};