const { Worker } = require('worker_threads');
const path = require('path');
const { dbPath } = require('../database/db_manager');

let worker;
const pendingRequests = new Map();

function initWorker() {
  try {
    worker = new Worker(path.join(__dirname, 'dbWorker.js'), {
      workerData: { dbPath }
    });

    worker.on('message', (msg) => {
      const { id, result, error } = msg;
      if (pendingRequests.has(id)) {
        const { resolve, reject } = pendingRequests.get(id);
        if (error) reject(new Error(error));
        else resolve(result);
        pendingRequests.delete(id);
      }
    });

    worker.on('error', (err) => {
      console.error("Worker Error:", err);
      // Reject all pending promises so callers don't hang forever
      for (const [id, { reject }] of pendingRequests.entries()) {
        reject(new Error(`Worker crashed: ${err.message}`));
      }
      pendingRequests.clear();
      worker = null;
    });

    worker.on('exit', (code) => {
      if (code !== 0) {
        console.error(`Worker exited with code ${code}`);
        for (const [id, { reject }] of pendingRequests.entries()) {
          reject(new Error(`Worker exited unexpectedly (code ${code})`));
        }
        pendingRequests.clear();
      }
      worker = null;
    });
  } catch (err) {
    console.error("Failed to init worker:", err);
    worker = null;
  }
}

function runInWorker(type, payload) {
  if (!worker) initWorker();
  const id = Date.now().toString() + Math.random().toString();
  return new Promise((resolve, reject) => {
    pendingRequests.set(id, { resolve, reject });
    try {
      worker.postMessage({ type, payload, id });
    } catch (err) {
      worker = null;
      reject(err);
    }
  });
}

function invalidateSupplierCache() {
  // OPTIMIZATION: Do not kill the worker. 
  // Send a reset signal to maintain the process & DB connection.
  if (worker) {
    try {
      worker.postMessage({ type: 'RESET_CACHE', id: 'system_reset' });
    } catch (e) {
      console.error("Worker reset error:", e);
      worker = null; // Fallback to re-init if communication fails
    }
  }
}

module.exports = {
  searchGlobal: (term) => runInWorker('SEARCH_GLOBAL', term),
  searchProducts: (query) => runInWorker('SEARCH_GLOBAL', query),
  searchSuppliers: (search, limit) => runInWorker('SEARCH_SUPPLIERS', { search, limit }),
  searchVariants: (query, limit) => runInWorker('SEARCH_VARIANTS', { query, limit }),
  exportLedgerData: (start, end) => runInWorker('EXPORT_LEDGER', { start, end }),
  getDaybook: (dateStr) => runInWorker('GET_DAYBOOK', { dateStr }),
  getDashboardStats: () => runInWorker('GET_DASHBOARD_STATS', {}),
  getProducts: (params) => runInWorker('GET_PRODUCTS', params || {}),
  invalidateSupplierCache: invalidateSupplierCache
};