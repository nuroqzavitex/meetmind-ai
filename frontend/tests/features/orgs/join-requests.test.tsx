import { cleanup, render, screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

import { ApiError } from "@/lib/api-client"

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), del: vi.fn() }))
const clerk = vi.hoisted(() => ({ role: "org:admin" as string | undefined, setActive: vi.fn() }))
const push = vi.hoisted(() => vi.fn())
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
vi.mock("@clerk/nextjs", () => ({
  useOrganization: () => ({ membership: clerk.role ? { role: clerk.role } : null }),
  useOrganizationList: () => ({ setActive: clerk.setActive }),
}))
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }))

import { JoinByCode } from "@/features/orgs/join-by-code"
import { JoinRequestsBell } from "@/features/orgs/join-requests-bell"
import { JoinSettings } from "@/features/orgs/join-settings"

const REQ = {
  id: "r1", org_id: "org_a", org_name: "Team A", user_name: "Minh Trần", user_email: "minh@example.com",
  status: "pending", created_at: "2026-10-14T08:00:00Z", decided_at: null,
}

function renderIt(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

afterEach(cleanup)
beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  clerk.role = "org:admin"
  clerk.setActive.mockReset()
  push.mockReset()
})

test("sends a join request with the typed code and lists it as pending", async () => {
  api.get.mockResolvedValueOnce([]).mockResolvedValue([REQ])
  api.post.mockResolvedValue(REQ)
  renderIt(<JoinByCode />)
  await userEvent.type(screen.getByLabelText("Mã tham gia"), " mm-7k3q-x9p2 ")
  await userEvent.click(screen.getByRole("button", { name: "Gửi yêu cầu" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/join-requests", { code: "mm-7k3q-x9p2" }))
  expect(await screen.findByText("Đang chờ duyệt")).toBeInTheDocument()
  expect(screen.getByText("Team A")).toBeInTheDocument()
})

test("shows the server error for a wrong code", async () => {
  api.get.mockResolvedValue([])
  api.post.mockRejectedValue(new ApiError(404, "invalid_code", "Mã tham gia không đúng hoặc đã được đổi"))
  renderIt(<JoinByCode />)
  await userEvent.type(screen.getByLabelText("Mã tham gia"), "MM-AAAA-BBBB")
  await userEvent.click(screen.getByRole("button", { name: "Gửi yêu cầu" }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Mã tham gia không đúng")
})

test("approved request enters the organization", async () => {
  api.get.mockResolvedValue([{ ...REQ, status: "approved" }])
  clerk.setActive.mockResolvedValue(undefined)
  renderIt(<JoinByCode />)
  await userEvent.click(await screen.findByRole("button", { name: "Vào tổ chức" }))
  await waitFor(() => expect(clerk.setActive).toHaveBeenCalledWith({ organization: "org_a" }))
  expect(push).toHaveBeenCalledWith("/")
})

test("pending request can be cancelled", async () => {
  api.get.mockResolvedValue([REQ])
  api.del.mockResolvedValue(undefined)
  renderIt(<JoinByCode />)
  await userEvent.click(await screen.findByRole("button", { name: "Huỷ" }))
  await waitFor(() => expect(api.del).toHaveBeenCalledWith("/join-requests/r1"))
})

test("admin sees the join code and approves a request", async () => {
  api.get.mockImplementation((path: string) =>
    Promise.resolve(path === "/settings/join-code" ? { code: "MM-7K3Q-X9P2" } : [REQ]),
  )
  api.post.mockResolvedValue({ ...REQ, status: "approved" })
  renderIt(<JoinSettings />)
  expect(await screen.findByTestId("join-code")).toHaveTextContent("MM-7K3Q-X9P2")
  const row = (await screen.findByText("Minh Trần")).closest("li")!
  expect(within(row).getByText(/minh@example.com · 14\/10\/2026/)).toBeInTheDocument()
  await userEvent.click(within(row).getByRole("button", { name: "Đồng ý Minh Trần" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/join-requests/r1/approve"))
})

test("admin rotates the code", async () => {
  api.get.mockImplementation((path: string) =>
    Promise.resolve(path === "/settings/join-code" ? { code: "MM-7K3Q-X9P2" } : []),
  )
  api.post.mockResolvedValue({ code: "MM-AAAA-BBBB" })
  renderIt(<JoinSettings />)
  await userEvent.click(await screen.findByRole("button", { name: /Đổi mã/ }))
  expect(await screen.findByText("MM-AAAA-BBBB")).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledWith("/settings/join-code/rotate")
})

test("members see neither the join settings nor the bell", async () => {
  clerk.role = "org:member"
  const { container } = renderIt(
    <>
      <JoinSettings />
      <JoinRequestsBell />
    </>,
  )
  expect(container).toBeEmptyDOMElement()
  expect(api.get).not.toHaveBeenCalled()
})

test("bell shows the number of pending requests for admins", async () => {
  api.get.mockResolvedValue([REQ, { ...REQ, id: "r2" }])
  renderIt(<JoinRequestsBell />)
  const link = await screen.findByRole("link", { name: "2 yêu cầu tham gia đang chờ duyệt" })
  expect(link).toHaveAttribute("href", "/settings#join-requests")
  expect(within(link).getByText("2")).toBeInTheDocument()
})
