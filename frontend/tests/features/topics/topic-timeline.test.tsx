import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

const api = vi.hoisted(() => ({ get: vi.fn() }))
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))

import { TopicTimeline } from "@/features/topics/topic-timeline"

const act = (id: string, utterance_id: string, start: number, a: string) => ({
  id, utterance_id, start, act: a, seq: 1, speaker: "An", quote: "q",
})
const topic = (extra = {}) => ({
  topic_id: "t1", question: "Chọn cơ sở dữ liệu nào?", deferred: false, ambiguous_decides: [],
  needs_confirmation: false,
  options: {
    Postgres: {
      label: "Postgres", state: "decided", superseded_by: null, decided_act: null,
      acts: [act("a1", "u0003", 210, "decide")],
      history: [[135, "propose", "proposed"], [210, "decide", "decided"]],
    },
    MongoDB: {
      label: "MongoDB", state: "superseded", superseded_by: "Postgres", decided_act: null,
      acts: [], history: [[20, "propose", "proposed"], [210, "decide", "superseded"]],
    },
  },
  ...extra,
})

function renderIt(onSeek?: (id: string) => void) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <TopicTimeline meetingId="m1" onSeek={onSeek} />
    </QueryClientProvider>,
  )
}

beforeEach(() => api.get.mockReset())
afterEach(cleanup)

test("renders question, conclusion and supersession", async () => {
  api.get.mockResolvedValue([topic()])
  renderIt()
  expect(await screen.findByText("Chọn cơ sở dữ liệu nào?")).toBeTruthy()
  expect(screen.getByText("Kết luận: Postgres")).toBeTruthy()
  expect(screen.getByText(/MongoDB → Postgres/)).toBeTruthy()
  expect(api.get).toHaveBeenCalledWith("/meetings/m1/topics")
})

test("shows needs-confirmation badge", async () => {
  api.get.mockResolvedValue([topic({ needs_confirmation: true, deferred: true })])
  renderIt()
  expect(await screen.findByText("Cần xác nhận")).toBeTruthy()
  expect(screen.getByText("Chờ cấp trên")).toBeTruthy()
})

test("clicking a linked event seeks to its utterance", async () => {
  api.get.mockResolvedValue([topic()])
  const onSeek = vi.fn()
  renderIt(onSeek)
  await screen.findByText("Kết luận: Postgres")
  const buttons = screen.getAllByRole("button")
  expect(buttons).toHaveLength(1)
  expect(buttons[0].className).toContain("focus-visible:ring")
  fireEvent.click(buttons[0])
  expect(onSeek).toHaveBeenCalledWith("u0003")
})

test("empty list", async () => {
  api.get.mockResolvedValue([])
  renderIt()
  expect(await screen.findByText("Không có chủ đề nào cần theo dõi")).toBeTruthy()
})
