import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './tests/template-preview',
  testMatch: '**/*.e2e.ts',
  outputDir: '../output/template-browser/results',
  reporter: [['list'], ['json', { outputFile: '../output/template-browser/report.json' }]],
  timeout: 25_000, workers: 1, retries: 0,
  use: { ...devices['Desktop Chrome'], channel: process.env.FLAMA_BROWSER_CHANNEL,
    screenshot: 'only-on-failure', trace: 'retain-on-failure' },
})
