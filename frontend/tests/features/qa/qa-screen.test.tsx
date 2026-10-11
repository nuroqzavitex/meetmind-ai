import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), postForm: vi.fn(), patch: vi.fn(), download: vi.fn() }))
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(""),
}))
vi.mock("@clerk/nextjs", () => ({ useAuth: () => ({ getToken: vi.fn() }) }))

import { QaScreen } from "@/features/qa/qa-screen"
import { ApiError } from "@/lib/api-client"

const REFUSAL = "Không đủ thông tin trong các cuộc họp đã phát hành."
const SAMPLE = "Ai phụ trách dựng schema?"

function renderIt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <QaScreen />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  api.get.mockResolvedValue([
    { id: "m1", title: "A", project: "Beta" },
    { id: "m2", title: "B", project: "Alpha" },
    { id: "m3", title: "C", project: "Beta" },
    { id: "m4", title: "D", project: null },
  ])
})
afterEach(cleanup)

test("sample question posts without project and shows answer + sources", async () => {
  api.post.mockResolvedValue({
    answer: "An phụ trách [1].",
    citations: [{
      ref: 1, meeting_id: "m1", title: "Họp tuần", date: "2026-03-05", ts: "00:12",
      speaker: "An", quote: "tôi làm schema", utterance_id: "u0007",
    }],
  })
  renderIt()
  fireEvent.click(screen.getByRole("button", { name: SAMPLE }))
  expect(await screen.findByText("Nguồn")).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledWith("/qa", { question: SAMPLE })
  expect(screen.getByText("tôi làm schema")).toBeInTheDocument()
})

test("selected project is sent", async () => {
  api.post.mockResolvedValue({ answer: REFUSAL, citations: [] })
  renderIt()
  await screen.findByRole("option", { name: "Alpha" })
  expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["Tất cả dự án", "Alpha", "Beta"])
  fireEvent.change(screen.getByLabelText("Dự án"), { target: { value: "Alpha" } })
  fireEvent.change(screen.getByLabelText("Câu hỏi của bạn"), { target: { value: "Gì?" } })
  fireEvent.click(screen.getByRole("button", { name: "Hỏi" }))
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/qa", { question: "Gì?", project: "Alpha" }))
})

test("refusal shows text and no sources list", async () => {
  api.post.mockResolvedValue({ answer: REFUSAL, citations: [] })
  renderIt()
  fireEvent.click(screen.getByRole("button", { name: SAMPLE }))
  expect(await screen.findByText(REFUSAL)).toBeInTheDocument()
  expect(screen.queryByText("Nguồn")).toBeNull()
})

test("error message displayed", async () => {
  api.post.mockRejectedValue(new ApiError(503, "x", "Dịch vụ tạm thời không khả dụng"))
  renderIt()
  fireEvent.click(screen.getByRole("button", { name: SAMPLE }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Dịch vụ tạm thời không khả dụng")
})

test("Enter submits, Shift+Enter does not", async () => {
  api.post.mockResolvedValue({ answer: REFUSAL, citations: [] })
  renderIt()
  const ta = screen.getByLabelText("Câu hỏi của bạn")
  fireEvent.change(ta, { target: { value: "Gì?" } })
  fireEvent.keyDown(ta, { key: "Enter", shiftKey: true })
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.keyDown(ta, { key: "Enter" })
  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
})

test("Enter during IME composition does not submit; plain Enter does", async () => {
  api.post.mockResolvedValue({ answer: REFUSAL, citations: [] })
  renderIt()
  const box = screen.getByLabelText("Câu hỏi của bạn")
  expect(box).toHaveAttribute("maxlength", "1000")
  fireEvent.change(box, { target: { value: "Gì?" } })
  fireEvent.keyDown(box, { key: "Enter", isComposing: true })
  fireEvent.keyDown(box, { key: "Enter", keyCode: 229 })
  expect(api.post).not.toHaveBeenCalled()
  fireEvent.keyDown(box, { key: "Enter" })
  await waitFor(() => expect(api.post).toHaveBeenCalledWith("/qa", { question: "Gì?" }))
})
