"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import type { ItemAction, ItemOut, ItemPatch } from "@/lib/types"

const STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: "final", label: "Chốt" },
  { value: "superseded", label: "Bị thay thế" },
  { value: "rejected", label: "Bị bác" },
  { value: "open", label: "Còn mở" },
]

const selectCls =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"

export function ItemEditForm({
  item,
  onSubmit,
  onCancel,
  error,
}: {
  item: ItemOut
  onSubmit: (a: ItemAction) => unknown
  onCancel: () => void
  error?: string | null
}) {
  const initial = {
    content: item.content ?? "",
    owner: item.owner ?? "",
    requester: item.requester ?? "",
    due_date: item.due_date ?? "",
    status: (item.status as string | null) ?? "",
    rationale: item.rationale ?? "",
    condition: item.condition ?? "",
  }
  const [v, setV] = useState(initial)
  const [reason, setReason] = useState("")
  const set = (k: keyof typeof initial) => (e: { target: { value: string } }) =>
    setV((p) => ({ ...p, [k]: e.target.value }))

  // Only changed fields are sent; a cleared value goes as an explicit null (clears the field).
  const patch: Record<string, string | null> = {}
  for (const k of Object.keys(initial) as (keyof typeof initial)[]) {
    if (v[k] !== initial[k]) patch[k] = v[k] === "" ? null : v[k]
  }
  const changed = Object.keys(patch).length > 0
  const needReason = item.type === "decision" && ("content" in patch || "status" in patch)
  const missingReason = needReason && !reason.trim()
  const canSubmit = changed && !missingReason && v.content.trim() !== ""

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    const action: ItemAction = { action: "edit", patch: patch as ItemPatch }
    if (reason.trim()) action.reason = reason.trim()
    onSubmit(action)
  }

  const fid = (id: string) => `${item.id}-${id}`
  const field = (id: string, label: string, el: React.ReactNode) => (
    <div className="space-y-1">
      <Label htmlFor={fid(id)}>{label}</Label>
      {el}
    </div>
  )

  return (
    <form onSubmit={submit} className="mt-3 space-y-3 rounded-lg border p-3">
      {field("content", "Nội dung", <Textarea id={fid("content")} value={v.content} onChange={set("content")} />)}
      <div className="grid gap-3 sm:grid-cols-2">
        {field("owner", "Người phụ trách", <Input id={fid("owner")} value={v.owner} onChange={set("owner")} />)}
        {field("requester", "Người yêu cầu", <Input id={fid("requester")} value={v.requester} onChange={set("requester")} />)}
        {field("due_date", "Hạn chót", <Input id={fid("due_date")} type="date" value={v.due_date} onChange={set("due_date")} />)}
        {item.type === "decision" &&
          field(
            "status",
            "Trạng thái",
            <select id={fid("status")} className={selectCls} value={v.status} onChange={set("status")}>
              {initial.status === "" && <option value="">—</option>}
              {STATUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>,
          )}
      </div>
      {field("rationale", "Căn cứ", <Textarea id={fid("rationale")} value={v.rationale} onChange={set("rationale")} />)}
      {field("condition", "Điều kiện", <Input id={fid("condition")} value={v.condition} onChange={set("condition")} />)}
      {field("reason", "Lý do", <Textarea id={fid("reason")} value={reason} onChange={(e) => setReason(e.target.value)} />)}
      {missingReason && <p className="text-sm text-destructive">Sửa quyết định cần ghi lý do</p>}
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="flex gap-2">
        <Button type="submit" size="sm" disabled={!canSubmit}>
          Lưu
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onCancel}>
          Huỷ
        </Button>
      </div>
    </form>
  )
}
