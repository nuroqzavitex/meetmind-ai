import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

import { ApiError } from "@/lib/api-client"

const api = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
}))
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))

import { DiscordSettings } from "@/features/settings/discord-settings"

const HOOK = "https://discord.com/api/webhooks/123/abc-DEF"
const OFF = { configured: false, webhook_hint: null, digest_enabled: false }
const ON = { configured: true, webhook_hint: "…-DEF", digest_enabled: true }

function renderIt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <DiscordSettings />
    </QueryClientProvider>,
  )
}

afterEach(cleanup)
beforeEach(() => Object.values(api).forEach((f) => f.mockReset()))

test("saves a new webhook with the digest toggle", async () => {
  api.get.mockResolvedValue(OFF)
  api.put.mockResolvedValue(ON)
  renderIt()
  expect(await screen.findByText(/Chưa kết nối/)).toBeInTheDocument()
  expect(screen.queryByRole("button", { name: /Gửi thử/ })).not.toBeInTheDocument()

  await userEvent.type(screen.getByLabelText("URL webhook"), `  ${HOOK} `)
  await userEvent.click(screen.getByRole("checkbox", { name: "Bản tin nhắc việc 8h sáng" }))
  await userEvent.click(screen.getByRole("button", { name: "Lưu" }))

  await waitFor(() =>
    expect(api.put).toHaveBeenCalledWith("/settings/discord", { webhook_url: HOOK, digest_enabled: true }),
  )
  expect(await screen.findByText("Đã lưu cài đặt")).toBeInTheDocument()
  expect(screen.getByText(/Đã kết nối webhook \(…-DEF\)/)).toBeInTheDocument()
  expect(screen.getByLabelText("Đổi URL webhook")).toHaveValue("")
})

test("rejects a non-Discord URL without calling the API", async () => {
  api.get.mockResolvedValue(OFF)
  renderIt()
  await userEvent.type(await screen.findByLabelText("URL webhook"), "https://evil.io/hook")
  await userEvent.click(screen.getByRole("button", { name: "Lưu" }))
  expect(screen.getByRole("alert")).toHaveTextContent("URL webhook không hợp lệ")
  expect(api.put).not.toHaveBeenCalled()
})

test("saving without a new URL keeps the stored webhook", async () => {
  api.get.mockResolvedValue(ON)
  api.put.mockResolvedValue({ ...ON, digest_enabled: false })
  renderIt()
  await userEvent.click(await screen.findByRole("checkbox", { name: "Bản tin nhắc việc 8h sáng" }))
  await userEvent.click(screen.getByRole("button", { name: "Lưu" }))
  await waitFor(() => expect(api.put).toHaveBeenCalledWith("/settings/discord", { digest_enabled: false }))
})

test("sends a test message and shows Discord errors", async () => {
  api.get.mockResolvedValue(ON)
  api.post.mockResolvedValueOnce(undefined)
  renderIt()
  await userEvent.click(await screen.findByRole("button", { name: /Gửi thử/ }))
  expect(await screen.findByText(/Đã gửi tin thử/)).toBeInTheDocument()
  expect(api.post).toHaveBeenCalledWith("/settings/discord/test")

  api.post.mockRejectedValueOnce(new ApiError(502, "discord_error", "Webhook không còn tồn tại"))
  await userEvent.click(screen.getByRole("button", { name: /Gửi thử/ }))
  expect(await screen.findByRole("alert")).toHaveTextContent("Webhook không còn tồn tại")
})

test("removes the webhook", async () => {
  api.get.mockResolvedValue(ON)
  api.put.mockResolvedValue(OFF)
  renderIt()
  await userEvent.click(await screen.findByRole("button", { name: /Xoá webhook/ }))
  await waitFor(() =>
    expect(api.put).toHaveBeenCalledWith("/settings/discord", { webhook_url: "", digest_enabled: true }),
  )
  expect(await screen.findByText(/Chưa kết nối/)).toBeInTheDocument()
})


test("saves the Discord invite link and rejects other links", async () => {
  api.get.mockResolvedValue(OFF)
  api.put.mockResolvedValue({ ...OFF, invite_url: "https://discord.gg/team" })
  renderIt()
  const field = await screen.findByLabelText("Link mời vào server Discord")
  await userEvent.type(field, "https://evil.io/x")
  await userEvent.click(screen.getByRole("button", { name: "Lưu" }))
  expect(screen.getByRole("alert")).toHaveTextContent("Link mời Discord không hợp lệ")
  expect(api.put).not.toHaveBeenCalled()

  await userEvent.clear(field)
  await userEvent.type(field, "https://discord.gg/team")
  await userEvent.click(screen.getByRole("button", { name: "Lưu" }))
  await waitFor(() =>
    expect(api.put).toHaveBeenCalledWith("/settings/discord", {
      digest_enabled: false,
      invite_url: "https://discord.gg/team",
    }),
  )
})
