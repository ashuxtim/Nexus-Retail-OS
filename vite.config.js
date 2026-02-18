const { defineConfig } = require('vite');
const react = require('@vitejs/plugin-react');
const envCompatible = require('vite-plugin-env-compatible').default;
const path = require('path');

module.exports = defineConfig({
  base: './', // <--- CRITICAL FIX: Ensures assets load in Electron (file://)
  plugins: [
    react(),
    envCompatible(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    strictPort: true,
  },
  build: {
    outDir: 'build',
    emptyOutDir: true,
  },
});
