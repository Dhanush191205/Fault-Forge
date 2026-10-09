import { defineConfig } from '@playwright/test';

/** Test the running local stack in one worker; environment chooses installed Edge or CI Chromium. */
export default defineConfig({
  testDir: './tests', fullyParallel: false, workers: 1, timeout: 60000,
  expect: {timeout: 10000}, reporter: [['list'], ['html', {open: 'never'}]],
  use: {baseURL: 'http://localhost:5173', channel: process.env.CI ? undefined : 'msedge',
    viewport: {width: 1440, height: 1000}, screenshot: 'only-on-failure', trace: 'retain-on-failure'},
});
