const { app, BrowserWindow, ipcMain, session, dialog, safeStorage } = require('electron');
const path = require('path');
const fs = require('fs');
const { spawn, execSync } = require('child_process');
const { Blob } = require('buffer');
const crypto = require('crypto');

const { autoUpdater } = require('electron-updater');
const log = require('electron-log');

// Configure Logger
autoUpdater.logger = log;
autoUpdater.logger.transports.file.level = 'info';
log.info('App starting...');

// --- Internal Modules ---
const config = require('./config');
const { initSchema, getDB } = require('./database/db_manager');
const cache = require('./database/cacheManager');
const WorkerHandler = require('./workers/workerHandler');
const { runMigrations } = require('./database/migrationManager');

// --- Repositories ---
const ProductRepo = require('./database/repositories/ProductRepository');
const CustomerRepo = require('./database/repositories/CustomerRepository');
const SaleRepo = require('./database/repositories/SaleRepository');
const SupplierRepo = require('./database/repositories/SupplierRepository');
const SettingsRepo = require('./database/repositories/SettingsRepository');

const appFolderName = "NexusRetailOS";
const customPath = path.join(app.getPath('appData'), appFolderName);
app.setPath('userData', customPath);

// ==========================================
// ENCRYPTION KEY BOOTSTRAP (safeStorage)
// ==========================================

/**
 * On first run: generates a cryptographically random 32-byte key,
 * encrypts it with the OS credential store (safeStorage), and saves
 * the encrypted blob to a file in userData.
 *
 * On subsequent runs: reads the encrypted blob and decrypts it.
 *
 * The decrypted key Buffer is passed to SettingsRepository so it
 * never needs to hardcode or store the key in plaintext.
 */
function initEncryptionKey() {
  const keyFilePath = path.join(app.getPath('userData'), '.nexus_vault');

  if (!safeStorage.isEncryptionAvailable()) {
    // Fallback: derive a key from a machine-specific ID (less secure but better than hardcoded)
    console.warn('⚠️  safeStorage unavailable — falling back to machine-id derived key');
    const os = require('os');
    const machineId = `${os.hostname()}-${os.platform()}-${os.arch()}`;
    const fallbackKey = crypto.createHash('sha256').update(machineId).digest();
    SettingsRepo.setEncryptionKey(fallbackKey);
    return;
  }

  let rawKey;

  if (fs.existsSync(keyFilePath)) {
    // Subsequent runs: decrypt the stored blob
    try {
      const encryptedBlob = fs.readFileSync(keyFilePath);
      rawKey = safeStorage.decryptString(encryptedBlob);
    } catch (e) {
      console.error('❌ Failed to read vault key — regenerating:', e.message);
      rawKey = null;
    }
  }

  if (!rawKey || rawKey.length !== 64) {
    // First run (or corrupted file): generate a fresh 32-byte key, store as 64-char hex
    const newKey = crypto.randomBytes(32);
    rawKey = newKey.toString('hex');
    const encryptedBlob = safeStorage.encryptString(rawKey);
    try {
      fs.mkdirSync(path.dirname(keyFilePath), { recursive: true });
      fs.writeFileSync(keyFilePath, encryptedBlob);
      console.log('🔑 New vault key generated and stored securely.');
    } catch (e) {
      console.error('❌ Failed to persist vault key:', e.message);
    }
  }

  const keyBuffer = Buffer.from(rawKey, 'hex');
  SettingsRepo.setEncryptionKey(keyBuffer);
  console.log('🔒 Encryption key initialized from secure OS storage.');
}

// --- Global State ---
let mainWindow;
let backendProcess = null;

// ==========================================
// API KEY INJECTION (Security: Memory-Only)
// ==========================================

/**
 * Inject API keys from encrypted DB into Python's memory on startup.
 * This ensures Python never needs to read/write keys to disk.
 * Keys are stored ONLY in Python's RAM and wiped when app closes.
 */
async function injectKeysIntoPython() {
  try {
    console.log('🔑 Loading API keys from database...');

    // 1. Read keys from database
    const groqKey = SettingsRepo.get('GROQ_API_KEY');
    const googleKey = SettingsRepo.get('GOOGLE_API_KEY');

    // 2. If no keys found, skip (first run or user hasn't configured)
    if (!groqKey && !googleKey) {
      console.log('⚠️  No API keys configured. User needs to set them in Settings page.');
      return;
    }

    // 3. Wait for Python server to be ready (max 15 seconds)
    const maxAttempts = 30;
    let attempt = 0;
    let pythonReady = false;

    console.log('⏳ Waiting for Python server to initialize...');

    while (attempt < maxAttempts && !pythonReady) {
      try {
        const response = await fetch(`${config.backendUrl}/health`, {
          method: 'GET',
          signal: AbortSignal.timeout(500)
        });

        if (response.ok) {
          pythonReady = true;
          console.log('✅ Python server is ready');
        }
      } catch (e) {
        // Server not ready yet, wait 500ms
        await new Promise(resolve => setTimeout(resolve, 500));
        attempt++;
      }
    }

    if (!pythonReady) {
      console.error('❌ Python server failed to start within 15 seconds');
      return;
    }

    // 4. Send keys to Python via POST /settings
    console.log('📤 Injecting API keys into Python memory...');

    const response = await fetch(`${config.backendUrl}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        groq_api_key: groqKey || '',
        google_api_key: googleKey || ''
      })
    });

    if (response.ok) {
      const result = await response.json();
      console.log('✅ API keys injected successfully:', result.message);
    } else {
      const errorText = await response.text();
      console.error('❌ Failed to inject keys. Python response:', errorText);
    }

  } catch (error) {
    console.error('❌ Error during key injection:', error.message);
  }
}


// ==========================================
// 1. LIFECYCLE & WINDOW MANAGEMENT
// ==========================================

function startBackend() {
  // 1. DEV MODE: Do NOT spawn Python.
  if (config.isDev) {
    console.log("⚠️ DEV MODE: Backend not spawned. Run python_server/main.py manually!");
    return;
  }

  // --- PROD MODE: Spawn the packaged EXE ---
  // ⚡ FIX 1: Point to 'backend' folder defined in package.json
  const executable = path.join(process.resourcesPath, 'backend', 'NexusBackend.exe');
  const userDataPath = app.getPath('userData');

  // Check if file exists to prevent immediate crash on spawn
  if (!fs.existsSync(executable)) {
    console.error("❌ CRITICAL: Backend binary not found at", executable);
    dialog.showErrorBox("Startup Error", "The analytics engine is missing. Please reinstall the app.");
    return;
  }

  console.log("🚀 PROD MODE: Spawning Backend Binary from:", executable);

  try {
    // --- SPAWN PROCESS WITH IPC BRIDGE ---
    backendProcess = spawn(executable, [], {
      stdio: ['ignore', 'pipe', 'pipe'], // 'pipe' enables listening to stdout
      windowsHide: true,

      // ⚡ FIX 2: Set Working Directory (CWD) to the EXE folder
      // This ensures XGBoost and Prophet can find their internal files
      cwd: path.dirname(executable),

      env: {
        ...process.env,
        NEXUS_USER_DATA: userDataPath, // Pass the shared cache path
        PYTHONUNBUFFERED: "1",
        PYTHONUTF8: "1"
      }
    });

    // --- ERROR HANDLING (Prevent App Crash) ---
    backendProcess.on('error', (err) => {
      console.error("❌ Backend Process Failed to Start:", err.message);
      backendProcess = null; // Mark as dead so we don't try to kill it later
    });

    backendProcess.on('exit', (code, signal) => {
      if (code !== 0 && code !== null) {
        console.warn(`⚠️ Backend exited unexpectedly with code ${code}`);
      }
      backendProcess = null;
    });

    // ✅ NEW: Inject API keys after Python spawns
    backendProcess.on('spawn', () => {
      console.log('🐍 Python process spawned successfully');
      // Wait 2 seconds for Python to fully initialize, then inject keys
      setTimeout(() => {
        injectKeysIntoPython().catch(err => {
          console.error('❌ Key injection failed:', err);
        });
      }, 2000);
    });


    // --- LISTEN FOR SIGNALS (Production Only) ---
    if (backendProcess.stdout) {
      backendProcess.stdout.on('data', (data) => {
        const str = data.toString().trim();

        // Debug Log (Optional - helpful to see if Uvicorn starts)
        // console.log(`[Python]: ${str}`);

        // THE MAGIC SIGNAL TRIGGER
        if (str.includes('>>ANALYTICS_READY<<')) {
          console.log("⚡ Analytics Finished. Refreshing UI...");
          if (mainWindow) {
            mainWindow.webContents.send('analytics:ready');
          }
        }
      });
    }

    if (backendProcess.stderr) {
      backendProcess.stderr.on('data', (data) => console.error(`[Python Error]: ${data}`));
    }

  } catch (e) {
    console.error("❌ Fatal Error spawning backend:", e);
    // App continues running despite this error
  }
}


function killBackend() {
  if (!backendProcess) return;

  // 1. Try Graceful Shutdown first
  backendProcess.kill('SIGTERM');

  // 2. Force kill if it doesn't close within 3 seconds
  setTimeout(() => {
    if (backendProcess) {
      console.log("Backend did not exit gracefully. Force killing...");
      try {
        if (process.platform === 'win32') {
          execSync(`taskkill /pid ${backendProcess.pid} /T /F`);
        } else {
          backendProcess.kill('SIGKILL');
        }
      } catch (e) {
        // Ignore errors if it's already dead
      }
      backendProcess = null;
    }
  }, 3000);
}

function createWindow() {
  mainWindow = new BrowserWindow({
    title: "Nexus Retail OS",
    width: config.window.width,
    height: config.window.height,
    minWidth: config.window.minWidth,
    minHeight: config.window.minHeight,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: false
    }
  });

  // CSP Setup
  session.defaultSession.webRequest.onHeadersReceived((details, callback) => {
    const responseHeaders = { ...details.responseHeaders };
    delete responseHeaders['content-security-policy'];
    delete responseHeaders['Content-Security-Policy'];

    const csp = [
      "default-src 'self'",
      `script-src ${config.csp.scriptSrc.join(' ')}`,
      "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
      "font-src 'self' data: https://fonts.gstatic.com",
      "img-src 'self' data: blob:",
      `connect-src ${config.csp.connectSrc.join(' ')}`,
      "object-src 'none'",
      "base-uri 'self'"
    ].join('; ');

    responseHeaders['Content-Security-Policy'] = [csp];
    callback({ responseHeaders });
  });

  if (config.isDev) {
    mainWindow.loadURL('http://localhost:3000');
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'build', 'index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.setMenuBarVisibility(false);
    mainWindow.show();
  });
}

// Inside app.whenReady()
app.whenReady().then(() => {
  try {
    // 0. INIT ENCRYPTION KEY (must happen before any DB reads)
    initEncryptionKey();

    // 1. RUN MIGRATIONS (Native JS)
    // This is synchronous. If it fails, it throws an error.
    const migrationSuccess = runMigrations();

    if (migrationSuccess) {
      // 2. CONTINUE STARTUP
      initSchema();
      startBackend();
      createWindow();

      if (!config.isDev) { // Only run updater in Production
        setTimeout(() => {
          setupAutoUpdater();
        }, 3000);
      }
    } else {
      // If runMigrations returned false (e.g. folder missing)
      throw new Error("Migration system check failed (Files missing).");
    }

  } catch (err) {
    // 3. FATAL ERROR UI
    console.error("Startup Failed:", err);
    dialog.showErrorBox(
      'Startup Error',
      'Database update failed. The app cannot start.\n\nError: ' + err.message
    );
    app.exit(1);
  }

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('will-quit', killBackend);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// ==========================================
// AUTO-UPDATER LOGIC
// ==========================================
function setupAutoUpdater() {
  console.log('🔍 Checking for updates...');

  // 1. Check Immediately
  autoUpdater.checkForUpdatesAndNotify();

  // 2. Event Listeners
  autoUpdater.on('checking-for-update', () => {
    log.info('Checking for updates...');
  });

  autoUpdater.on('update-available', (info) => {
    log.info('Update available:', info);
    // Optional: Send event to renderer to show a spinner
    if (mainWindow) mainWindow.webContents.send('update:available');
  });

  autoUpdater.on('update-not-available', (info) => {
    log.info('Update not available.');
  });

  autoUpdater.on('error', (err) => {
    log.error('Update error:', err);
  });

  autoUpdater.on('download-progress', (progressObj) => {
    let log_message = "Download speed: " + progressObj.bytesPerSecond;
    log_message = log_message + ' - Downloaded ' + progressObj.percent + '%';
    log.info(log_message);
    // Optional: Send progress to renderer
    if (mainWindow) mainWindow.webContents.send('update:progress', progressObj.percent);
  });

  autoUpdater.on('update-downloaded', (info) => {
    log.info('Update downloaded');

    // 3. Prompt User to Restart
    dialog.showMessageBox({
      type: 'info',
      title: 'Update Ready',
      message: 'A new version of Nexus Retail OS is ready. Restart now to apply?',
      buttons: ['Restart Now', 'Later']
    }).then((result) => {
      if (result.response === 0) { // Index 0 = "Restart Now"
        // silent = true, forceRunAfter = true
        autoUpdater.quitAndInstall(false, true);
      }
    });
  });
}

// ==========================================
// 2. IPC HANDLERS - SYSTEM & CORE
// ==========================================

// Helper for Python Requests
// Helper for Python Requests
const fetchPython = async (endpoint, method = 'GET', body = null) => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 65000);
  try {
    // CACHE BUSTING: Append timestamp to prevent Electron/Chromium from caching local GET requests
    const separator = endpoint.includes('?') ? '&' : '?';
    const url = `${config.backendUrl}${endpoint}${separator}_t=${Date.now()}`;

    const options = {
      method,
      headers: { 'Content-Type': 'application/json' },
      signal: controller.signal,
    };
    if (body) options.body = JSON.stringify(body);

    const response = await fetch(url, options);
    if (!response.ok) throw new Error(`Python API Error: ${response.statusText}`);
    return await response.json();
  } catch (err) {
    if (err.name === 'AbortError') {
      return { status: "Inactive", error: "Request timed out (65s)", error_type: "timeout" };
    }
    return { status: "Inactive", error: err.message };
  } finally {
    clearTimeout(timeoutId);
  }
};

ipcMain.handle('app:get-config', () => ({
  appName: "NexusRetail OS AI",
  version: app.getVersion(),
  isDev: config.isDev,
  backendUrl: config.backendUrl
}));

ipcMain.handle('app:check-health', async () => {
  return await fetchPython('/health');
});

// --- WORKER DELEGATION ---
ipcMain.handle('worker:search-products', (e, q) => WorkerHandler.searchProducts(q));
ipcMain.handle('worker:search-suppliers', (e, q, l) => WorkerHandler.searchSuppliers(q, l));
ipcMain.handle('worker:search-variants', (e, q, l) => WorkerHandler.searchVariants(q, l));
ipcMain.handle('app:global-search', (e, term) => WorkerHandler.searchGlobal(term));

ipcMain.handle('app:export-ledger', async (e, s, end) => {
  const { canceled, filePath } = await dialog.showSaveDialog({
    title: 'Export Ledger',
    defaultPath: `Nexus_Ledger.csv`,
    filters: [{ name: 'CSV File', extensions: ['csv'] }]
  });

  if (canceled || !filePath) return { canceled: true };

  try {
    const rows = await WorkerHandler.exportLedgerData(s, end);
    const stream = fs.createWriteStream(filePath, { encoding: 'utf8' });

    stream.write("Date,Type,Transaction ID,Customer Name,Mobile,Address,Details,Amount\n");

    for (const row of rows) {
      const safeName = (row.customer_name || '').replace(/"/g, '""');
      const safeDetails = (row.details || '').replace(/"/g, '""');
      stream.write(`${row.date},${row.type},${row.transaction_id},"${safeName}","${row.customer_mobile}","${row.customer_address}","${safeDetails}",${row.amount}\n`);
    }

    stream.end();
    return { success: true, filePath };
  } catch (err) { return { error: err.message }; }
});

// --- AI ASSISTANT ---
ipcMain.handle('ai:ask', async (e, text) => {
  return await fetchPython('/ask', 'POST', { text });
});

ipcMain.handle('ai:transcribe', async (e, arrayBuffer) => {
  try {
    const blob = new Blob([arrayBuffer], { type: 'audio/webm' });
    const formData = new FormData();
    formData.append('file', blob, 'voice.webm');

    const res = await fetch(`${config.backendUrl}/transcribe`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error("Transcription Failed");
    return await res.json();
  } catch (e) { return { error: e.message }; }
});

ipcMain.handle('ai:scan-receipt', async (e, arrayBuffer) => {
  try {
    const blob = new Blob([arrayBuffer], { type: 'image/jpeg' });
    const formData = new FormData();
    formData.append('file', blob, 'receipt.jpg');

    const res = await fetch(`${config.backendUrl}/scan_receipt`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error("Scan Failed");
    return await res.json();
  } catch (e) { return { error: e.message }; }
});

// --- SETTINGS ---
ipcMain.handle('settings:get', async () => fetchPython('/settings'));
ipcMain.handle('settings:save', async (e, data) => {
  try {
    // 1. Save to encrypted database first
    if (data.groq_api_key) {
      SettingsRepo.set('GROQ_API_KEY', data.groq_api_key);
    }
    if (data.google_api_key) {
      SettingsRepo.set('GOOGLE_API_KEY', data.google_api_key);
    }

    // 2. Send to Python (so it updates in-memory immediately)
    const result = await fetchPython('/settings', 'POST', data);

    console.log('✅ Settings saved to database and sent to Python');
    return result;
  } catch (err) {
    console.error('❌ Settings save failed:', err);
    return { error: err.message };
  }
});

ipcMain.handle('local-settings:get-all', () => SettingsRepo.getAll());
ipcMain.handle('local-settings:save', (e, key, val) => SettingsRepo.set(key, val));

// --- DASHBOARD ---

ipcMain.handle('dashboard:get-stats', () => {
  try {
    const custStats = CustomerRepo.getStats()
    const db = getDB()

    const prodCount = db.prepare(`SELECT COUNT(*) as c FROM product_variant`).get().c
    const custCount = db.prepare(`SELECT COUNT(*) as c FROM customer`).get().c

    const lowStock = db.prepare(`
      SELECT 
        p.name as product_name,
        v.name as variant_name,
        v.current_stock as total_stock,
        p.category
      FROM product_variant v 
      JOIN product p ON v.product_id = p.id 
      WHERE v.current_stock <= 10
      ORDER BY v.current_stock ASC
      LIMIT 50
    `).all()

    // ✅ FIX: Map field names to match frontend expectations (with underscores)
    const debtors = custStats.topDebtors.map(debtor => ({
      name: debtor.name,
      mobile: debtor.mobile,
      outstanding_balance: debtor.outstandingbalance  // ✅ Add underscore
    }))

    return {
      totaloutstandingcredit: custStats.credit || 0,
      totalproductvariants: prodCount || 0,
      totalcustomers: custCount || 0,
      low_stock_items: lowStock,           // ✅ Changed to use underscores
      top_customers_by_credit: debtors     // ✅ Changed to use underscores
    }
  } catch (err) {
    console.error('Dashboard Stats Error:', err)
    return { error: err.message }
  }
});


ipcMain.handle('dashboard:get-forecast', async () => {
  try {
    // Non-blocking fetch. If Python is down/slow, catch and return safe object.
    const res = await fetchPython('/forecast');
    if (res && res.error) return { error: res.error };
    return res;
  } catch (err) {
    console.warn("Forecast unavailable:", err.message);
    return { error: "Service Unavailable", forecast: [], history: [] };
  }
});


ipcMain.handle('dashboard:get-analytics', async () => {
  try {
    const userDataPath = app.getPath('userData');
    const cachePath = path.join(userDataPath, 'analytics_cache.json');

    let analyticsData = null;

    // 1. Try reading analytics_cache.json (Fast Load)
    if (fs.existsSync(cachePath)) {
      try {
        const raw = fs.readFileSync(cachePath, 'utf8');
        const parsed = JSON.parse(raw);
        const cacheTime = new Date(parsed.timestamp).getTime();
        const now = Date.now();

        // 4 Hours Expiry
        if ((now - cacheTime) < 14400000 && parsed.data) {
          analyticsData = parsed.data;
        }
      } catch (parseErr) {
        console.warn("Corrupt analytics cache");
      }
    }

    // 2. If cache stale/missing, fetch from Python (Source of Truth)
    if (!analyticsData) {
      const res = await fetchPython('/analytics/dashboard');
      analyticsData = res && res.data ? res.data : res;
    }

    // 3. Format Stockouts (ensure fields exist)
    if (analyticsData && Array.isArray(analyticsData.stockouts)) {
      analyticsData.stockouts = analyticsData.stockouts.map(item => ({
        name: item.name,
        variant_id: item.variant_id,
        stock: item.stock,
        days_left: item.days_left,
        status: item.status,
        metrics: item.metrics || null,
        recommendation: item.recommendation || null
      }));
    }

    return analyticsData || { status: 'unavailable', data: null };

  } catch (err) {
    console.warn("Analytics unavailable:", err.message);
    return { status: 'unavailable', data: null };
  }
});



// ==========================================
// 3. IPC HANDLERS - SUPPLIERS
// ==========================================
ipcMain.handle('supplier:get-paginated', async (e, params) => {
  try {
    const cacheKey = cache.generateKey('suppliers:paginated', params);
    let result = cache.get('suppliers', cacheKey);
    if (!result) {
      result = SupplierRepo.getPaginated(params);
      cache.set('suppliers', cacheKey, result);
    }
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('supplier:get-list', async () => {
  try {
    const cacheKey = 'suppliers:list:all';
    let result = cache.get('suppliers', cacheKey);
    if (!result) {
      result = SupplierRepo.getList();
      cache.set('suppliers', cacheKey, result);
    }
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('supplier:get-search-minimal', async (e, params) => {
  try {
    const cacheKey = cache.generateKey('suppliers:search', params);
    let result = cache.get('suppliers', cacheKey);
    if (!result) {
      result = SupplierRepo.getSearchMinimal(params);
      cache.set('suppliers', cacheKey, result);
    }
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('supplier:get-deleted', async () => {
  try { return { success: true, data: SupplierRepo.getDeleted() }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('supplier:create', async (e, data) => {
  try {
    const existing = SupplierRepo.getSearchMinimal({ search: data.name, limit: 1 });
    if (existing && existing.length > 0) {
      return { success: true, data: { id: existing[0].id, name: existing[0].name, note: 'Already exists' } };
    }
    const result = SupplierRepo.create(data.name, data.mobile, data.address);
    if (result.error) throw new Error(result.error);
    cache.invalidate('suppliers');
    if (WorkerHandler.invalidateSupplierCache) WorkerHandler.invalidateSupplierCache();
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('supplier:update', async (e, data) => {
  try {
    const result = SupplierRepo.update(data.id, data.name, data.mobile, data.address);
    if (result.error) throw new Error(result.error);
    cache.invalidate('suppliers');
    WorkerHandler.invalidateSupplierCache();
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('supplier:soft-delete', async (e, { id }) => {
  try {
    const result = SupplierRepo.softDelete(id);
    if (result.error) throw new Error(result.error);
    cache.invalidate('suppliers');
    WorkerHandler.invalidateSupplierCache();
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('supplier:restore', async (e, { id }) => {
  try {
    const result = SupplierRepo.restore(id);
    if (result.error) throw new Error(result.error);
    cache.invalidate('suppliers');
    WorkerHandler.invalidateSupplierCache();
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('supplier:get-purchases', async (e, { id }) => {
  try { return { success: true, data: SupplierRepo.getBySupplierId(id) }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('supplier:get-by-id', async (e, { id }) => {
  try { return { success: true, data: SupplierRepo.getById(id) }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('supplier:get-purchases-paginated', async (e, { supplierId, page, limit }) => {
  try {
    const cacheKey = cache.generateKey('purchases', { supplierId, page, limit });
    let result = cache.get('purchases', cacheKey);
    if (!result) {
      result = SupplierRepo.getPurchasesBySupplierPaginated(supplierId, page, limit);
      cache.set('purchases', cacheKey, result);
    }
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

// ==========================================
// 4. IPC HANDLERS - PRODUCTS & INVENTORY
// ==========================================
ipcMain.handle('product:get-all', async (e, params = {}) => {
  try { return { success: true, data: ProductRepo.getAll(params) }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('product:create', async (e, data) => {
  try {
    const result = ProductRepo.create(data.name, data.category);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('products');
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('product:create-full', async (e, data) => {
  try {
    const result = ProductRepo.createFull(data.name, data.category, data.variantName, data.price, data.unit, data.stock);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('products');
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('variant:create', async (e, data) => {
  try {
    const result = ProductRepo.createVariant(data.productId, data.name, data.price, data.unit, data.stock);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('products');
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('variant:update', async (e, data) => {
  try {
    const result = ProductRepo.updateVariant(data.id, data.price, data.stock);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('products');
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('product:delete', async (e, { id }) => {
  try {
    const result = ProductRepo.delete(id);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('products');
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('variant:delete', async (e, { id }) => {
  try {
    const result = ProductRepo.deleteVariant(id);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('products');
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('product:update', async (e, data) => {
  try {
    const result = ProductRepo.update(data.id, data.name, data.category);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('products');
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

// ==========================================
// 5. IPC HANDLERS - CUSTOMERS & SALES
// ==========================================
ipcMain.handle('customer:get-all', async () => {
  try { return { success: true, data: CustomerRepo.getAll() }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('customer:get-by-id', async (e, { id }) => {
  try { return { success: true, data: CustomerRepo.getById(id) }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('customer:create', async (e, data) => {
  try {
    const result = CustomerRepo.create(data.name, data.mobile, data.address);
    if (result?.error) throw new Error(result.error);
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('customer:update', async (e, data) => {
  try {
    const result = CustomerRepo.update(data.id, data.name, data.mobile, data.address);
    if (result?.error) throw new Error(result.error);
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('customer:delete', async (e, { id }) => {
  try {
    const result = CustomerRepo.delete(id);
    if (result?.error) throw new Error(result.error);
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('customer:get-paginated', async (e, { limit, offset, search }) => {
  try { return { success: true, data: CustomerRepo.getPaginated(limit, offset, search) }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('customer:get-due', async () => {
  try { return { success: true, data: CustomerRepo.getDueCustomers() }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('customer:process-collection', async (e, data) => {
  try {
    const result = CustomerRepo.processCollection(data.customerId, data.amount, data.nextDate);
    if (result?.error) throw new Error(result.error);
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('sale:get-by-customer', async (e, { id }) => {
  try { return { success: true, data: SaleRepo.getByCustomer(id) }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('sale:get-by-customer-paginated', async (e, { id, limit, offset }) => {
  try { return { success: true, data: SaleRepo.getByCustomer(id, limit, offset) }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('payment:get-by-customer', async (e, { id }) => {
  try { return { success: true, data: SaleRepo.getPaymentsByCustomer(id) }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('payment:get-by-customer-paginated', async (e, { id, limit, offset }) => {
  try { return { success: true, data: SaleRepo.getPaymentsByCustomer(id, limit, offset) }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('payment:create', async (e, data) => {
  try {
    const result = SaleRepo.createPayment(data.customerId, data.amount);
    if (result?.error) throw new Error(result.error);
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('payment:update', async (e, data) => {
  try {
    const result = SaleRepo.updatePayment(data.id, data.amount);
    if (result?.error) throw new Error(result.error);
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('payment:delete', async (e, { id }) => {
  try {
    const result = SaleRepo.deletePayment(id);
    if (result?.error) throw new Error(result.error);
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('sale:create', async (e, data) => {
  try {
    const result = SaleRepo.createSale(data.customerId, data.items);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('products');
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('sale:delete', async (e, { id }) => {
  try {
    const result = SaleRepo.deleteSale(id);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('products');
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('sale:get-last', async () => {
  try { return { success: true, data: SaleRepo.getLastSale() }; }
  catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('sale:create-full', async (e, data) => {
  try {
    const result = SaleRepo.createFullTransaction(data.customerId, data.items, data.paidAmount, data.nextPaymentDate);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('products');
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('sale:get-daybook', async (e, { date }) => {
  try { return { success: true, data: SaleRepo.getDaybookData(date) }; }
  catch (err) { return { success: false, error: err.message }; }
});

// ==========================================
// 6. IPC HANDLERS - PURCHASES (STANDARDIZED)
// ==========================================

ipcMain.handle('purchase:get-paginated', async (e, params) => {
  try {
    const cacheKey = cache.generateKey('purchases:paginated', params);
    let result = cache.get('purchases', cacheKey);
    if (!result) {
      result = SupplierRepo.getPurchasesPaginated(params);
      cache.set('purchases', cacheKey, result);
    }
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('purchase:create-invoice', async (e, data) => {
  try {
    const result = SupplierRepo.createPurchaseInvoice(data.supplierId, data.items, data.totalAmount, data.date);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('purchases');
    cache.invalidate('products'); // Stock changed
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('purchase:delete', async (e, { id }) => {
  try {
    const result = SupplierRepo.deletePurchase(id);
    if (result?.error) throw new Error(result.error);
    cache.invalidate('purchases');
    cache.invalidate('products'); // Stock reverted
    return { success: true, data: result };
  } catch (err) { return { success: false, error: err.message }; }
});

ipcMain.handle('purchase:get-details', async (e, { id }) => {
  try { return { success: true, data: SupplierRepo.getInvoiceDetails(id) }; }
  catch (err) { return { success: false, error: err.message }; }
});
