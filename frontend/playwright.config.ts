import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 45_000,
  use: { baseURL: 'http://127.0.0.1:5173', trace: 'retain-on-failure', screenshot: 'only-on-failure', launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] } },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 1080 } } }],
  webServer: { command: 'npm run dev -- --port 5173', url: 'http://127.0.0.1:5173', reuseExistingServer: !process.env.CI },
})
