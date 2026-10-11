import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), postForm: vi.fn(), patch: vi.fn(), download: vi.fn() }))
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ getToken: vi.fn() }) }))

import { ApiError } from "@/lib/api-client"
import { ReviewScreen } from "@/features/review/review-screen"

const item = (id: string, type: string, review_state: string, extra = {}) => ({
  id, meeting_id: "m1", type, content: `nd ${id}`, status: "final", supersedes: [], confidence: 0.9,
  flags: [], evidence: [], review_state, ...extra,
})
let items: unknown[]
let status: string
const meeting = () => ({
  id: "m1", title: "H", status,
  utterances: [
    { id: "u0001", seq: 1, speaker: "An", start: 0, end: null, text: "xin chào" },
    { id: "u0002", seq: 2, speaker: "Bình", start: 5, end: null, text: "ok" },
  ],
})

function renderIt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <ReviewScreen meetingId="m1" />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
  Object.values(api).forEach((f) => f.mockReset())
  status = "in_review"
  items = [
    item("a", "decision", "pending", { evidence: [{ utterance_id: "u0002", speaker: "Bình", ts: "00:00:05", quote: "trích dẫn ok" }] }),
    item("b", "decision", "approved"),
    item("c", "action_item", "approved"),
  ]
  api.get.mockImplementation(async (p: string) => (p.includes("/items") ? items : meeting()))
})
afterEach(cleanup)

test("tab labels show counts and publish disabled while pending", async () => {
  renderIt()
  expect(await screen.findByRole("tab", { name: "Quyết định (2)" })).toBeInTheDocument()
  expect(screen.getByRole("tab", { name: "Việc cần làm (1)" })).toBeInTheDocument()
  expect(screen.getByRole("tab", { name: "Diễn biến chủ đề" })).toBeInTheDocument()
  const pub = screen.getByRole("button", { name: "Phát hành" })
  expect(pub).toBeDisabled()
  expect(pub).toHaveAttribute("title", "Còn 1 mục chưa duyệt")
  expect(screen.getByText("Còn 1 mục chưa duyệt")).toBeInTheDocument()
})

test("publish enabled at zero pending", async () => {
  items = [item("b", "decision", "approved")]
  renderIt()
  await screen.findByRole("tab", { name: "Quyết định (1)" })
  expect(screen.getByRole("button", { name: "Phát hành" })).toBeEnabled()
})

test("evidence click highlights transcript row", async () => {
  const { container } = renderIt()
  fireEvent.click(await screen.findByText(/trích dẫn ok/))
  const row = container.querySelector("#utt-u0002")!
  expect(row.className).toContain("bg-yellow")
})

test("published meeting shows banner and no approve buttons", async () => {
  status = "published"
  renderIt()
  expect(await screen.findByText(/Cuộc họp đang ở trạng thái: Đã phát hành/)).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: "Duyệt" })).toBeNull()
})

test("clicking the same quote twice scrolls twice", async () => {
  renderIt()
  const spy = vi.fn()
  Element.prototype.scrollIntoView = spy
  const q = await screen.findByText(/trích dẫn ok/)
  fireEvent.click(q)
  fireEvent.click(q)
  expect(spy).toHaveBeenCalledTimes(2)
})

test("approve-clean shows count", async () => {
  api.post.mockResolvedValue({ approved: 3 })
  renderIt()
  fireEvent.click(await screen.findByRole("button", { name: "Chấp nhận mục sạch" }))
  expect(await screen.findByText("Đã duyệt 3 mục")).toBeInTheDocument()
})

test("publish 409 message is surfaced", async () => {
  items = [item("b", "decision", "approved")]
  api.post.mockRejectedValue(new ApiError(409, "pending_items", "Còn 2 mục chưa duyệt"))
  renderIt()
  await screen.findByRole("tab", { name: "Quyết định (1)" })
  fireEvent.click(screen.getByRole("button", { name: "Phát hành" }))
  expect(await screen.findByText("Còn 2 mục chưa duyệt")).toBeInTheDocument()
})

test("edit error is shown once (inline only), reject error in banner then cleared on success", async () => {
  api.patch.mockRejectedValueOnce(new ApiError(422, "reason_required", "Cần ghi lý do"))
  renderIt()
  const edit = (await screen.findAllByRole("button", { name: "Sửa" }))[0]
  fireEvent.click(edit)
  fireEvent.change(screen.getByLabelText("Nội dung"), { target: { value: "mới" } })
  fireEvent.change(screen.getByLabelText("Lý do"), { target: { value: "x" } })
  fireEvent.click(screen.getByRole("button", { name: "Lưu" }))
  expect(await screen.findByText("Cần ghi lý do")).toBeInTheDocument()
  expect(screen.getAllByText("Cần ghi lý do")).toHaveLength(1)

  fireEvent.click(screen.getByRole("button", { name: "Huỷ" }))
  api.patch.mockRejectedValueOnce(new ApiError(409, "not_in_review", "Cuộc họp không ở trạng thái duyệt"))
  fireEvent.click(screen.getAllByRole("button", { name: "Bác" })[0])
  expect(await screen.findByRole("alert")).toHaveTextContent("Cuộc họp không ở trạng thái duyệt")

  api.patch.mockResolvedValueOnce(item("a", "decision", "approved"))
  fireEvent.click(screen.getAllByRole("button", { name: "Duyệt" })[0])
  await vi.waitFor(() => expect(screen.queryByRole("alert")).toBeNull())
})

test("approve/reject disabled while that item's mutation is pending", async () => {
  let resolve: (v: unknown) => void = () => {}
  api.patch.mockReturnValue(new Promise((r) => (resolve = r)))
  renderIt()
  const approve = (await screen.findAllByRole("button", { name: "Duyệt" }))[0]
  fireEvent.click(approve)
  await vi.waitFor(() => expect(screen.getAllByRole("button", { name: "Duyệt" })[0]).toBeDisabled())
  expect(screen.getAllByRole("button", { name: "Bác" })[0]).toBeDisabled()
  expect(screen.getAllByRole("button", { name: "Duyệt" })[1]).toBeEnabled()
  resolve(item("a", "decision", "approved"))
})
