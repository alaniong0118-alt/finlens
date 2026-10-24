import { defineConfig } from '@playwright/test';
import acceptance from './playwright.config';

// A deliberate execution switch, not a substitute for coordinator authorization.
if (process.env.FINLENS_CAPTURE_AUTHORIZED !== 'true') {
  throw new Error('Capture is default OFF. Obtain execution authorization before opting in.');
}

export default defineConfig({
  ...acceptance,
  testMatch: '**/research-walkthrough.capture.ts',
  outputDir: 'test-results/research-walkthrough/runner',
  reporter: [['list'], ['json', { outputFile: 'test-results/research-walkthrough/result.json' }]],
  use: {
    ...acceptance.use,
    viewport: { width: 1440, height: 1000 },
    deviceScaleFactor: 1,
    colorScheme: 'light',
    locale: 'en-US',
    timezoneId: 'UTC',
    reducedMotion: 'reduce',
    // Only the four explicitly annotated evidence captures are emitted.
    screenshot: 'off',
    trace: 'off',
    video: 'off',
  },
  projects: [{ name: 'synthetic-walkthrough-chromium' }],
  webServer: {
    ...acceptance.webServer,
    // exec keeps the receipt wrapper as Playwright's process-group leader.
    // The wrapper admits every copied render input before launch, rechecks after
    // cleanup, and attests the unchanged launcher's actual exit code.
    command: 'exec node scripts/package-research-walkthrough.mjs --serve',
  },
});
