import { defineConfig } from '@playwright/test';

/**
 * Epic 9A T219-T221 — real-browser E2E verification of the Platform
 * Admin surface against the actual running Docker Compose stack
 * (erp-system-web-1:3000, erp-system-api-1:8000). No mocked network
 * layer: every request in these specs is a genuine browser request
 * against the real frontend hitting the real backend/Postgres.
 */
export default defineConfig({
  testDir: './e2e',
  // Generous timeouts: this suite runs against a dev-mode (Turbopack,
  // hot-reload) Next.js server on a Windows-drive-backed WSL2 filesystem
  // (see AGENTS.md/CLAUDE.md environment notes) — first-visit route
  // compiles and multi-context tests (two simultaneous browser sessions)
  // are measurably slower here than in a built/production or native-fs
  // environment. Every underlying assertion is unchanged; this only
  // gives real, in-flight work enough time to finish.
  timeout: 180_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list'], ['json', { outputFile: 'e2e-results.json' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});
