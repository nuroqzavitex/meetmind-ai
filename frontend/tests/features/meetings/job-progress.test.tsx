import { act, cleanup, render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  postForm: vi.fn(),
  patch: vi.fn(),
  download: vi.fn(),
}))
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
const push = vi.hoisted(() => vi.fn())
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }))

import { ApiError } from "@/lib/api-client"
import { JobProgress } from "@/features/meetings/job-progress"

const job = (over: Record<string, unknown>) => ({
  id: "j1", kind: "analyze", meeting_id: "m1", status: "running", step: "topics", progress: 0.6, error: null, ...over,
})

function renderIt(autoNavigate = true) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <JobProgress jobId="j1" meetingId="m1" autoNavigate={autoNavigate} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true })
  Object.values(api).forEach((f) => f.mockReset())
  push.mockReset()
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

test("running then succeeded stops polling", async () => {
  api.get.mockResolvedValueOnce(job({}))
  api.get.mockResolvedValue(job({ status: "succeeded", step: "done", progress: 1 }))
  renderIt()
  expect(await screen.findByText("Gom chủ đề")).toBeInTheDocument()
  expect(screen.getByText("60%")).toBeInTheDocument()
  await act(async () => {
    await vi.advanceTimersByTimeAsync(1500)
  })
  const link = await screen.findByRole("link", { name: "Bắt đầu duyệt" })
  expect(link).toHaveAttribute("href", "/meetings/m1/review")
  expect(push).toHaveBeenCalledWith("/meetings/m1/review")
  const n = api.get.mock.calls.length
  await act(async () => {
    await vi.advanceTimersByTimeAsync(5000)
  })
  expect(api.get.mock.calls.length).toBe(n)
})

test("failed shows error and reanalyze polls new job", async () => {
  api.get.mockImplementation(async (path: string) =>
    path === "/jobs/j2"
      ? job({ id: "j2", step: "extract", progress: 0.2 })
      : job({ status: "failed", error: "Lỗi mô hình" }),
  )
  api.post.mockResolvedValue({ meeting_id: "m1", job_id: "j2" })
  renderIt()
  expect(await screen.findByText("Lỗi mô hình")).toBeInTheDocument()
  expect(screen.getByText(/Gom chủ đề/)).toBeInTheDocument()
  const btn = screen.getByRole("button", { name: "Phân tích lại" })
  await act(async () => {
    btn.click()
  })
  expect(api.post).toHaveBeenCalledWith("/meetings/m1/reanalyze")
  expect(await screen.findByText("Trích xuất hành vi")).toBeInTheDocument()
  expect(api.get).toHaveBeenCalledWith("/jobs/j2")
})

test("no auto-navigation when autoNavigate is false", async () => {
  api.get.mockResolvedValue(job({ status: "succeeded", step: "done", progress: 1 }))
  renderIt(false)
  expect(await screen.findByRole("link", { name: "Bắt đầu duyệt" })).toBeInTheDocument()
  expect(push).not.toHaveBeenCalled()
})

test("failed first fetch shows error with retry", async () => {
  api.get.mockRejectedValueOnce(new ApiError(503, "queue_unavailable", "Dịch vụ tạm thời không khả dụng"))
  api.get.mockResolvedValue(job({}))
  renderIt()
  expect(await screen.findByText("Dịch vụ tạm thời không khả dụng")).toBeInTheDocument()
  expect(screen.queryByText(/Đang tải tiến độ/)).toBeNull()
  await act(async () => {
    screen.getByRole("button", { name: "Thử lại" }).click()
  })
  expect(await screen.findByText("Gom chủ đề")).toBeInTheDocument()
})

test("progressbar has label and values", async () => {
  api.get.mockResolvedValue(job({}))
  renderIt()
  const bar = await screen.findByRole("progressbar", { name: "Tiến độ phân tích" })
  expect(bar).toHaveAttribute("aria-valuenow", "60")
  expect(bar).toHaveAttribute("aria-valuemin", "0")
  expect(bar).toHaveAttribute("aria-valuemax", "100")
})

test("success invalidates items and topics", async () => {
  api.get.mockResolvedValue(job({ status: "succeeded", step: "done", progress: 1 }))
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const spy = vi.spyOn(qc, "invalidateQueries")
  render(
    <QueryClientProvider client={qc}>
      <JobProgress jobId="j1" meetingId="m1" />
    </QueryClientProvider>,
  )
  await screen.findByRole("link", { name: "Bắt đầu duyệt" })
  const keys = spy.mock.calls.map((c) => JSON.stringify(c[0]?.queryKey))
  expect(keys).toContain('["items","m1"]')
  expect(keys).toContain('["topics","m1"]')
})

test("finished transcription links to speaker naming and auto-navigates there", async () => {
  api.get.mockResolvedValue(job({ kind: "transcribe", status: "succeeded", step: "done", progress: 1 }))
  renderIt()
  const link = await screen.findByRole("link", { name: "Gán tên người nói" })
  expect(link).toHaveAttribute("href", "/meetings/m1/speakers")
  expect(screen.getByText("Đã chuyển giọng nói thành văn bản")).toBeInTheDocument()
  expect(push).toHaveBeenCalledWith("/meetings/m1/speakers")
})
