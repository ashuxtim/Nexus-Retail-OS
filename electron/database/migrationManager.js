const fs = require('fs');
const path = require('path');
const Database = require('better-sqlite3');
const { app } = require('electron');

// 1. CONFIGURATION
const DB_FILENAME = 'nexus.db';

function getDbPath() {
  // Use env var if set (good for dev), otherwise standard UserData
  const userDataPath = process.env.NEXUS_USER_DATA || app.getPath('userData');
  if (!fs.existsSync(userDataPath)) {
    fs.mkdirSync(userDataPath, { recursive: true });
  }
  return path.join(userDataPath, DB_FILENAME);
}

function createBackup(dbPath) {
  try {
    if (!fs.existsSync(dbPath)) return;

    const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
    // Save backup in a 'backups' folder next to the DB
    const backupDir = path.join(path.dirname(dbPath), 'backups');
    
    if (!fs.existsSync(backupDir)) {
      fs.mkdirSync(backupDir, { recursive: true });
    }

    const backupPath = path.join(backupDir, `${DB_FILENAME}.${timestamp}.bak`);
    fs.copyFileSync(dbPath, backupPath);
    console.log(`📦 Backup created: ${path.basename(backupPath)}`);
  } catch (err) {
    console.error('❌ Backup Failed:', err.message);
    // In strict mode, we might throw here. 
    // For now, we log it but allow the app to try updating.
  }
}

function runMigrations() {
  const isDev = !app.isPackaged;
  console.log('🚧 Starting Database Pre-flight Check (JS Native)...');

  const dbPath = getDbPath();
  console.log(`📂 Database: ${dbPath}`);

  // 2. LOCATE MIGRATIONS FOLDER
  let migrationsDir;
  
  if (isDev) {
    // DEV: Go up from 'database/' to root, then into python_server/config/...
    migrationsDir = path.join(__dirname, '..', '..', 'python_server', 'config', 'schema_migrations');
  } else {
    // PROD: Look in the 'resources/migrations' folder
    migrationsDir = path.join(process.resourcesPath, 'migrations');
  }

  if (!fs.existsSync(migrationsDir)) {
    fs.mkdirSync(migrationsDir, { recursive: true });
    console.log('Migrations folder created automatically.');
  }

  // 3. OPEN DB (Synchronous)
  const db = new Database(dbPath);

  try {
    // 4. INIT HISTORY TABLE
    db.prepare(`
      CREATE TABLE IF NOT EXISTS migration_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        migration_name TEXT UNIQUE NOT NULL,
        applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `).run();

    // 5. CHECK FOR PENDING MIGRATIONS
    const files = fs.readdirSync(migrationsDir)
      .filter(f => f.endsWith('.sql'))
      .sort(); // Sorts 001, 002 correctly

    const pending = [];
    const checkStmt = db.prepare('SELECT 1 FROM migration_history WHERE migration_name = ?');

    for (const file of files) {
      if (!checkStmt.get(file)) {
        pending.push(file);
      }
    }

    if (pending.length === 0) {
      console.log('✅ System is up to date.');
      db.close();
      return true;
    }

    console.log(`🚀 Found ${pending.length} new updates.`);
    
    // 6. BACKUP BEFORE WRITE
    db.close(); // Close connection to safely copy file
    createBackup(dbPath);
    const dbWrite = new Database(dbPath); // Reopen

    // 7. APPLY (Transaction)
    const applyTx = dbWrite.transaction((filesToRun) => {
      for (const file of filesToRun) {
        console.log(`🔄 Applying: ${file}...`);
        const filePath = path.join(migrationsDir, file);
        const sql = fs.readFileSync(filePath, 'utf-8');
        
        // Execute SQL script
        dbWrite.exec(sql);
        
        // Record History
        dbWrite.prepare('INSERT INTO migration_history (migration_name) VALUES (?)').run(file);
        console.log(`   ✅ Success`);
      }
    });

    applyTx(pending);
    console.log('✨ All migrations applied successfully.');
    dbWrite.close();
    return true;

  } catch (err) {
    console.error('❌ CRITICAL: Migration Failed', err);
    if (db.open) db.close();
    throw err; // Throw so main.js catches it and shows the Error Box
  }
}

module.exports = { runMigrations };