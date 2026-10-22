import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"
import { ConfirmQueue, heldPending, settledCount } from "@/features/review/confirm-queue"
import { splitPhrase } from "@/features/review/hold"
import type { ItemOut } from "@/lib/types"

afterEach(cleanup)

const base = {
  id: "i1", meeting_id: "m1", type: "action_item", content: "Làm dashboard", status: "final",
  supersedes: [], confidence: 0.9, flags: [], review_state: "pending", owner: "Quốc",
  evidence: [{ utterance_id: "u0009", speaker: "Hằng", ts: "00:02:50", quote: "Quốc làm dashboard nhé." }],
} as unknown as ItemOut
const mk = (o: Record<string, unknown>) => ({ ...base, ...o }) as ItemOut
const declined = mk({
  flags: ["needs_confirmation", "declined"],
  hold: {
    reason: "declined", quote: "Tuần này em kín lịch rồi chị.", phrase: "kín lịch",
    speaker: "Quốc", ts: "00:03:05",
  },
})

test("splitPhrase finds the phrase or leaves the quote whole", () => {
  expect(splitPhrase("em kín lịch rồi", "kín lịch")).toEqual(["em ", "kín lịch", " rồi"])
  expect(splitPhrase("em bận", "kín lịch")).toEqual(["em bận", "", ""])
  expect(splitPhrase("em bận", null)).toEqual(["em bận", "", ""])
})

test("counts settled decisions and tasks apart from held ones", () => {
  const items = [
    mk({ id: "a" }),
    mk({ id: "b", type: "decision" }),
    mk({ id: "c", type: "blocker" }),
    mk({ id: "d", review_state: "rejected" }),
    mk({ ...declined, id: "e" }),
    mk({ ...declined, id: "f", review_state: "edited" }),
  ]
  expect(settledCount(items)).toBe(2)
  expect(heldPending(items).map((i) => i.id)).toEqual(["e"])
})

test("shows why an item is held, with the trigger highlighted", () => {
  render(
    <ConfirmQueue items={[mk({ id: "ok" }), declined]} readOnly={false} pendingId={null}
      onAction={vi.fn()} onEvidenceClick={vi.fn()} />,
  )
  expect(screen.getByText("Đã chốt: 1")).toBeInTheDocument()
  expect(screen.getByText("Cần xác nhận: 1")).toBeInTheDocument()
  expect(screen.getByText("Người nhận từ chối")).toBeInTheDocument()
  expect(screen.getByText("kín lịch").tagName).toBe("MARK")
  expect(screen.getByText(/Người được giao đã từ chối/)).toBeInTheDocument()
})

test("the three ways to settle a held item", () => {
  const onAction = vi.fn()
  render(<ConfirmQueue items={[declined]} readOnly={false} pendingId={null}
    onAction={onAction} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: /Xác nhận là chính thức/ }))
  fireEvent.click(screen.getByRole("button", { name: /Chuyển thành câu hỏi mở/ }))
  fireEvent.click(screen.getByRole("button", { name: /Bỏ/ }))
  expect(onAction.mock.calls).toEqual([
    ["i1", { action: "approve" }], ["i1", { action: "to_question" }], ["i1", { action: "reject" }],
  ])
})

test("clicking the quote jumps to the refusal in the transcript", () => {
  const onEv = vi.fn()
  const item = mk({
    ...declined,
    evidence: [...base.evidence, { utterance_id: "u0010", speaker: "Quốc", ts: "00:03:05", quote: "Tuần này em kín lịch rồi chị." }],
  })
  render(<ConfirmQueue items={[item]} readOnly={false} pendingId={null} onAction={vi.fn()} onEvidenceClick={onEv} />)
  fireEvent.click(screen.getByText("kín lịch"))
  expect(onEv).toHaveBeenCalledWith("u0010")
})

test("read-only hides the actions; nothing held means no queue", () => {
  const { rerender, container } = render(
    <ConfirmQueue items={[declined]} readOnly pendingId={null} onAction={vi.fn()} onEvidenceClick={vi.fn()} />,
  )
  expect(screen.queryByRole("button", { name: /Xác nhận/ })).toBeNull()
  rerender(<ConfirmQueue items={[mk({})]} readOnly={false} pendingId={null} onAction={vi.fn()} onEvidenceClick={vi.fn()} />)
  expect(container).toBeEmptyDOMElement()
})

test("all held items settled shows a done note", () => {
  render(<ConfirmQueue items={[mk({ ...declined, review_state: "edited" })]} readOnly={false} pendingId={null}
    onAction={vi.fn()} onEvidenceClick={vi.fn()} />)
  expect(screen.getByText("Đã xử lý hết các mục cần xác nhận.")).toBeInTheDocument()
})
