import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  globalTimeout: 600_000,
  expect: { timeout: 5_000 },
  forbidOnly: !!process.env.CI,
  reporter: [['list'], ['html', { open: 'never' }]],
  outputDir: 'test-results',
  use: {
    browserName: 'chromium',
    baseURL: 'http://127.0.0.1:3107',
    serviceWorkers: 'block',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
    actionTimeout: 10_000,
    navigationTimeout: 30_000,
  },
  projects: [
    { name: 'desktop-chromium', grepInvert: /@mobile-only/, use: { viewport: { width: 1440, height: 1000 } } },
    { name: 'mobile-width-chromium', testMatch: ['**/experience.spec.ts', '**/comparison.spec.ts', '**/comparison-gap-filter.spec.ts'], grepInvert: /@desktop-only/,
      use: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true } },
  ],
  webServer: {
    command: 'node scripts/e2e-server.mjs',
    url: 'http://127.0.0.1:3107',
    reuseExistingServer: false,
    timeout: 120_000,
    // Launcher owns the child tree and temporary copy, including on SIGTERM.
    gracefulShutdown: { signal: 'SIGTERM', timeout: 15_000 },
  },
});
