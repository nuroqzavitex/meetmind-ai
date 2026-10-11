import path from "node:path"

import { defineConfig, devices } from "@playwright/test"

import { loadEnvFiles, missingClerkEnv, skipReason } from "../tests/e2e/env"

// Real env vars win; then frontend/.env.local; then the repo-root .env. Blank values are ignored.
loadEnvFiles([path.resolve(__dirname, ".env.local"), path.resolve(__dirname, "../.env")])

const CI = !!process.env.CI
const backendDir = path.resolve(__dirname, "../backend")
// Absolute, so it does not depend on the backend's cwd and overrides an empty FAKE_LLM_DIR in .env.
const backendEnv = {
  LLM_PROVIDER: "fake",
  EMBEDDING_PROVIDER: "hash",
  FAKE_LLM_DIR: path.resolve(__dirname, "../tests/fixtures/llm/payment_v2"),
}

const skipped = missingClerkEnv().length > 0
if (skipped) console.warn(skipReason())

export default defineConfig({
  testDir: "../tests/e2e",
  globalSetup: "../tests/e2e/global.setup.ts",
  fullyParallel: false,
  workers: 1,
  retries: CI ? 1 : 0,
  timeout: 180_000,
  forbidOnly: CI,
  reporter: CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  // Without Clerk env the suite is skipped, so do not start the stack at all.
  webServer: skipped
    ? undefined
    : [
        {
          name: "backend",
          command: "uv run uvicorn app.main:app --port 8000",
          cwd: backendDir,
          url: "http://localhost:8000/api/v1/health",
          env: backendEnv,
          reuseExistingServer: !CI,
          timeout: 120_000,
        },
        {
          name: "worker",
          command: "uv run arq app.workers.main.WorkerSettings",
          cwd: backendDir,
          // arq logs "Starting worker for N functions" to stderr.
          wait: { stderr: /Starting worker/ },
          env: backendEnv,
          reuseExistingServer: !CI,
          timeout: 120_000,
        },
        {
          name: "frontend",
          command: CI ? "npm run build && npm run start" : "npm run dev",
          url: "http://localhost:3000",
          env: { NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000" },
          reuseExistingServer: !CI,
          timeout: 240_000,
        },
      ],
})
