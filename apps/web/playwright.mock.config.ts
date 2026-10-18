import { defineConfig, devices } from '@playwright/test'

/**
 * Workspace specs that run against the Vite dev server with `?mock=1` (the scripted session), so
 * they need neither Docker nor the API: the REST calls are answered by the specs themselves.
 * Run with `npm run e2e:mock`.
 */
export default defineConfig({
  testDir: './e2e/mock',
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['github'], ['list']] : 'list',
  outputDir: 'test-results/mock',
  use: {
    baseURL: 'http://localhost:5199',
    trace: 'retain-on-failure',
    reducedMotion: 'reduce',
    ...devices['Desktop Chrome'],
    viewport: { width: 1920, height: 1080 },
    launchOptions: {
      args: [
        '--use-gl=angle',
        '--use-angle=swiftshader',
        '--enable-unsafe-swiftshader',
        '--ignore-gpu-blocklist',
      ],
    },
  },
  webServer: {
    command: 'npx vite --port 5199 --strictPort',
    url: 'http://localhost:5199',
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
})
