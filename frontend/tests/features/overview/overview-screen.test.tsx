import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
const clerkUser = vi.hoisted(() => ({ firstName: null as string | null }))
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
vi.mock("@clerk/nextjs", () => ({ useUser: () => ({ user: clerkUser }), useAuth: () => ({ getToken: vi.fn() }) }))

import { OverviewScreen } from "@/features/overview/overview-screen"

const entry = (id: string, extra: Record<string, unknown> = {}) => ({
  item_id: id, meeting_id: "m1", meeting_title: "Họp thông báo", meeting_date: "2026-10-19",
  project: "Thông báo", type: "action_item", status: "final", content: `nd ${id}`, owner: null,
  due_date: null, due_state: null, condition: null, supersedes: [], hold: null,
  speaker: "Hằng", ts: "00:01:20", quote: "q", utterance_id: "u0004", ...extra,
})

const agenda = {
  project: null, projects: ["Thông báo"], generated_on: "2026-10-22",
  to_decide: [entry("q1", {
    type: "open_question", status: "open", content: "Ai làm dashboard?",
    hold: { reason: "declined", quote: "Em kín lịch rồi.", phrase: "kín lịch", speaker: "Quốc", ts: "00:03:05" },
  })],
  conditions: [entry("c1", { content: "Soạn mẫu tiếng Anh", condition: "pháp chế duyệt" })],
  due: [entry("d1", { content: "Dựng hàng đợi", owner: "Quốc", due_date: "2026-10-22", due_state: "today" })],
  markdown: "**📋 Chương trình họp kế tiếp**",
}
const tasks = (owner: string | null) => ({
  projects: ["Thông báo"], owners: ["Quốc", "Vân"],
  tasks: [
    entry("t1", { content: "Dựng hàng đợi", owner: "Quốc", due_date: "2026-10-20", due_state: "overdue" }),
    entry("t2", { content: "Soạn mẫu", owner: "Vân" }),
  ].filter((t) => !owner || t.owner === owner),
})
const decisions = {
  projects: ["Thông báo"],
  decisions: [
    entry("x1", { type: "decision", content: "Hàng đợi? → Redis Streams", supersedes: ["RabbitMQ"] }),
    entry("x2", { type: "decision", content: "Hàng đợi? → RabbitMQ", status: "superseded" }),
  ],
}

function renderIt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <OverviewScreen />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  clerkUser.firstName = null
  localStorage.clear()
  api.get.mockImplementation(async (p: string) => {
    if (p.startsWith("/overview/agenda")) return agenda
    if (p.startsWith("/overview/tasks")) return tasks(new URLSearchParams(p.split("?")[1]).get("owner"))
    return decisions
  })
})
afterEach(cleanup)

test("agenda shows the three parts, why items are open, and can be posted to Discord", async () => {
  api.post.mockResolvedValue({ sent: true })
  renderIt()
  expect(await screen.findByText("Ai làm dashboard?")).toBeInTheDocument()
  expect(screen.getByText("kín lịch").tagName).toBe("MARK")
  expect(screen.getByText("Điều kiện: pháp chế duyệt")).toBeInTheDocument()
  expect(screen.getByText(/Hôm nay · 22\/10\/2026/)).toBeInTheDocument()
  expect(screen.getAllByRole("link", { name: /Họp thông báo/ })[0]).toHaveAttribute(
    "href", "/meetings/m1/minutes?u=u0004",
  )
  fireEvent.click(screen.getByRole("button", { name: /Gửi lên Discord/ }))
  expect(await screen.findByText("Đã gửi chương trình họp lên Discord.")).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledWith("/overview/agenda/discord")
})

test("project filter reloads every view for that project", async () => {
  renderIt()
  const select = await screen.findByRole("combobox")
  fireEvent.change(select, { target: { value: "Thông báo" } })
  await waitFor(() =>
    expect(api.get).toHaveBeenCalledWith("/overview/agenda?project=Th%C3%B4ng+b%C3%A1o"),
  )
})

test("tasks: everyone by default, the account's first name is guessed, the choice is kept", async () => {
  clerkUser.firstName = "quốc"
  renderIt()
  fireEvent.click(await screen.findByRole("tab", { name: /Việc của tôi/ }))
  const who = await screen.findByRole("combobox", { name: /Tôi là/ })
  await waitFor(() => expect(who).toHaveValue("Quốc"))
  expect(await screen.findByText("Dựng hàng đợi")).toBeInTheDocument()
  expect(screen.queryByText("Soạn mẫu")).toBeNull()
  fireEvent.change(who, { target: { value: "" } })
  expect(await screen.findByText("Soạn mẫu")).toBeInTheDocument()
  expect(who).toHaveValue("")  // choosing everyone is not overridden by the guess
  expect(localStorage.getItem("meetmind.overview.owner")).toBe("*")
  fireEvent.change(who, { target: { value: "Vân" } })
  await waitFor(() => expect(localStorage.getItem("meetmind.overview.owner")).toBe("Vân"))
})

test("decision log strikes superseded decisions and can be searched", async () => {
  renderIt()
  fireEvent.click(await screen.findByRole("tab", { name: /Sổ quyết định/ }))
  const old = await screen.findByText("Hàng đợi? → RabbitMQ")
  expect(old.className).toContain("line-through")
  expect(screen.getByText(/Thay cho:/)).toBeInTheDocument()
  fireEvent.change(screen.getByRole("searchbox", { name: "Tìm quyết định" }), { target: { value: "redis" } })
  expect(screen.queryByText("Hàng đợi? → RabbitMQ")).toBeNull()
  expect(screen.getByText("Hàng đợi? → Redis Streams")).toBeInTheDocument()
})
