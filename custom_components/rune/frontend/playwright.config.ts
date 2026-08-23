import { defineConfig, devices } from "@playwright/test";

const PORT = 5180;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? "list" : "list",

  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    actionTimeout: 5_000,
    navigationTimeout: 10_000,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    // Build first (produces ``dist/panel.html`` + ``dist/panel.js``),
    // then copy the mock host fixture next to them, then start a
    // static preview server bound to 127.0.0.1. The iframe tests
    // navigate to ``/host.html`` which embeds ``/panel.html`` and
    // fakes the HA postMessage bridge.
    command: `pnpm exec vite build --config vite.spa.config.ts && pnpm exec vite build --config vite.shim.config.ts && cp tests/e2e/fixtures/host.html dist/host.html && pnpm exec vite preview --port ${PORT} --host 127.0.0.1 --strictPort`,
    url: `http://127.0.0.1:${PORT}/panel.html`,
    reuseExistingServer: !process.env.CI,
    stdout: "pipe",
    stderr: "pipe",
    timeout: 60_000,
  },
});
