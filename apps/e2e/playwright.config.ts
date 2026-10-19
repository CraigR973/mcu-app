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
  // A control that is not there fails in seconds, not after the whole case's minute.
  // (set below in use)
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
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit', use: { ...devices['Desktop Safari'] } },
  ],
})
