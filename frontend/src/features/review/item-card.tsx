"use client"

import { Check, Pencil, X } from "lucide-react"
import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ApiError } from "@/lib/api-client"
import { cn } from "@/lib/utils"
import { REVIEW_STATE_LABEL, fmtDate, fmtPercent } from "@/lib/format"
import { ITEM_TYPE_STYLE, REVIEW_STATE_STYLE } from "@/lib/item-style"
import type { ItemAction, ItemOut } from "@/lib/types"
import { ItemEditForm } from "./item-edit-form"

const FLAG_LABEL: Record<string, string> = {
  missing_owner: "Thiếu người phụ trách",
  missing_due_date: "Thiếu hạn chót",
  missing_requester: "Thiếu người yêu cầu",
  low_confidence: "Độ tin cậy thấp",
  needs_confirmation: "Cần xác nhận",
  tentative: "Mới là gợi ý",
  conditional: "Có điều kiện",
  declined: "Người nhận chưa đồng ý",
  waiting: "Chỉ là chờ phản hồi",
}

export function ItemCard({
  item,
  onAction,
  onEvidenceClick,
  readOnly = false,
  pending = false,
}: {
  item: ItemOut
  onAction: (a: ItemAction) => unknown
  onEvidenceClick: (utteranceId: string) => void
  readOnly?: boolean
  pending?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [editError, setEditError] = useState<string | null>(null)
  const fire = (a: ItemAction) => {
    void Promise.resolve(onAction(a)).catch(() => {})
  }
  const superseded = item.status === "superseded"
  const meta: [string, string | null | undefined][] = [
    [item.type === "decision" ? "Người chốt" : "Người phụ trách", item.owner],
    ["Người yêu cầu", item.requester],
    ["Hạn chót", item.due_date ? fmtDate(item.due_date) : null],
    ["Điều kiện", item.condition],
    ["Căn cứ", item.rationale],
  ]

  return (
    <Card className={cn("border border-border border-l-4 shadow-xs ring-0", ITEM_TYPE_STYLE[item.type]?.border, superseded && "opacity-75")}>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="outline" className={cn("border-transparent ring-1 ring-inset", REVIEW_STATE_STYLE[item.review_state])}>
            {REVIEW_STATE_LABEL[item.review_state]}
          </Badge>
          <Badge variant={item.confidence < 0.6 ? "destructive" : "outline"} title="Độ tin cậy">
            {fmtPercent(item.confidence)}
          </Badge>
          {superseded && <Badge variant="outline">Bị thay thế</Badge>}
          {item.flags.map((f) => (
            <Badge key={f} variant="destructive">
              {FLAG_LABEL[f] ?? f}
            </Badge>
          ))}
        </div>
        <p className={cn("text-[0.95rem] leading-relaxed font-medium", superseded && "line-through text-muted-foreground")}>{item.content}</p>
        {item.supersedes.length > 0 && (
          <p className="text-sm text-muted-foreground">
            Thay cho:{" "}
            {item.supersedes.map((s, i) => (
              <span key={s}>
                {i > 0 && ", "}
                <s>{s}</s>
              </span>
            ))}
          </p>
        )}
        {meta.some(([, v]) => v) && (
          <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
            {meta.map(([k, val]) =>
              val ? (
                <div key={k} className="contents">
                  <dt className="text-muted-foreground">{k}:</dt>
                  <dd className="font-medium">{val}</dd>
                </div>
              ) : null,
            )}
          </dl>
        )}
        {item.evidence.length > 0 && (
          <ul className="space-y-1.5">
            {[...item.evidence].sort((a, b) => a.ts.localeCompare(b.ts)).map((e, i) => (
              <li key={`${e.utterance_id}-${i}`}>
                <button
                  type="button"
                  className="group/ev w-full rounded-lg border-l-2 border-primary/30 bg-muted/60 px-3 py-2 text-left text-sm transition-colors hover:border-primary hover:bg-accent"
                  onClick={() => onEvidenceClick(e.utterance_id)}
                >
                  <span className="mr-1.5 font-mono text-xs text-muted-foreground">[{e.ts} · {e.speaker}]</span>
                  <span className="text-foreground/80 italic">&quot;{e.quote}&quot;</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {!readOnly && !editing && (
          <div className="flex flex-wrap gap-2 border-t pt-3">
            <Button size="sm" disabled={pending} onClick={() => fire({ action: "approve" })}>
              <Check aria-hidden />
              Duyệt
            </Button>
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              <Pencil aria-hidden />
              Sửa
            </Button>
            <Button size="sm" variant="destructive" disabled={pending} onClick={() => fire({ action: "reject" })}>
              <X aria-hidden />
              Bác
            </Button>
          </div>
        )}
        {!readOnly && editing && (
          <ItemEditForm
            item={item}
            error={editError}
            onCancel={() => {
              setEditing(false)
              setEditError(null)
            }}
            onSubmit={async (a) => {
              setEditError(null)
              try {
                await onAction(a)
                setEditing(false)
              } catch (e) {
                setEditError(e instanceof ApiError ? e.message : "Không cập nhật được mục.")
              }
            }}
          />
        )}
      </CardContent>
    </Card>
  )
}
