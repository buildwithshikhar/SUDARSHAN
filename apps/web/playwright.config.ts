import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  // The signed-in tests share three seeded accounts and their saved preferences, so they run in order.
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:8080',
    trace: 'retain-on-failure',
    // The interface switches animation off for reduced motion; tests run that way so axe never
    // measures a colour in the middle of a transition.
    reducedMotion: 'reduce',
  },
  snapshotPathTemplate: '{testDir}/__screenshots__/{platform}/{arg}{ext}',
  projects: [
    { name: 'chromium', grepInvert: /@visual/, use: { ...devices['Desktop Chrome'] } },
    { name: 'visual', grep: /@visual/, workers: 1, use: { ...devices['Desktop Chrome'] } },
  ],
})
