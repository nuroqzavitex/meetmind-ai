"use client"

import { useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent } from "@/components/ui/card"
import { ApiError } from "@/lib/api-client"
import { cn } from "@/lib/utils"
import { REVIEW_STATE_LABEL, fmtDate, fmtPercent } from "@/lib/format"
import type { ItemAction, ItemOut } from "@/lib/types"
import { ItemEditForm } from "./item-edit-form"

const FLAG_LABEL: Record<string, string> = {
  missing_owner: "Thiếu người phụ trách",
  missing_due_date: "Thiếu hạn chót",
  missing_requester: "Thiếu người yêu cầu",
  low_confidence: "Độ tin cậy thấp",
  needs_confirmation: "Cần xác nhận",
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
    ["Người phụ trách", item.owner],
    ["Người yêu cầu", item.requester],
    ["Hạn chót", item.due_date ? fmtDate(item.due_date) : null],
    ["Điều kiện", item.condition],
    ["Căn cứ", item.rationale],
  ]

  return (
    <Card>
      <CardContent className="space-y-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{REVIEW_STATE_LABEL[item.review_state]}</Badge>
          <Badge variant={item.confidence < 0.6 ? "destructive" : "outline"}>
            {fmtPercent(item.confidence)}
          </Badge>
          {superseded && <Badge variant="outline">Bị thay thế</Badge>}
          {item.flags.map((f) => (
            <Badge key={f} variant="destructive">
              {FLAG_LABEL[f] ?? f}
            </Badge>
          ))}
        </div>
        <p className={cn("font-medium", superseded && "line-through text-muted-foreground")}>{item.content}</p>
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
        <dl className="text-sm">
          {meta.map(([k, val]) =>
            val ? (
              <div key={k} className="flex gap-1">
                <dt className="text-muted-foreground">{k}:</dt>
                <dd>{val}</dd>
              </div>
            ) : null,
          )}
        </dl>
        {item.evidence.length > 0 && (
          <ul className="space-y-1 text-sm">
            {item.evidence.map((e, i) => (
              <li key={`${e.utterance_id}-${i}`}>
                <button
                  type="button"
                  className="text-left text-muted-foreground hover:underline"
                  onClick={() => onEvidenceClick(e.utterance_id)}
                >
                  [{e.ts} · {e.speaker}] &quot;{e.quote}&quot;
                </button>
              </li>
            ))}
          </ul>
        )}
        {!readOnly && !editing && (
          <div className="flex gap-2">
            <Button size="sm" disabled={pending} onClick={() => fire({ action: "approve" })}>
              Duyệt
            </Button>
            <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
              Sửa
            </Button>
            <Button size="sm" variant="destructive" disabled={pending} onClick={() => fire({ action: "reject" })}>
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
