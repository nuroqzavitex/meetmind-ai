import { cleanup, render, screen, waitFor } from "@testing-library/react"
import { useQuery } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

const auth = vi.hoisted(() => ({
  orgId: "org_a" as string | null | undefined,
  getToken: async () => "t",
}))
vi.mock("@clerk/nextjs", () => ({ useAuth: () => auth }))

import { Providers } from "@/app/providers"

const fn = vi.fn()

function Child() {
  const q = useQuery({
    queryKey: ["meetings", {}],
    queryFn: async () => fn(),
  })
  if (q.isPending) return <div>loading</div>
  return <div>data:{q.data}</div>
}

afterEach(cleanup)

beforeEach(() => {
  fn.mockReset()
  auth.orgId = "org_a"
})

test("test_org_switch_clears_cache", async () => {
  fn.mockResolvedValueOnce("A").mockResolvedValueOnce("B")
  const ui = () => (
    <Providers>
      <Child />
    </Providers>
  )
  const { rerender } = render(ui())
  await screen.findByText("data:A")

  auth.orgId = "org_b"
  rerender(ui())
  expect(screen.queryByText("data:A")).toBeNull()
  expect(screen.getByText("loading")).toBeTruthy()
  await screen.findByText("data:B")
  expect(fn).toHaveBeenCalledTimes(2)
})

test("same org rerender does not refetch", async () => {
  fn.mockResolvedValue("A")
  const ui = () => (
    <Providers>
      <Child />
    </Providers>
  )
  const { rerender } = render(ui())
  await screen.findByText("data:A")
  rerender(ui())
  await waitFor(() => expect(screen.getByText("data:A")).toBeTruthy())
  expect(fn).toHaveBeenCalledTimes(1)
})

test("sign-out clears cache and hides old data", async () => {
  fn.mockResolvedValueOnce("A").mockResolvedValueOnce("B")
  const ui = () => (
    <Providers>
      <Child />
    </Providers>
  )
  const { rerender } = render(ui())
  await screen.findByText("data:A")
  auth.orgId = null
  rerender(ui())
  expect(screen.queryByText("data:A")).toBeNull()
  expect(screen.getByText("loading")).toBeTruthy()
  await screen.findByText("data:B")
})

test("first mount with undefined then org does not clear or refetch", async () => {
  fn.mockResolvedValue("A")
  auth.orgId = undefined
  const ui = () => (
    <Providers>
      <Child />
    </Providers>
  )
  const { rerender } = render(ui())
  await screen.findByText("data:A")
  auth.orgId = "org_a"
  rerender(ui())
  await screen.findByText("data:A")
  expect(fn).toHaveBeenCalledTimes(1)
})
