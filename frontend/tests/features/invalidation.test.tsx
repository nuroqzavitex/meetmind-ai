import { renderHook, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { expect, test, vi } from "vitest"

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), postForm: vi.fn(), patch: vi.fn(), download: vi.fn() }))
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }))

import { usePublish } from "@/features/review/hooks"
import { useReopenItem } from "@/features/minutes/hooks"

function setup() {
  const qc = new QueryClient()
  const spy = vi.spyOn(qc, "invalidateQueries")
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  )
  return { spy, wrapper }
}
const keys = (spy: ReturnType<typeof setup>["spy"]) => spy.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey))

test("publish invalidates meetings list", async () => {
  api.post.mockResolvedValue({})
  const { spy, wrapper } = setup()
  const { result } = renderHook(() => usePublish("m1"), { wrapper })
  result.current.mutate()
  await waitFor(() => expect(keys(spy)).toContain('["meetings"]'))
  expect(keys(spy)).toContain('["meeting","m1"]')
})

test("reopen invalidates meetings list", async () => {
  api.post.mockResolvedValue({})
  const { spy, wrapper } = setup()
  const { result } = renderHook(() => useReopenItem("m1"), { wrapper })
  result.current.mutate({ id: "i1" })
  await waitFor(() => expect(keys(spy)).toContain('["meetings"]'))
})
