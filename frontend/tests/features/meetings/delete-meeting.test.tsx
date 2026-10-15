import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

import { ApiError } from "@/lib/api-client"

const api = vi.hoisted(() => ({ del: vi.fn() }))
const org = vi.hoisted(() => ({ admin: true }))
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
vi.mock("@/features/orgs/hooks", () => ({ useIsOrgAdmin: () => org.admin }))

import { DeleteMeetingButton } from "@/features/meetings/delete-meeting"

function renderIt(props: { compact?: boolean; onDeleted?: () => void } = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <DeleteMeetingButton meetingId="m1" title="Họp chốt" {...props} />
    </QueryClientProvider>,
  )
}

afterEach(cleanup)
beforeEach(() => {
  api.del.mockReset()
  org.admin = true
})

test("asks for confirmation, then deletes and reports back", async () => {
  api.del.mockResolvedValue(undefined)
  const onDeleted = vi.fn()
  renderIt({ onDeleted })
  await userEvent.click(screen.getByRole("button", { name: "Xoá" }))
  expect(await screen.findByText(/Xoá vĩnh viễn cuộc họp “Họp chốt”/)).toBeInTheDocument()
  expect(api.del).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole("button", { name: /Xoá vĩnh viễn/ }))
  await waitFor(() => expect(api.del).toHaveBeenCalledWith("/meetings/m1"))
  await waitFor(() => expect(onDeleted).toHaveBeenCalled())
})

test("shows the server refusal while the meeting is being processed", async () => {
  api.del.mockRejectedValue(new ApiError(409, "job_running", "Cuộc họp đang được xử lý, hãy đợi xong rồi xoá"))
  renderIt({ compact: true })
  await userEvent.click(screen.getByRole("button", { name: "Xoá cuộc họp Họp chốt" }))
  await userEvent.click(await screen.findByRole("button", { name: /Xoá vĩnh viễn/ }))
  expect(await screen.findByRole("alert")).toHaveTextContent("đang được xử lý")
})

test("hidden for members", () => {
  org.admin = false
  const { container } = renderIt()
  expect(container).toBeEmptyDOMElement()
})
