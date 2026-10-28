import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'tests/e2e',timeout:240000,workers:1,retries:0,
  reporter:[['list'],['json',{outputFile:'test-results/browser-results.json'}]],
  use:{channel:'chromium',baseURL:process.env.CLUETIDE_DEMO_URL||'http://127.0.0.1:8787',viewport:{width:1440,height:1000},
    video:'on',screenshot:'only-on-failure',trace:'retain-on-failure'}});
