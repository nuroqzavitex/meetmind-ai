import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), postForm: vi.fn(), patch: vi.fn(), download: vi.fn() }))
const search = vi.hoisted(() => ({ value: "" }))
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(search.value),
}))
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ getToken: vi.fn() }) }))
vi.mock("@/features/orgs/hooks", () => ({ useIsOrgAdmin: () => false }))

import { MinutesView } from "@/features/minutes/minutes-view"

const item = (id: string, type: string, review_state: string, extra = {}) => ({
  id, meeting_id: "m1", type, content: `nd ${id}`, status: "final", supersedes: [], confidence: 0.9,
  flags: [], evidence: [], review_state, ...extra,
})
let items: unknown[]
let status: string
const meeting = () => ({
  id: "m1", title: "Họp tuần", status, meeting_date: "2026-03-05", project: "Alpha",
  published_at: "2026-03-06T10:00:00Z",
  utterances: [
    { id: "u0001", seq: 1, speaker: "An", start: 0, end: null, text: "xin chào" },
    { id: "u0005", seq: 5, speaker: "Bình", start: 9, end: null, text: "đồng ý" },
  ],
})

function renderIt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MinutesView meetingId="m1" />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
  Object.values(api).forEach((f) => f.mockReset())
  search.value = ""
  status = "published"
  items = [
    item("a", "action_item", "approved"),
    item("b", "decision", "edited"),
    item("c", "decision", "pending"),
    item("d", "decision", "rejected"),
    item("e", "decision", "approved", { status: "superseded" }),
  ]
  api.get.mockImplementation(async (p: string) => (p.includes("/items") ? items : meeting()))
})
afterEach(cleanup)

test("renders only approved/edited non-superseded items under ordered headings", async () => {
  renderIt()
  expect(await screen.findByText("nd a")).toBeInTheDocument()
  expect(screen.getByText("nd b")).toBeInTheDocument()
  for (const t of ["nd c", "nd d", "nd e"]) expect(screen.queryByText(t)).toBeNull()
  const heads = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent)
  expect(heads).toEqual(["Quyết định", "Việc cần làm"])
  expect(screen.getByText("Họp tuần")).toBeInTheDocument()
  expect(screen.getByText(/05\/03\/2026/)).toBeInTheDocument()
  expect(screen.getByText(/Phát hành: 06\/03\/2026/)).toBeInTheDocument()
  expect(screen.getAllByRole("button", { name: "Báo sai" })).toHaveLength(2)
})

test("download buttons call download with format", async () => {
  api.download.mockResolvedValue(undefined)
  renderIt()
  fireEvent.click(await screen.findByRole("button", { name: "Tải .md" }))
  expect(api.download).toHaveBeenCalledWith("/meetings/m1/export?format=md", "bien-ban.md")
  fireEvent.click(screen.getByRole("button", { name: "Tải .json" }))
  expect(api.download).toHaveBeenCalledWith("/meetings/m1/export?format=json", "bien-ban.json")
})

test("?u= opens transcript and scrolls to utterance", async () => {
  search.value = "u=u0005"
  const { container } = renderIt()
  await screen.findByText("nd a")
  expect(await screen.findByRole("button", { name: "Ẩn transcript" })).toBeInTheDocument()
  expect(container.querySelector("#utt-u0005")).not.toBeNull()
  expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
})

test("transcript hidden by default and toggles", async () => {
  const { container } = renderIt()
  fireEvent.click(await screen.findByRole("button", { name: "Xem transcript" }))
  expect(container.querySelector("#utt-u0001")).not.toBeNull()
})

test("non-published meeting shows banner with review link", async () => {
  status = "in_review"
  renderIt()
  expect(await screen.findByText("Biên bản đang được chỉnh sửa lại")).toBeInTheDocument()
  expect(screen.getByRole("link", { name: /duyệt/i })).toHaveAttribute("href", "/meetings/m1/review")
})

test("report/reopen hidden when not published", async () => {
  status = "in_review"
  renderIt()
  await screen.findByText("nd a")
  expect(screen.queryByRole("button", { name: "Báo sai" })).toBeNull()
  expect(screen.queryByRole("button", { name: "Mở lại" })).toBeNull()
})
