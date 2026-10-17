import {defineConfig,devices} from '@playwright/test';
const port=5185;
export default defineConfig({testDir:'./e2e',fullyParallel:false,reporter:[['list']],use:{baseURL:`http://127.0.0.1:${port}`,trace:'retain-on-failure',screenshot:'only-on-failure',video:'retain-on-failure'},projects:[{name:'chromium',use:{...devices['Desktop Chrome']}}],webServer:{command:'npm run dev',url:`http://127.0.0.1:${port}`,reuseExistingServer:false,timeout:120000,env:{VITE_DEMO_URL:'https://witness-fleet-guglxni.eastus.cloudapp.azure.com/demo',VITE_GITHUB_URL:'https://github.com/guglxni/witness-fleet'}}});
