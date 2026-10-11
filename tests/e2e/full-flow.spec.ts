import { readFileSync } from "node:fs"
import path from "node:path"

import { clerk, setupClerkTestingToken } from "@clerk/testing/playwright"
import { expect, test, type Page } from "@playwright/test"

import { missingClerkEnv, skipReason } from "./env"

test.skip(missingClerkEnv().length > 0, skipReason())

const TRANSCRIPT = path.resolve(__dirname, "../fixtures/transcripts/payment_v2.txt")
const QUESTION = "Dịch vụ thanh toán dùng cơ sở dữ liệu gì?"
// Tab labels of the review screen (ITEM_TYPE_LABEL in src/lib/format.ts).
const ITEM_TAB_LABELS = [
  "Quyết định",
  "Việc cần làm",
  "Vướng mắc",
  "Yêu cầu",
  "Câu hỏi mở",
  "Tri thức",
  "Góp ý",
]

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")

/**
 * Runs in the browser after sign-in. Personal accounts are disabled, so a fresh session may be
 * "pending" (choose-organization task) with no active org: activate the user's first organization.
 */
async function activateFirstOrganization(): Promise<"ok" | "no-session" | "no-membership"> {
  const session = window.Clerk.session
  if (!session) return "no-session"
  if (window.Clerk.organization) return "ok"
  const { data } = await session.user.getOrganizationMemberships()
  const membership = data[0]
  if (!membership) return "no-membership"
  await window.Clerk.setActive({ organization: membership.organization.id })
  return window.Clerk.organization ? "ok" : "no-session"
}

async function signIn(page: Page): Promise<void> {
  await setupClerkTestingToken({ page })
  // @clerk/testing needs a public page that loads Clerk; every other route redirects here anyway.
  await page.goto("/sign-in")
  await clerk.signIn({
    page,
    signInParams: {
      strategy: "password",
      identifier: process.env.E2E_CLERK_USER_USERNAME!,
      password: process.env.E2E_CLERK_USER_PASSWORD ?? "",
    },
  })
  // <SignIn> may redirect on its own once the session exists; retry across that navigation.
  let outcome = ""
  await expect(async () => {
    await clerk.loaded({ page })
    outcome = await page.evaluate(activateFirstOrganization)
    expect(["ok", "no-membership"]).toContain(outcome)
  }).toPass({ timeout: 30_000 })
  if (outcome === "no-membership") {
    throw new Error(
      "E2E Clerk user has no organization membership: add it to an organization (tests/e2e/README.md)",
    )
  }
  await page.goto("/")
  await expect(page).toHaveURL(/^https?:\/\/[^/]+\/$/)
  await expect(page.getByRole("heading", { name: "Cuộc họp", exact: true })).toBeVisible()
}

async function approveAll(page: Page): Promise<void> {
  for (const label of ITEM_TAB_LABELS) {
    await page.getByRole("tab", { name: new RegExp(`^${escapeRe(label)} \\(`) }).click()
    const pending = page
      .getByRole("tabpanel")
      .locator('[data-slot="card"]')
      .filter({ has: page.getByText("Chờ duyệt", { exact: true }) })
    for (let n = await pending.count(); n > 0; n--) {
      await pending.first().getByRole("button", { name: "Duyệt", exact: true }).click()
      await expect(pending).toHaveCount(n - 1)
    }
  }
  await expect(page.getByText(/Còn \d+ mục chưa duyệt/)).toHaveCount(0)
}

test("upload → review → publish → download md → ask with citation", async ({ page }) => {
  const run = Date.now()
  const title = `E2E payment ${run}`
  const project = `e2e-${run}`

  await signIn(page)

  // Upload
  await page.goto("/meetings/new")
  await page.getByLabel("File transcript").setInputFiles(TRANSCRIPT)
  await page.getByLabel("Tiêu đề").fill(title)
  await page.getByLabel("Ngày họp").fill("2026-10-01")
  await page.getByLabel("Dự án").fill(project)
  await page.getByLabel("Người tham gia").fill("Lan | *\nMinh\nHoa")
  await page.getByRole("button", { name: "Phân tích", exact: true }).click()

  // Review: the worker (fake LLM) finishes and the form navigates here.
  await page.waitForURL(/\/meetings\/[^/]+\/review$/, { timeout: 60_000 })
  const meetingId = new URL(page.url()).pathname.split("/")[2]
  await page.getByRole("tab", { name: /^Quyết định \(/ }).click()
  await expect(
    page.getByRole("tabpanel").locator('[data-slot="card"]').filter({ hasText: "Postgres" }).first(),
  ).toBeVisible({ timeout: 60_000 })

  await approveAll(page)
  await page.getByRole("button", { name: "Phát hành" }).click()

  // Minutes + markdown export
  await page.waitForURL(new RegExp(`/meetings/${escapeRe(meetingId)}/minutes$`))
  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("button", { name: "Tải .md" }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/\.md$/)
  expect(readFileSync(await download.path(), "utf8")).toContain("Postgres")

  // Q&A: retry until the index job has made this meeting searchable.
  await page.goto("/qa")
  await page.getByLabel("Dự án").selectOption(project)
  const chip = page.getByRole("link", { name: new RegExp(`^\\[${escapeRe(title)} · `) }).first()
  await expect(async () => {
    await page.getByLabel("Câu hỏi của bạn").fill(QUESTION)
    await page.getByRole("button", { name: "Hỏi", exact: true }).click()
    await expect(page.getByText("Đang tìm câu trả lời…")).toHaveCount(0, { timeout: 30_000 })
    await expect(chip).toBeVisible({ timeout: 1_000 })
  }).toPass({ timeout: 60_000, intervals: [2_000, 5_000] })

  await chip.click()
  await expect(page).toHaveURL(new RegExp(`/meetings/${escapeRe(meetingId)}/minutes\\?u=`))
})
