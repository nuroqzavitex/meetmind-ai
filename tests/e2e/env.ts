import { existsSync, readFileSync } from "node:fs"

/** Env vars without which the e2e suite cannot sign in, so it is skipped. */
export const REQUIRED_CLERK_ENV = ["CLERK_SECRET_KEY", "E2E_CLERK_USER_USERNAME"] as const

export function missingClerkEnv(): string[] {
  return REQUIRED_CLERK_ENV.filter((name) => !process.env[name])
}

export function skipReason(): string {
  return (
    `E2E skipped: missing ${missingClerkEnv().join(", ")}. ` +
    "See tests/e2e/README.md for the Clerk test user and env setup."
  )
}

/**
 * Loads `KEY=VALUE` lines from the given files, earlier files first. A variable is only set while it is
 * unset or blank, so a real env var wins, and a blank `E2E_*=` in one file does not hide the value in
 * a later one (unlike `process.loadEnvFile`).
 */
export function loadEnvFiles(files: string[]): void {
  for (const file of files) {
    if (!existsSync(file)) continue
    for (const raw of readFileSync(file, "utf8").split(/\r?\n/)) {
      const match = /^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$/.exec(raw)
      if (!match) continue
      const [, key, rawValue] = match
      const quoted = /^(["'])(.*?)\1(?:\s+#.*)?$/.exec(rawValue)
      const value = quoted ? quoted[2] : rawValue.replace(/\s+#.*$/, "")
      if (value && !process.env[key]) process.env[key] = value
    }
  }
}
