import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e', fullyParallel: false, reporter: [['list']],
  use: { baseURL: 'http://127.0.0.1:5195', trace: 'retain-on-failure' },
  projects: [{ name: 'chromium' }],
  webServer: { command: 'npm run dev -- --host 127.0.0.1 --port 5195', url: 'http://127.0.0.1:5195/demo/', reuseExistingServer: !process.env.CI, timeout: 120_000 },
});
