import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"
import { ItemCard } from "@/features/review/item-card"
import { ApiError } from "@/lib/api-client"
import type { ItemOut } from "@/lib/types"

afterEach(cleanup)

const base = {
  id: "i1", meeting_id: "m1", type: "decision", content: "Dùng Postgres", status: "final", supersedes: [],
  confidence: 0.9, flags: [], evidence: [], review_state: "pending",
} as unknown as ItemOut
const mk = (o: Record<string, unknown>) => ({ ...base, ...o }) as ItemOut

test("superseded decision is struck through", () => {
  render(<ItemCard item={mk({ status: "superseded", supersedes: ["MongoDB"] })} onAction={vi.fn()} onEvidenceClick={vi.fn()} />)
  expect(screen.getByText("Dùng Postgres").className).toContain("line-through")
  expect(screen.getByText("Bị thay thế")).toBeInTheDocument()
  expect(screen.getByText(/Thay cho/)).toBeInTheDocument()
  expect(screen.getByText("MongoDB")).toBeInTheDocument()
})

test("flags, confidence, evidence", () => {
  const onEv = vi.fn()
  render(
    <ItemCard
      item={mk({
        flags: ["missing_owner", "weird"], confidence: 0.55,
        evidence: [{ utterance_id: "u0007", speaker: "An", ts: "00:01:00", quote: "chọn Postgres" }],
      })}
      onAction={vi.fn()} onEvidenceClick={onEv}
    />,
  )
  expect(screen.getByText("Thiếu người phụ trách")).toBeInTheDocument()
  expect(screen.getByText("weird")).toBeInTheDocument()
  expect(screen.getByText("55%").className).toContain("text-destructive")
  fireEvent.click(screen.getByText(/chọn Postgres/))
  expect(onEv).toHaveBeenCalledWith("u0007")
})

test("approve and readOnly", () => {
  const onAction = vi.fn()
  const { rerender } = render(<ItemCard item={base} onAction={onAction} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Duyệt" }))
  expect(onAction).toHaveBeenCalledWith({ action: "approve" })
  rerender(<ItemCard item={base} onAction={onAction} onEvidenceClick={vi.fn()} readOnly />)
  for (const n of ["Duyệt", "Sửa", "Bác"]) expect(screen.queryByRole("button", { name: n })).toBeNull()
})

test("edit action item due date sends only that field", () => {
  const onAction = vi.fn()
  render(<ItemCard item={mk({ type: "action_item", content: "Làm X" })} onAction={onAction} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Sửa" }))
  const submit = screen.getByRole("button", { name: "Lưu" })
  expect(submit).toBeDisabled()
  fireEvent.change(screen.getByLabelText("Hạn chót"), { target: { value: "2026-10-20" } })
  fireEvent.click(submit)
  expect(onAction).toHaveBeenCalledWith({ action: "edit", patch: { due_date: "2026-10-20" } })
})

test("editing decision content requires reason", () => {
  const onAction = vi.fn()
  render(<ItemCard item={base} onAction={onAction} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Sửa" }))
  fireEvent.change(screen.getByLabelText("Nội dung"), { target: { value: "Dùng MySQL" } })
  expect(screen.getByText("Sửa quyết định cần ghi lý do")).toBeInTheDocument()
  expect(screen.getByRole("button", { name: "Lưu" })).toBeDisabled()
  fireEvent.change(screen.getByLabelText("Lý do"), { target: { value: "đổi ý" } })
  expect(screen.queryByText("Sửa quyết định cần ghi lý do")).toBeNull()
  fireEvent.click(screen.getByRole("button", { name: "Lưu" }))
  expect(onAction).toHaveBeenCalledWith({ action: "edit", patch: { content: "Dùng MySQL" }, reason: "đổi ý" })
})

test("cleared owner sends null", () => {
  const onAction = vi.fn()
  render(<ItemCard item={mk({ type: "action_item", owner: "An" })} onAction={onAction} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Sửa" }))
  fireEvent.change(screen.getByLabelText("Người phụ trách"), { target: { value: "" } })
  fireEvent.click(screen.getByRole("button", { name: "Lưu" }))
  expect(onAction).toHaveBeenCalledWith({ action: "edit", patch: { owner: null } })
})

test("blank content disables submit", () => {
  render(<ItemCard item={mk({ type: "action_item" })} onAction={vi.fn()} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Sửa" }))
  fireEvent.change(screen.getByLabelText("Nội dung"), { target: { value: "  " } })
  expect(screen.getByRole("button", { name: "Lưu" })).toBeDisabled()
})

test("failed edit keeps form and input, shows error", async () => {
  const onAction = vi.fn().mockRejectedValue(new ApiError(422, "reason_required", "Cần ghi lý do"))
  render(<ItemCard item={mk({ type: "action_item" })} onAction={onAction} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Sửa" }))
  fireEvent.change(screen.getByLabelText("Nội dung"), { target: { value: "Mới" } })
  fireEvent.click(screen.getByRole("button", { name: "Lưu" }))
  expect(await screen.findByText("Cần ghi lý do")).toBeInTheDocument()
  expect(screen.getByLabelText("Nội dung")).toHaveValue("Mới")
})

test("null status shows placeholder option", () => {
  render(<ItemCard item={mk({ status: null, type: "decision" })} onAction={vi.fn()} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Sửa" }))
  expect(screen.getByLabelText("Trạng thái")).toHaveValue("")
})

test("cleared due date sends null", () => {
  const onAction = vi.fn()
  render(<ItemCard item={mk({ type: "action_item", due_date: "2026-10-20" })} onAction={onAction} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Sửa" }))
  fireEvent.change(screen.getByLabelText("Hạn chót"), { target: { value: "" } })
  fireEvent.click(screen.getByRole("button", { name: "Lưu" }))
  expect(onAction).toHaveBeenCalledWith({ action: "edit", patch: { due_date: null } })
})

test("cleared rationale and condition send null", () => {
  const onAction = vi.fn()
  render(<ItemCard item={mk({ type: "action_item", rationale: "r", condition: "c" })} onAction={onAction} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Sửa" }))
  fireEvent.change(screen.getByLabelText("Căn cứ"), { target: { value: "" } })
  fireEvent.change(screen.getByLabelText("Điều kiện"), { target: { value: "" } })
  fireEvent.click(screen.getByRole("button", { name: "Lưu" }))
  expect(onAction).toHaveBeenCalledWith({ action: "edit", patch: { rationale: null, condition: null } })
})

test("status select only for decisions; cancel label uses Huỷ", () => {
  const { unmount } = render(<ItemCard item={mk({ type: "action_item" })} onAction={vi.fn()} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Sửa" }))
  expect(screen.queryByLabelText("Trạng thái")).toBeNull()
  expect(screen.getByRole("button", { name: "Huỷ" })).toBeInTheDocument()
  unmount()
  render(<ItemCard item={base} onAction={vi.fn()} onEvidenceClick={vi.fn()} />)
  fireEvent.click(screen.getByRole("button", { name: "Sửa" }))
  expect(screen.getByLabelText("Trạng thái")).toBeInTheDocument()
})
