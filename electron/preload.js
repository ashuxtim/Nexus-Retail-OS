// FILE: app/electron/preload.js
const { contextBridge, ipcRenderer } = require('electron');

// Helper to unwrap standard backend response { success, data } -> data
const invokeStandard = async (channel, payload = {}) => {
  const response = await ipcRenderer.invoke(channel, payload);
  if (response && response.success === false) {
    throw new Error(response.error || 'Unknown IPC Error');
  }
  return response && response.data !== undefined ? response.data : response;
};

contextBridge.exposeInMainWorld('api', {
  // System & Config
  getAppConfig: () => ipcRenderer.invoke('app:get-config'),
  checkBackendHealth: () => ipcRenderer.invoke('app:check-health'),

  // Settings & AI
  getSettings: () => ipcRenderer.invoke('settings:get'),
  saveSettings: (data) => ipcRenderer.invoke('settings:save', data),
  getLocalSettings: () => ipcRenderer.invoke('local-settings:get-all'),
  saveLocalSetting: (key, val) => ipcRenderer.invoke('local-settings:save', key, val),
  askAI: (text) => ipcRenderer.invoke('ai:ask', text),
  transcribeAudio: (buffer) => ipcRenderer.invoke('ai:transcribe', buffer),
  scanReceipt: (buffer) => ipcRenderer.invoke('ai:scan-receipt', buffer),

  // Workers
  searchProducts: (query) => ipcRenderer.invoke('worker:search-products', query),
  searchSuppliersWorker: (search, limit) => ipcRenderer.invoke('worker:search-suppliers', search, limit),
  searchVariantsWorker: (query, limit) => ipcRenderer.invoke('worker:search-variants', query, limit),
  
  // Global Search
  searchGlobal: (term) => ipcRenderer.invoke('app:global-search', term),

  // Dashboard
  getDashboardStats: () => ipcRenderer.invoke('dashboard:get-stats'),
  getForecast: () => ipcRenderer.invoke('dashboard:get-forecast'),
  getAnalytics: () => ipcRenderer.invoke('dashboard:get-analytics'),

  // Products
  getProducts: (params) => invokeStandard('product:get-all', params),
  createProduct: (data) => invokeStandard('product:create', data),
  createFullProduct: (data) => invokeStandard('product:create-full', data),
  createVariant: (data) => invokeStandard('variant:create', data),
  updateVariant: (data) => invokeStandard('variant:update', data),
  deleteProduct: (id) => invokeStandard('product:delete', { id }),
  deleteVariant: (id) => invokeStandard('variant:delete', { id }),
  updateProduct: (data) => invokeStandard('product:update', data),

  // Customers
  getCustomers: () => invokeStandard('customer:get-all'),
  getCustomerById: (id) => invokeStandard('customer:get-by-id', { id }),
  createCustomer: (data) => invokeStandard('customer:create', data),
  deleteCustomer: (id) => invokeStandard('customer:delete', { id }),
  updateCustomer: (data) => invokeStandard('customer:update', data),
  getCustomersPaginated: (limit, offset, search) => invokeStandard('customer:get-paginated', { limit, offset, search }),
  getDueCustomers: () => invokeStandard('customer:get-due'),
  processCollection: (data) => invokeStandard('customer:process-collection', data),

  // Sales & History
  getSalesByCustomer: (id) => invokeStandard('sale:get-by-customer', { id }),
  getSalesByCustomerPaginated: (id, limit, offset) => invokeStandard('sale:get-by-customer-paginated', { id, limit, offset }),
  getPaymentsByCustomer: (id) => invokeStandard('payment:get-by-customer', { id }),
  getPaymentsByCustomerPaginated: (id, limit, offset) => invokeStandard('payment:get-by-customer-paginated', { id, limit, offset }),
  createPayment: (data) => invokeStandard('payment:create', data),
  deletePayment: (id) => invokeStandard('payment:delete', { id }),
  updatePayment: (data) => invokeStandard('payment:update', data),
  createSale: (data) => invokeStandard('sale:create', data),
  deleteSale: (id) => invokeStandard('sale:delete', { id }),
  getLastSale: () => invokeStandard('sale:get-last'),
  createFullTransaction: (data) => invokeStandard('sale:create-full', data),
  getDaybook: (date) => invokeStandard('sale:get-daybook', { date }),
  
  exportLedger: (start, end) => ipcRenderer.invoke('app:export-ledger', start, end),

  // Suppliers
  getSuppliers: (params) => invokeStandard('supplier:get-paginated', params),
  getSupplierList: () => invokeStandard('supplier:get-list'),
  getSupplierSearchMinimal: (params) => invokeStandard('supplier:get-search-minimal', params),
  getDeletedSuppliers: () => invokeStandard('supplier:get-deleted'),
  createSupplier: (data) => invokeStandard('supplier:create', data),
  updateSupplier: (data) => invokeStandard('supplier:update', data),
  softDeleteSupplier: (id) => invokeStandard('supplier:soft-delete', { id }),
  restoreSupplier: (id) => invokeStandard('supplier:restore', { id }),
  getSupplierPurchases: (id) => invokeStandard('supplier:get-purchases', { id }),
  getSupplierById: (id) => invokeStandard('supplier:get-by-id', { id }),
  getSupplierPurchasesPaginated: (id, page, limit) => invokeStandard('supplier:get-purchases-paginated', { supplierId: id, page, limit }),

  // Purchases (STANDARDIZED)
  getPurchases: (params) => invokeStandard('purchase:get-paginated', params),
  createPurchaseInvoice: (data) => invokeStandard('purchase:create-invoice', data),
  deletePurchase: (id) => invokeStandard('purchase:delete', { id }),
  getInvoiceDetails: (id) => invokeStandard('purchase:get-details', { id }),
  on: (channel, func) => ipcRenderer.on(channel, (event, ...args) => func(...args)),
  off: (channel, func) => ipcRenderer.removeListener(channel, func)
});
