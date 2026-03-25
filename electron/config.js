const path = require('path');
const { app } = require('electron');

const isDev = !app.isPackaged;

const config = {
  isDev,
  // Backend URL: Default port 8000 (dynamically overwritten by main.js in production)
  backendUrl: 'http://127.0.0.1:8000',
  
  // Python Backend Filename (for spawning)
  backendBinary: 'NexusBackend.exe',
  
  // Window Configuration
  window: {
    width: 1280,
    height: 800,
    minWidth: 1024,
    minHeight: 768,
  },

  // Content Security Policy (CSP) Settings
  csp: {
    // strict in production, looser in dev for Hot Module Replacement (HMR)
    scriptSrc: isDev ? ["'self'", "'unsafe-eval'", "'unsafe-inline'"] : ["'self'"],
    // basic connection permissions
    connectSrc: isDev 
      ? ["'self'", "http://127.0.0.1:8000", "ws://localhost:3000", "http://localhost:3000"] 
      : ["'self'", "http://127.0.0.1:8000"]
  }
};

module.exports = config;