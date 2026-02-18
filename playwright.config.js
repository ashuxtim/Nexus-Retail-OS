const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: './tests', // We will put tests here
  timeout: 30000,     // Give the robot 30 seconds max per test
  retries: 1,         // If a test fails, try 1 more time (good for flaky UIs)
  workers: 1,         // Run 1 test at a time (Crucial for SQLite databases to avoid locking)
  use: {
    trace: 'on-first-retry', // Record a video/trace if a test fails
    headless: false,         // FALSE = You will see the robot working (Cool to watch!)
  },
});