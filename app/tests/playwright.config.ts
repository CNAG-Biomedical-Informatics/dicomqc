import {defineConfig} from '@playwright/test';

export default defineConfig({
  testDir: '.', testMatch: '*.spec.ts', outputDir: '../test-results',
  use: {headless: true, launchOptions: process.env.CHROMIUM_PATH ? {executablePath: process.env.CHROMIUM_PATH} : {}},
});
