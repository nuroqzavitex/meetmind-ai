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
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }))

import { UploadForm } from "@/features/meetings/upload-form"

function renderForm() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <UploadForm />
    </QueryClientProvider>,
  )
}

afterEach(cleanup)
beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
})

test("submit without file shows error and does not post", async () => {
  renderForm()
  await userEvent.type(screen.getByLabelText("Tiêu đề"), "Họp")
  await userEvent.click(screen.getByRole("button", { name: "Phân tích" }))
  expect(await screen.findByText("Cần chọn file transcript")).toBeInTheDocument()
  expect(api.postForm).not.toHaveBeenCalled()
})

test("submit with file posts FormData with context", async () => {
  api.postForm.mockResolvedValue({ meeting_id: "m1", job_id: "j1" })
  api.get.mockResolvedValue({
    id: "j1", kind: "analyze", meeting_id: "m1", status: "running", step: "extract", progress: 0.3, error: null,
  })
  renderForm()
  await userEvent.type(screen.getByLabelText("Tiêu đề"), "Họp")
  await userEvent.upload(
    screen.getByLabelText("File transcript"),
    new File(["hi"], "a.txt", { type: "text/plain" }),
  )
  await userEvent.click(screen.getByRole("button", { name: "Phân tích" }))
  await waitFor(() => expect(api.postForm).toHaveBeenCalledTimes(1))
  const [path, form] = api.postForm.mock.calls[0] as [string, FormData]
  expect(path).toBe("/meetings")
  expect((form.get("file") as File).name).toBe("a.txt")
  const ctx = JSON.parse(form.get("context") as string)
  expect(ctx.title).toBe("Họp")
  expect(ctx.meeting_date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  expect(await screen.findByText("Trích xuất hành vi")).toBeInTheDocument()
})

test("shows ApiError message", async () => {
  api.postForm.mockRejectedValue(
    new ApiError(422, "transcript_parse_error", "Không đọc được transcript: sai định dạng"),
  )
  renderForm()
  await userEvent.type(screen.getByLabelText("Tiêu đề"), "Họp")
  await userEvent.upload(
    screen.getByLabelText("File transcript"),
    new File(["hi"], "a.txt", { type: "text/plain" }),
  )
  await userEvent.click(screen.getByRole("button", { name: "Phân tích" }))
  expect(await screen.findByText("Không đọc được transcript: sai định dạng")).toBeInTheDocument()
})

test("title input is capped at 200 characters", () => {
  renderForm()
  expect(screen.getByLabelText("Tiêu đề")).toHaveAttribute("maxlength", "200")
})
