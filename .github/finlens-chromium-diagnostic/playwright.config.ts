import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: '.', testMatch: '**/offline-browser-smoke.spec.ts',
  timeout: 12_000, workers: 1, retries: 0, globalTimeout: 20_000,
  reporter: 'list',
  use: {
    browserName: 'chromium', baseURL: 'http://127.0.0.1:3000', serviceWorkers: 'block',
    screenshot: 'off', trace: 'off', video: 'off',
  },
});
