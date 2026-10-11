import { expect, test, vi } from "vitest"

vi.mock("@clerk/nextjs/server", () => ({
  clerkMiddleware: (fn: unknown) => fn,
  createRouteMatcher: () => () => false,
}))
vi.mock("next/server", () => ({ NextResponse: {} }))

import { config } from "@/middleware"

const re = new RegExp(`^${config.matcher[0]}$`)

test("matcher covers app routes", () => {
  for (const p of ["/", "/meetings/new", "/meetings/abc/review", "/xdocs", "/meetings/apng", "/select-org"])
    expect(re.test(p), p).toBe(true)
})

test("matcher skips static files", () => {
  for (const p of ["/favicon.ico", "/_next/static/x.js"]) expect(re.test(p), p).toBe(false)
})
