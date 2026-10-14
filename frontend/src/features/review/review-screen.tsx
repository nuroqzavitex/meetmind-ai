"use client"

import { GitBranch } from "lucide-react"
import { useMemo, useState } from "react"

import { PageHeader } from "@/components/page-header"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TopicTimeline } from "@/features/topics/topic-timeline"
import { useMeeting } from "@/features/meetings/hooks"
import { ApiError } from "@/lib/api-client"
import { ITEM_TYPES, ITEM_TYPE_LABEL, MEETING_STATUS_LABEL, fmtDate } from "@/lib/format"
import { ITEM_TYPE_STYLE } from "@/lib/item-style"
import { cn } from "@/lib/utils"
import { useItemAction, useItems } from "./hooks"
import { ItemCard } from "./item-card"
import { ReviewToolbar } from "./review-toolbar"
import { groupByType } from "./sort"
import { TranscriptPanel } from "./transcript-panel"

export function ReviewScreen({ meetingId }: { meetingId: string }) {
  const meeting = useMeeting(meetingId)
  const items = useItems(meetingId)
  const act = useItemAction(meetingId)
  const [highlight, setHighlight] = useState<{ id: string; nonce: number } | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)
  const grouped = useMemo(() => groupByType(items.data ?? []), [items.data])

  if (meeting.isPending || items.isPending)
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Đang tải…
      </p>
    )
  if (meeting.isError || items.isError)
    return <p className="text-sm text-destructive">Không tải được dữ liệu duyệt.</p>

  const readOnly = meeting.data.status !== "in_review"

  return (
    <div className="space-y-6">
      <PageHeader
        title={meeting.data.title}
        description={
          <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>Duyệt từng mục trước khi phát hành biên bản</span>
            {meeting.data.meeting_date && <span>· {fmtDate(meeting.data.meeting_date)}</span>}
            {meeting.data.project && <span>· {meeting.data.project}</span>}
          </span>
        }
      />
      {readOnly && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Cuộc họp đang ở trạng thái: {MEETING_STATUS_LABEL[meeting.data.status] ?? meeting.data.status}
        </div>
      )}
      <ReviewToolbar meetingId={meetingId} items={items.data} readOnly={readOnly} />
      {actionError && (
        <p role="alert" className="text-sm text-destructive">
          {actionError}
        </p>
      )}
      <div className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        <Tabs defaultValue={ITEM_TYPES[0]} className="min-w-0">
          <TabsList className="h-auto w-full flex-wrap group-data-horizontal/tabs:h-auto justify-start gap-1 rounded-xl bg-muted p-1">
            {ITEM_TYPES.map((t) => (
              <TabsTrigger key={t} value={t} className="flex-none gap-1.5 px-2.5 py-1.5">
                <span aria-hidden className={cn("size-2 rounded-full", ITEM_TYPE_STYLE[t].dot)} />
                {ITEM_TYPE_LABEL[t]} ({grouped[t].length})
              </TabsTrigger>
            ))}
            <TabsTrigger value="topics" className="flex-none gap-1.5 px-2.5 py-1.5">
              <GitBranch aria-hidden className="size-3.5" />
              Diễn biến chủ đề
            </TabsTrigger>
          </TabsList>
          {ITEM_TYPES.map((t) => (
            <TabsContent key={t} value={t} className="space-y-3">
              {grouped[t].length === 0 && (
                <p className="rounded-xl border border-dashed bg-card py-10 text-center text-sm text-muted-foreground">
                  Không có mục nào.
                </p>
              )}
              {grouped[t].map((item) => (
                <ItemCard
                  key={item.id}
                  item={item}
                  readOnly={readOnly}
                  pending={act.isPending && act.variables?.id === item.id}
                  onAction={(body) => {
                    const p = act.mutateAsync({ id: item.id, body })
                    // Edit errors are shown inline by the edit form, not in the banner.
                    if (body.action === "edit") {
                      return p.then((r) => {
                        setActionError(null)
                        return r
                      })
                    }
                    return p.then(
                      (r) => {
                        setActionError(null)
                        return r
                      },
                      (e: unknown) => {
                        setActionError(
                          e instanceof ApiError ? e.message : "Không cập nhật được mục.",
                        )
                        throw e
                      },
                    )
                  }}
                  onEvidenceClick={(id) => setHighlight((h) => ({ id, nonce: (h?.nonce ?? 0) + 1 }))}
                />
              ))}
            </TabsContent>
          ))}
          <TabsContent value="topics">
            <TopicTimeline
              meetingId={meetingId}
              onSeek={(id) => setHighlight((h) => ({ id, nonce: (h?.nonce ?? 0) + 1 }))}
            />
          </TabsContent>
        </Tabs>
        <div className="min-w-0 lg:sticky lg:top-20 lg:self-start">
          <TranscriptPanel utterances={meeting.data.utterances} highlightId={highlight?.id ?? null} nonce={highlight?.nonce} />
        </div>
      </div>
    </div>
  )
}
