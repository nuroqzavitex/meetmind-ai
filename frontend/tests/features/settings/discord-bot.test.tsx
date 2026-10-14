import { cleanup, render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { afterEach, beforeEach, expect, test, vi } from "vitest"

const api = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn() }))
const org = vi.hoisted(() => ({ admin: true }))
vi.mock("@/lib/use-api", () => ({ useApi: () => api }))
vi.mock("@/features/orgs/hooks", () => ({ useIsOrgAdmin: () => org.admin }))

import { DiscordBotSettings } from "@/features/settings/discord-bot"

const BOT = {
  available: true,
  linked: false,
  link_code: "DC-7K3Q-X9P2",
  install_url: "https://discord.com/oauth2/authorize?client_id=app123&scope=applications.commands",
}

function renderIt() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <DiscordBotSettings />
    </QueryClientProvider>,
  )
}

afterEach(cleanup)
beforeEach(() => {
  Object.values(api).forEach((f) => f.mockReset())
  org.admin = true
})

test("shows the install link and the /ketnoi command with the link code", async () => {
  api.get.mockResolvedValue(BOT)
  renderIt()
  expect(await screen.findByTestId("link-command")).toHaveTextContent("/ketnoi ma:DC-7K3Q-X9P2")
  expect(screen.getByRole("link", { name: /Mời bot MeetMind/ })).toHaveAttribute("href", BOT.install_url)
  expect(screen.getByTestId("bot-status")).toHaveTextContent("Chưa liên kết")
  expect(screen.queryByRole("button", { name: /Huỷ liên kết/ })).not.toBeInTheDocument()
})

test("linked server can be unlinked and the code rotated", async () => {
  api.get.mockResolvedValue({ ...BOT, linked: true })
  api.post.mockImplementation((path: string) =>
    Promise.resolve(path.endsWith("unlink") ? { ...BOT, linked: false } : { ...BOT, link_code: "DC-AAAA-BBBB" }),
  )
  renderIt()
  await userEvent.click(await screen.findByRole("button", { name: /Huỷ liên kết/ }))
  await waitFor(() => expect(screen.getByTestId("bot-status")).toHaveTextContent("Chưa liên kết"))
  expect(api.post).toHaveBeenCalledWith("/settings/discord-bot/unlink")
  await userEvent.click(screen.getByRole("button", { name: /Đổi mã/ }))
  expect(await screen.findByText("/ketnoi ma:DC-AAAA-BBBB")).toBeInTheDocument()
})

test("explains when the backend has no bot configured", async () => {
  api.get.mockResolvedValue({ ...BOT, available: false, install_url: null })
  renderIt()
  expect(await screen.findByText(/Backend chưa cấu hình bot/)).toBeInTheDocument()
})

test("hidden for members", () => {
  org.admin = false
  const { container } = renderIt()
  expect(container).toBeEmptyDOMElement()
  expect(api.get).not.toHaveBeenCalled()
})
