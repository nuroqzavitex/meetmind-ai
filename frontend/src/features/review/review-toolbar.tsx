"use client"

import { CheckCheck, Send } from "lucide-react"

import { Button } from "@/components/ui/button"
import { REVIEW_STATE_LABEL } from "@/lib/format"
import { REVIEW_STATE_STYLE } from "@/lib/item-style"
import { cn } from "@/lib/utils"
import { ApiError } from "@/lib/api-client"
import type { ItemOut, ReviewState } from "@/lib/types"
import { useApproveClean, usePublish } from "./hooks"
import { countPending } from "./sort"

const STATES: ReviewState[] = ["pending", "approved", "edited", "rejected"]
const errMsg = (e: unknown) => (e instanceof ApiError ? e.message : "Có lỗi xảy ra, vui lòng thử lại.")

export function ReviewToolbar({
  meetingId,
  items,
  readOnly,
}: {
  meetingId: string
  items: ItemOut[]
  readOnly: boolean
}) {
  const approve = useApproveClean(meetingId)
  const publish = usePublish(meetingId)
  const pending = countPending(items)

  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-3 shadow-xs">
      <div className="flex flex-wrap gap-2 text-sm">
        {STATES.map((s) => (
          <span
            key={s}
            className={cn("rounded-full px-2.5 py-0.5 font-medium ring-1 ring-inset", REVIEW_STATE_STYLE[s])}
          >
            {REVIEW_STATE_LABEL[s]}: {items.filter((i) => i.review_state === s).length}
          </span>
        ))}
      </div>
      {!readOnly && (
        <div className="ml-auto flex items-center gap-2">
          <Button variant="outline" disabled={approve.isPending} onClick={() => approve.mutate()}>
            <CheckCheck aria-hidden />
            Chấp nhận mục sạch
          </Button>
          {pending > 0 && (
            <span className="text-sm text-muted-foreground">Còn {pending} mục chưa duyệt</span>
          )}
          <Button
            disabled={pending > 0 || publish.isPending}
            title={pending > 0 ? `Còn ${pending} mục chưa duyệt` : undefined}
            onClick={() => publish.mutate()}
          >
            <Send aria-hidden />
            Phát hành
          </Button>
        </div>
      )}
      <div className="basis-full text-sm empty:hidden" role="status">
        {approve.isSuccess && <span>Đã duyệt {approve.data.approved} mục</span>}
        {approve.isError && <span className="text-destructive">{errMsg(approve.error)}</span>}
        {publish.isError && <span className="text-destructive">{errMsg(publish.error)}</span>}
      </div>
    </div>
  )
}
