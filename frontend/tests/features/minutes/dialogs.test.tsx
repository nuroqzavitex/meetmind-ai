import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), postForm: vi.fn(), patch: vi.fn(), download: vi.fn() }))
const push = vi.hoisted(() => vi.fn())
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }))
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ getToken: vi.fn() }) }))

import { ReopenDialog } from "@/features/minutes/reopen-dialog"
import { ReportDialog } from "@/features/minutes/report-dialog"

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>)
}

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  push.mockReset()
})
afterEach(cleanup)

test("report: empty text cannot submit; text posts reason and shows success", async () => {
  api.post.mockResolvedValue(undefined)
  wrap(<ReportDialog itemId="i1" />)
  fireEvent.click(screen.getByRole("button", { name: "Báo sai" }))
  const submit = await screen.findByRole("button", { name: "Gửi báo sai" })
  expect(submit).toBeDisabled()
  fireEvent.change(screen.getByLabelText("Mô tả chỗ sai"), { target: { value: "Sai tên người" } })
  expect(submit).toBeEnabled()
  fireEvent.click(submit)
  expect(await screen.findByText("Đã ghi nhận báo sai")).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledWith("/items/i1/report", { reason: "Sai tên người" })
})

test("reopen posts and navigates to review", async () => {
  api.post.mockResolvedValue({ id: "i1" })
  wrap(<ReopenDialog itemId="i1" meetingId="m1" />)
  fireEvent.click(screen.getByRole("button", { name: "Mở lại" }))
  expect(await screen.findByText(/Cuộc họp sẽ quay về trạng thái đang duyệt/)).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText("Lý do (không bắt buộc)"), { target: { value: "cần sửa" } })
  fireEvent.click(screen.getByRole("button", { name: "Mở lại để sửa" }))
  await waitFor(() => expect(push).toHaveBeenCalledWith("/meetings/m1/review"))
  expect(api.post).toHaveBeenCalledWith("/items/i1/reopen", { reason: "cần sửa" })
})
