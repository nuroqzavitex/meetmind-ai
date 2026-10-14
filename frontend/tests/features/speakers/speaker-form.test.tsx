import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

import { ApiError } from "@/lib/api-client"

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  postForm: vi.fn(),
  patch: vi.fn(),
  download: vi.fn(),
}))
const push = vi.hoisted(() => vi.fn())
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }))

import { SpeakerForm, validateRows } from "@/features/speakers/speaker-form"

const SPEAKERS = [
  { label: "Người nói A", count: 2, samples: ["Hôm nay mình chốt CSDL", "Vậy chốt Postgres nhé"] },
  { label: "Người nói B", count: 1, samples: ["Em đề xuất MongoDB"] },
]

function renderForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <SpeakerForm meetingId="m1" />
    </QueryClientProvider>,
  )
}

afterEach(cleanup)
beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  push.mockReset()
})

test("shows each speaker with samples and submits names and decision maker", async () => {
  api.get.mockImplementation((path: string) =>
    path === "/meetings/m1/speakers"
      ? Promise.resolve(SPEAKERS)
      : Promise.resolve({
          id: "j2", kind: "analyze", meeting_id: "m1", status: "succeeded", step: "done", progress: 1, error: null,
        }),
  )
  api.post.mockResolvedValue({ meeting_id: "m1", job_id: "j2" })
  renderForm()
  expect(await screen.findByText(/Vậy chốt Postgres nhé/)).toBeInTheDocument()
  expect(screen.getByText("2 câu")).toBeInTheDocument()

  await userEvent.type(screen.getByLabelText("Tên của Người nói A"), "  Lan ")
  await userEvent.type(screen.getByLabelText("Tên của Người nói B"), "Minh")
  await userEvent.click(screen.getByRole("checkbox", { name: "Người nói A là người quyết định" }))
  await userEvent.click(screen.getByRole("button", { name: "Phân tích" }))

  await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
  expect(api.post).toHaveBeenCalledWith("/meetings/m1/speakers", {
    speakers: [
      { label: "Người nói A", name: "Lan", is_decision_maker: true },
      { label: "Người nói B", name: "Minh", is_decision_maker: false },
    ],
  })
  await waitFor(() => expect(push).toHaveBeenCalledWith("/meetings/m1/review"))
})

test("blocks submission with missing or duplicate names", async () => {
  api.get.mockResolvedValue(SPEAKERS)
  renderForm()
  await userEvent.type(await screen.findByLabelText("Tên của Người nói A"), "Lan")
  await userEvent.click(screen.getByRole("button", { name: "Phân tích" }))
  expect(await screen.findByText("Chưa nhập tên cho Người nói B")).toBeInTheDocument()
  await userEvent.type(screen.getByLabelText("Tên của Người nói B"), "lan")
  await userEvent.click(screen.getByRole("button", { name: "Phân tích" }))
  expect(await screen.findByText('Tên "lan" bị trùng')).toBeInTheDocument()
  expect(api.post).not.toHaveBeenCalled()
})

test("validateRows rejects colons and names not starting with a letter", () => {
  const rows = { "Người nói A": { name: "Lan: x", isDecisionMaker: false }, "Người nói B": { name: "9X", isDecisionMaker: false } }
  expect(validateRows(SPEAKERS, rows)).toHaveLength(2)
})

test("meeting not awaiting speakers shows the server message", async () => {
  api.get.mockRejectedValue(new ApiError(409, "not_awaiting_speakers", "Cuộc họp không ở bước gán người nói"))
  renderForm()
  expect(await screen.findByRole("alert")).toHaveTextContent("Cuộc họp không ở bước gán người nói")
})
