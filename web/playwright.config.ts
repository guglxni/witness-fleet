import { defineConfig } from '@playwright/test';

const webPort=process.env.WITNESS_E2E_PORT||'5173';
const apiPort=process.env.WITNESS_E2E_API_PORT||'8090';
export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  fullyParallel: true,
  reporter: process.env.CI ? 'line' : 'list',
  outputDir: process.env.PW_OUTPUT_DIR || 'test-results',
  use: { baseURL: `http://127.0.0.1:${webPort}`, trace: 'retain-on-failure' },
  webServer: [
    {command:`../.venv/bin/python -m uvicorn witness_fleet.api.app:create_app --factory --host 127.0.0.1 --port ${apiPort}`,url:`http://127.0.0.1:${apiPort}/api/health`,reuseExistingServer:!process.env.CI,timeout:90000},
    {command:`npm run dev -- --port ${webPort}`,url:`http://127.0.0.1:${webPort}`,env:{WITNESS_E2E_API_PORT:apiPort},reuseExistingServer:!process.env.CI,timeout:60000},
  ],
  projects: [
    { name: 'desktop', use: { viewport: { width: 1440, height: 900 } } },
    { name: 'mobile', use: { viewport: { width: 390, height: 844 }, isMobile: true } },
  ],
});
