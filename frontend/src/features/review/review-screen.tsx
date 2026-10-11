"use client"

import { useMemo, useState } from "react"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { TopicTimeline } from "@/features/topics/topic-timeline"
import { useMeeting } from "@/features/meetings/hooks"
import { ApiError } from "@/lib/api-client"
import { ITEM_TYPES, ITEM_TYPE_LABEL, MEETING_STATUS_LABEL } from "@/lib/format"
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

  if (meeting.isPending || items.isPending) return <p className="text-sm">Đang tải…</p>
  if (meeting.isError || items.isError)
    return <p className="text-sm text-destructive">Không tải được dữ liệu duyệt.</p>

  const readOnly = meeting.data.status !== "in_review"

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">{meeting.data.title}</h1>
      {readOnly && (
        <div className="rounded-lg border bg-muted p-3 text-sm">
          Cuộc họp đang ở trạng thái: {MEETING_STATUS_LABEL[meeting.data.status] ?? meeting.data.status}
        </div>
      )}
      <ReviewToolbar meetingId={meetingId} items={items.data} readOnly={readOnly} />
      {actionError && (
        <p role="alert" className="text-sm text-destructive">
          {actionError}
        </p>
      )}
      <div className="grid gap-4 lg:grid-cols-2">
        <Tabs defaultValue={ITEM_TYPES[0]}>
          <TabsList className="h-auto flex-wrap">
            {ITEM_TYPES.map((t) => (
              <TabsTrigger key={t} value={t}>
                {ITEM_TYPE_LABEL[t]} ({grouped[t].length})
              </TabsTrigger>
            ))}
            <TabsTrigger value="topics">Diễn biến chủ đề</TabsTrigger>
          </TabsList>
          {ITEM_TYPES.map((t) => (
            <TabsContent key={t} value={t} className="space-y-3">
              {grouped[t].length === 0 && <p className="text-muted-foreground">Không có mục nào.</p>}
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
        <div className="lg:sticky lg:top-4 lg:self-start">
          <TranscriptPanel utterances={meeting.data.utterances} highlightId={highlight?.id ?? null} nonce={highlight?.nonce} />
        </div>
      </div>
    </div>
  )
}
