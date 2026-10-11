import { renderHook } from "@testing-library/react"
import { beforeEach, expect, test, vi } from "vitest"

const getToken = vi.hoisted(() => vi.fn(async () => "tok"))
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ getToken }) }))

const apiFetch = vi.hoisted(() => vi.fn(async () => ({ ok: true })))
const apiDownload = vi.hoisted(() =>
  vi.fn(async () => ({ blob: new Blob(["x"]), filename: "bien-ban.md" })),
)
vi.mock("@/lib/api-client", () => ({ apiFetch, apiDownload }))

import { useApi } from "@/lib/use-api"

beforeEach(() => {
  apiFetch.mockClear()
})

test("get passes token getter to apiFetch", async () => {
  const { result } = renderHook(() => useApi())
  await result.current.get("/meetings")
  expect(apiFetch).toHaveBeenCalledTimes(1)
  const [path, opts] = apiFetch.mock.calls[0] as unknown as [
    string,
    { getToken: () => Promise<string | null> },
  ]
  expect(path).toBe("/meetings")
  expect(await opts.getToken()).toBe("tok")
})

test("post/patch/postForm forward bodies", async () => {
  const { result } = renderHook(() => useApi())
  await result.current.post("/a", { x: 1 })
  await result.current.patch("/b", { y: 2 })
  const form = new FormData()
  await result.current.postForm("/c", form)
  const calls = apiFetch.mock.calls as unknown as [string, Record<string, unknown>][]
  expect(calls[0][1]).toMatchObject({ method: "POST", json: { x: 1 } })
  expect(calls[1][1]).toMatchObject({ method: "PATCH", json: { y: 2 } })
  expect(calls[2][1]).toMatchObject({ method: "POST", form })
})

test("download creates object URL and clicks link with filename", async () => {
  URL.createObjectURL = vi.fn(() => "blob:x")
  URL.revokeObjectURL = vi.fn()
  const click = vi
    .spyOn(HTMLAnchorElement.prototype, "click")
    .mockImplementation(() => {})
  const { result } = renderHook(() => useApi())
  await result.current.download("/meetings/1/export")
  expect(URL.createObjectURL).toHaveBeenCalled()
  expect(click).toHaveBeenCalledTimes(1)
  const a = click.mock.contexts[0] as HTMLAnchorElement
  expect(a.download).toBe("bien-ban.md")
  expect(a.href).toContain("blob:x")
})

test("download forwards fallback name", async () => {
  URL.createObjectURL = vi.fn(() => "blob:x")
  URL.revokeObjectURL = vi.fn()
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {})
  apiDownload.mockClear()
  const { result } = renderHook(() => useApi())
  await result.current.download("/p", "bien-ban.json")
  expect((apiDownload.mock.calls[0] as unknown[])[2]).toBe("bien-ban.json")
})
