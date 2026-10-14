import { cleanup, fireEvent, render, screen, within } from "@testing-library/react"
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
import { MeetingList } from "@/features/meetings/meeting-list"

const m = (id: string, status: string, over: Record<string, unknown> = {}) => ({
  id, title: `Họp ${id}`, meeting_date: "2026-10-01", project: "Alpha", status,
  created_at: "2026-10-01T00:00:00Z", published_at: null, ...over,
})

function renderIt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MeetingList />
    </QueryClientProvider>,
  )
}

afterEach(cleanup)
beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  push.mockReset()
})

test("renders statuses and links", async () => {
  api.get.mockImplementation(async (path: string) => {
    if (path === "/meetings/a2") return { ...m("a2", "analyzing"), active_job_id: "j9", latest_job: null }
    if (path === "/meetings/f1")
      return {
        ...m("f1", "failed"),
        active_job_id: null,
        latest_job: { id: "j", kind: "analyze", meeting_id: "f1", status: "failed", step: "topics", progress: 0.5, error: "Hỏng rồi" },
      }
    if (path === "/jobs/j9")
      return { id: "j9", kind: "analyze", meeting_id: "a2", status: "running", step: "extract", progress: 0.1, error: null }
    return [m("r1", "in_review"), m("p1", "published"), m("a2", "analyzing"), m("f1", "failed")]
  })
  renderIt()
  expect(await screen.findByRole("link", { name: /Họp r1/ })).toHaveAttribute("href", "/meetings/r1/review")
  expect(screen.getByRole("link", { name: /Họp p1/ })).toHaveAttribute("href", "/meetings/p1/minutes")
  const list = within(screen.getByRole("list"))
  expect(list.getByText("Đang duyệt")).toBeInTheDocument()
  expect(list.getByText("Đã phát hành")).toBeInTheDocument()
  expect(await screen.findByText("Trích xuất hành vi")).toBeInTheDocument()
  expect(await screen.findByText("Hỏng rồi")).toBeInTheDocument()
  expect(screen.getAllByRole("button", { name: "Phân tích lại" })).toHaveLength(2)
})

test("empty state", async () => {
  api.get.mockResolvedValue([])
  renderIt()
  expect(await screen.findByText("Chưa có cuộc họp nào. Tải transcript đầu tiên lên nhé.")).toBeInTheDocument()
  expect(screen.getByRole("link", { name: "Tải transcript" })).toHaveAttribute("href", "/meetings/new")
})

test("inline succeeded job does not navigate", async () => {
  api.get.mockImplementation(async (path: string) => {
    if (path === "/meetings/a2") return { ...m("a2", "analyzing"), active_job_id: "j9", latest_job: null }
    if (path === "/jobs/j9")
      return { id: "j9", kind: "analyze", meeting_id: "a2", status: "succeeded", step: "done", progress: 1, error: null }
    return [m("a2", "analyzing")]
  })
  renderIt()
  expect(await screen.findByRole("link", { name: "Bắt đầu duyệt" })).toBeInTheDocument()
  expect(push).not.toHaveBeenCalled()
})

test("analyzing meeting offers reanalyze and shows backend 409 message", async () => {
  api.get.mockImplementation(async (path: string) => {
    if (path === "/meetings/a2") return { ...m("a2", "analyzing"), active_job_id: "j9", latest_job: null }
    if (path === "/jobs/j9")
      return { id: "j9", kind: "analyze", meeting_id: "a2", status: "running", step: "extract", progress: 0.1, error: null }
    return [m("a2", "analyzing")]
  })
  api.post.mockRejectedValue(new ApiError(409, "not_failed", "Phân tích vẫn đang chạy"))
  renderIt()
  const btn = await screen.findByRole("button", { name: "Phân tích lại" })
  fireEvent.click(btn)
  expect(await screen.findByText("Phân tích vẫn đang chạy")).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledWith("/meetings/a2/reanalyze")
})

test("project filter is debounced and keeps the previous list visible", async () => {
  api.get.mockImplementation(async (path: string) => {
    if (path.startsWith("/meetings?project=")) {
      await new Promise((r) => setTimeout(r, 200))
      return [m("n1", "published")]
    }
    return [m("r1", "in_review")]
  })
  renderIt()
  await screen.findByRole("link", { name: /Họp r1/ })
  fireEvent.change(screen.getByLabelText("Lọc theo dự án"), { target: { value: "Beta" } })
  await new Promise((r) => setTimeout(r, 100))
  expect(api.get.mock.calls.filter((c) => String(c[0]).includes("project="))).toHaveLength(0)
  await new Promise((r) => setTimeout(r, 300))
  expect(api.get).toHaveBeenCalledWith("/meetings?project=Beta")
  expect(screen.getByRole("link", { name: /Họp r1/ })).toBeInTheDocument()
  expect(await screen.findByRole("link", { name: /Họp n1/ })).toBeInTheDocument()
})
test("audio meetings: awaiting speakers links to naming page, transcribing shows its label", async () => {
  api.get.mockImplementation((path: string) => {
    if (path.startsWith("/meetings?") || path === "/meetings") {
      return Promise.resolve([m("s1", "awaiting_speakers"), m("t1", "transcribing")])
    }
    return Promise.resolve({ ...m("t1", "transcribing"), active_job_id: null, utterances: [], context: {} })
  })
  renderIt()
  const link = await screen.findByRole("link", { name: /Họp s1/ })
  expect(link).toHaveAttribute("href", "/meetings/s1/speakers")
  const list = within(screen.getByRole("list"))
  expect(list.getByText("Chờ gán người nói")).toBeInTheDocument()
  expect(list.getByText("Đang chuyển giọng nói")).toBeInTheDocument()
})
