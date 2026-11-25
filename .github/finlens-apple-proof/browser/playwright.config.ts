import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.',
  testMatch: '**/apple-first-run.spec.ts',
  timeout: 55_000,
  workers: 1,
  retries: 0,
  globalTimeout: 65_000,
  reporter: 'list',
  use: { browserName: 'chromium', baseURL: 'http://127.0.0.1:3000', serviceWorkers: 'block',
    screenshot: 'off', trace: 'off', video: 'off' },
});
