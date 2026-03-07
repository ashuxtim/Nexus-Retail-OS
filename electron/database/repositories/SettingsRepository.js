const { getDB } = require('../db_manager');
const crypto = require('crypto');

// 🔒 SECURITY: Key is NOT hardcoded. It is injected at startup by main.js
// via setEncryptionKey(), which retrieves a machine-specific key from
// Electron's safeStorage (OS keychain / credential store).
let ENCRYPTION_KEY = null;
const IV_LENGTH = 16;

/**
 * Called once by main.js after safeStorage has retrieved the machine key.
 * Must be called before any get/set/getAll operations.
 * @param {Buffer} keyBuffer - 32-byte Buffer
 */
function setEncryptionKey(keyBuffer) {
  if (!Buffer.isBuffer(keyBuffer) || keyBuffer.length !== 32) {
    throw new Error('SettingsRepository: encryption key must be a 32-byte Buffer');
  }
  ENCRYPTION_KEY = keyBuffer;
}

function getKey() {
  if (!ENCRYPTION_KEY) {
    throw new Error('SettingsRepository: encryption key not initialized. Call setEncryptionKey() first.');
  }
  return ENCRYPTION_KEY;
}

function encrypt(text) {
  if (!text) return text;
  try {
    const iv = crypto.randomBytes(IV_LENGTH);
    const cipher = crypto.createCipheriv('aes-256-cbc', getKey(), iv);
    let encrypted = cipher.update(JSON.stringify(text));
    encrypted = Buffer.concat([encrypted, cipher.final()]);
    return iv.toString('hex') + ':' + encrypted.toString('hex');
  } catch (e) {
    console.error("Encryption failed:", e);
    return null;
  }
}

function decrypt(text) {
  if (!text) return null;
  try {
    const textParts = text.split(':');
    if (textParts.length < 2) {
      try { return JSON.parse(text); } catch { return text; }
    }
    const iv = Buffer.from(textParts.shift(), 'hex');
    const encryptedText = Buffer.from(textParts.join(':'), 'hex');
    const decipher = crypto.createDecipheriv('aes-256-cbc', getKey(), iv);
    let decrypted = decipher.update(encryptedText);
    decrypted = Buffer.concat([decrypted, decipher.final()]);
    return JSON.parse(decrypted.toString());
  } catch (e) {
    console.error("Decryption failed:", e);
    return null;
  }
}

module.exports = {
  setEncryptionKey,

  get(key) {
    const row = getDB().prepare('SELECT setting_value FROM app_settings WHERE setting_key = ?').get(key);
    if (!row) return null;
    return decrypt(row.setting_value);
  },

  getAll() {
    const rows = getDB().prepare('SELECT * FROM app_settings').all();
    const settings = {};
    rows.forEach(r => {
      const val = decrypt(r.setting_value);
      if (val !== null) settings[r.setting_key] = val;
    });
    return settings;
  },

  set(key, value) {
    try {
      const encryptedValue = encrypt(value);
      if (!encryptedValue) throw new Error("Encryption failed");

      getDB().prepare(`
        INSERT INTO app_settings (setting_key, setting_value) 
        VALUES (?, ?) 
        ON CONFLICT(setting_key) DO UPDATE SET setting_value = excluded.setting_value
      `).run(key, encryptedValue);
      return { success: true };
    } catch (e) { return { error: e.message }; }
  }
};