import { defineConfig, devices } from '@playwright/test'
import { WEB_ORIGIN } from './harness/env.ts'

// Serial on purpose: one API and one database serve every case, and each case makes its own
// uniquely named data. No retries: a case that passes on the second try is a flaky case.
export default defineConfig({
  testDir: './specs',
  globalSetup: './harness/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: WEB_ORIGIN,
    trace: 'retain-on-failure',
    actionTimeout: 10_000,
    viewport: { width: 390, height: 844 },
    locale: 'en-GB',
    timezoneId: 'Europe/London',
  },
  projects: [
    { name: 'chromium', testIgnore: /jobs\.spec\.ts/, use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', testIgnore: /jobs\.spec\.ts/, use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', testIgnore: /jobs\.spec\.ts/, use: { ...devices['Desktop Safari'] } },
    // The cron jobs' entry points: no browser, so they run once, not once per browser.
    { name: 'jobs', testMatch: /jobs\.spec\.ts/ },
  ],
})
