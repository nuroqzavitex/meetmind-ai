"use client"

import { Check, CircleCheckBig, HelpCircle, ShieldAlert, X } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ITEM_TYPE_LABEL } from "@/lib/format"
import { ITEM_TYPE_STYLE } from "@/lib/item-style"
import type { ItemAction, ItemOut } from "@/lib/types"
import { cn } from "@/lib/utils"
import { HOLD_INFO, HoldQuote } from "./hold"

const COMMITTED = new Set(["decision", "action_item"])

/** Decisions and tasks the analysis presents as settled (no hold, not dropped). */
export function settledCount(items: ItemOut[]): number {
  return items.filter(
    (i) => COMMITTED.has(i.type) && !i.hold && i.review_state !== "rejected" && i.status !== "superseded",
  ).length
}

/** Held items the reviewer still has to settle. */
export function heldPending(items: ItemOut[]): ItemOut[] {
  return items.filter((i) => i.hold && i.review_state === "pending")
}

/**
 * Top of the review screen: what the analysis settled vs what it refused to make official.
 * Each held item shows why, with the triggering words highlighted, and three ways to settle it.
 */
export function ConfirmQueue({
  items,
  readOnly,
  pendingId,
  onAction,
  onEvidenceClick,
}: {
  items: ItemOut[]
  readOnly: boolean
  pendingId: string | null
  onAction: (id: string, body: ItemAction) => void
  onEvidenceClick: (utteranceId: string) => void
}) {
  const held = heldPending(items)
  const settled = settledCount(items)
  if (held.length === 0 && !items.some((i) => i.hold)) return null

  return (
    <section aria-labelledby="confirm-queue" className="space-y-3 rounded-xl border border-amber-200 bg-amber-50/40 p-4 dark:border-amber-500/30 dark:bg-amber-950/20">
      <div className="flex flex-wrap items-center gap-2">
        <h2 id="confirm-queue" className="mr-auto flex items-center gap-2 font-semibold">
          <ShieldAlert aria-hidden className="size-4 text-amber-600" />
          Hàng chờ xác nhận
        </h2>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-medium text-emerald-900 dark:bg-emerald-500/20 dark:text-emerald-100">
          <CircleCheckBig aria-hidden className="size-3.5" />
          Đã chốt: {settled}
        </span>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-200 px-2.5 py-0.5 text-xs font-medium text-amber-950 dark:bg-amber-500/30 dark:text-amber-50">
          <ShieldAlert aria-hidden className="size-3.5" />
          Cần xác nhận: {held.length}
        </span>
      </div>
      <p className="text-sm text-muted-foreground">
        AI không tự biến những câu dưới đây thành quyết định hay việc chính thức. Phần tô vàng là lý do nó dè dặt.
      </p>
      {held.length === 0 ? (
        <p className="rounded-lg bg-background/70 px-3 py-2 text-sm text-muted-foreground">Đã xử lý hết các mục cần xác nhận.</p>
      ) : (
        <ul className="space-y-2">
          {held.map((item) => {
            const hold = item.hold!
            const info = HOLD_INFO[hold.reason]
            const busy = pendingId === item.id
            return (
              <li key={item.id} className="space-y-2 rounded-lg border bg-card p-3 shadow-xs">
                <div className="flex flex-wrap items-center gap-1.5">
                  <Badge variant="outline" className={cn("border-transparent ring-1 ring-inset", ITEM_TYPE_STYLE[item.type].badge)}>
                    {ITEM_TYPE_LABEL[item.type]}
                  </Badge>
                  <Badge className="bg-amber-500 text-white hover:bg-amber-500">{info.label}</Badge>
                  {item.owner && <span className="text-xs text-muted-foreground">Người phụ trách: {item.owner}</span>}
                </div>
                <p className="font-medium">{item.content}</p>
                <button
                  type="button"
                  className="w-full rounded-md bg-muted/60 px-3 py-2 text-left transition-colors hover:bg-accent"
                  onClick={() => {
                    const ev = item.evidence.find((e) => e.quote === hold.quote) ?? item.evidence[0]
                    if (ev) onEvidenceClick(ev.utterance_id)
                  }}
                >
                  <HoldQuote hold={hold} />
                </button>
                <p className="text-sm text-muted-foreground">→ {info.why}</p>
                {!readOnly && (
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" disabled={busy} onClick={() => onAction(item.id, { action: "approve" })}>
                      <Check aria-hidden />
                      Xác nhận là chính thức
                    </Button>
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => onAction(item.id, { action: "to_question" })}>
                      <HelpCircle aria-hidden />
                      Chuyển thành câu hỏi mở
                    </Button>
                    <Button size="sm" variant="ghost" disabled={busy} onClick={() => onAction(item.id, { action: "reject" })}>
                      <X aria-hidden />
                      Bỏ
                    </Button>
                  </div>
                )}
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
