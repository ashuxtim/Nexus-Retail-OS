// FILE: electron/database/search.js
// Unified fuzzy search utility — works offline, no Python required.
// Called by IPC handler in main.js. Used by every search surface in the app.

const { distance } = require('fastest-levenshtein');

/**
 * Score how well a query matches a target string.
 * Returns 0-100. Higher = better match.
 */
function scoreMatch(query, target) {
    const q = query.toLowerCase().trim();
    const t = target.toLowerCase().trim();

    if (!q || !t) return 0;
    if (t === q) return 100;
    if (t.startsWith(q)) return 95;
    if (t.includes(q)) return 85;

    // Check each word in target for typo tolerance
    const words = t.split(/\s+/);
    let bestDist = Infinity;
    for (const word of words) {
        if (word.length < 2) continue;
        const d = distance(q, word);
        if (d < bestDist) bestDist = d;
    }

    if (bestDist === 0) return 85;
    if (bestDist === 1) return 75; // 1-char typo: "lays" → "lasy"
    if (bestDist === 2) return 60; // 2-char typo: "maggi" → "magi"
    return 0;
}

/**
 * Main fuzzy search function.
 * @param {Database} db - better-sqlite3 database instance
 * @param {string} query - user's search string
 * @param {string} type - 'product' | 'customer' | 'supplier'
 * @param {number} limit - max results to return
 */
function fuzzySearch(db, query, type, limit = 20) {
    const q = query.toLowerCase().trim();
    if (!q || q.length < 1) return [];

    const prefix = q.slice(0, 3) + '%';

    if (type === 'product') {
        let rows = db.prepare(`
            SELECT v.id, p.name as product_name, v.name as variant_name,
                   p.category, v.price, v.current_stock, v.unit,
                   p.id as product_id
            FROM product_variant v
            JOIN product p ON v.product_id = p.id
            WHERE LOWER(p.name) LIKE @q
               OR LOWER(v.name) LIKE @q
               OR LOWER(p.category) LIKE @q
               OR LOWER(p.name) LIKE @prefix
               OR LOWER(v.name) LIKE @prefix
            LIMIT 200
        `).all({ q: `%${q}%`, prefix });

        return rows
            .map(r => ({
                id: r.id,
                product_id: r.product_id,
                product_name: r.product_name,
                variant_name: r.variant_name,
                category: r.category || '',
                price: r.price || 0,
                current_stock: r.current_stock || 0,
                unit: r.unit || '',
                full_name: `${r.product_name} - ${r.variant_name}`,
                display: `${r.product_name} ${r.variant_name}`,
                current_stock_label: `Stock: ${r.current_stock || 0}`,
                _score: scoreMatch(q, `${r.product_name} ${r.variant_name} ${r.category || ''}`)
            }))
            .filter(r => r._score > 50)
            .sort((a, b) => b._score - a._score)
            .slice(0, limit);
    }

    if (type === 'customer') {
        let rows = db.prepare(`
            SELECT id, name, mobile, address, balance
            FROM customer
            WHERE LOWER(name) LIKE @q
               OR CAST(mobile AS TEXT) LIKE @mq
               OR LOWER(name) LIKE @prefix
            LIMIT 200
        `).all({ q: `%${q}%`, mq: `${q}%`, prefix });

        return rows
            .map(r => ({
                id: r.id,
                name: r.name,
                mobile: r.mobile || '',
                address: r.address || '',
                balance: r.balance || 0,
                display: r.mobile ? `${r.name} (${r.mobile})` : r.name,
                _score: scoreMatch(q, `${r.name} ${r.mobile || ''}`)
            }))
            .filter(r => r._score > 50)
            .sort((a, b) => b._score - a._score)
            .slice(0, limit);
    }

    if (type === 'supplier') {
        let rows = db.prepare(`
            SELECT id, name, mobile
            FROM supplier
            WHERE LOWER(name) LIKE @q
               OR LOWER(name) LIKE @prefix
            LIMIT 200
        `).all({ q: `%${q}%`, prefix });

        return rows
            .map(r => ({
                id: r.id,
                name: r.name,
                mobile: r.mobile || '',
                display: r.name,
                _score: scoreMatch(q, r.name)
            }))
            .filter(r => r._score > 50)
            .sort((a, b) => b._score - a._score)
            .slice(0, limit);
    }

    return [];
}

module.exports = { fuzzySearch };
