const { LRUCache } = require('lru-cache');

// Cache configuration
const caches = {
  suppliers: new LRUCache({
    max: 100,           // 100 different queries cached
    ttl: 1000 * 60 * 5, // 5 minutes
    updateAgeOnGet: true
  }),
  
  products: new LRUCache({
    max: 50,
    ttl: 1000 * 60 * 3, // 3 minutes
    updateAgeOnGet: true
  }),
  
  purchases: new LRUCache({
    max: 50,
    ttl: 1000 * 60 * 2, // 2 minutes
    updateAgeOnGet: true
  })
};


// Generate cache key from params
function generateKey(prefix, params) {
  return `${prefix}:${JSON.stringify(params)}`;
}

// Get from cache
function get(cacheName, key) {
  return caches[cacheName]?.get(key);
}

// Set to cache
function set(cacheName, key, value) {
  return caches[cacheName]?.set(key, value);
}

// Invalidate cache
function invalidate(cacheName, pattern = null) {
  if (!caches[cacheName]) return;
  
  if (pattern) {
    // Clear specific pattern
    const cache = caches[cacheName];
    for (const key of cache.keys()) {
      if (key.includes(pattern)) {
        cache.delete(key);
      }
    }
  } else {
    // Clear all
    caches[cacheName].clear();
  }
}

// Invalidate all caches
function invalidateAll() {
  Object.values(caches).forEach(cache => cache.clear());
}

module.exports = {
  generateKey,
  get,
  set,
  invalidate,
  invalidateAll
};
