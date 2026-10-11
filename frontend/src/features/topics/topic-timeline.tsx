"use client"

import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Spinner } from "@/components/ui/spinner"
import type { TopicOut } from "@/lib/types"
import { cn } from "@/lib/utils"
import { useTopics } from "./hooks"
import { buildTimeline, finalSummary, type TimelineEvent } from "./timeline-model"

function findUtterance(topic: TopicOut, e: TimelineEvent): string | null {
  const opt = Object.values(topic.options).find((o) => o.label === e.option)
  const same = opt?.acts.filter((a) => a.start === e.ts) ?? []
  return (same.find((a) => a.act === e.act) ?? same[0])?.utterance_id ?? null
}

function TopicCard({ topic, onSeek }: { topic: TopicOut; onSeek?: (id: string) => void }) {
  const summary = finalSummary(topic)
  const events = buildTimeline(topic)
  const struck = new Set([...summary.superseded.map((s) => s.label), ...summary.rejected])
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-2">
          <span>{topic.question}</span>
          {topic.needs_confirmation && <Badge variant="destructive">Cần xác nhận</Badge>}
          {topic.deferred && <Badge variant="secondary">Chờ cấp trên</Badge>}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="space-y-1">
          <p className="font-medium">{summary.decided ? `Kết luận: ${summary.decided}` : "Chưa chốt"}</p>
          {summary.superseded.map((s) => (
            <p key={s.label} className="text-muted-foreground">
              Bị thay thế: {s.label} → {s.by ?? "?"}
            </p>
          ))}
        </div>
        <ol className="space-y-1 border-l pl-3">
          {events.map((e, i) => {
            const uid = onSeek ? findUtterance(topic, e) : null
            const decided = e.stateAfter === "decided"
            const body = (
              <>
                <span className="tabular-nums text-muted-foreground">{e.tsText}</span>{" "}
                <span className={cn(struck.has(e.option) && "line-through")}>{e.option}</span>:{" "}
                {e.actLabel} → {e.stateLabel}
              </>
            )
            const cls = cn("text-left", decided && "font-semibold")
            return (
              <li key={`${e.ts}-${e.option}-${i}`}>
                {uid ? (
                  <button type="button" className={cn(cls, "rounded-sm hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring")} onClick={() => onSeek?.(uid)}>
                    {body}
                  </button>
                ) : (
                  <span className={cls}>{body}</span>
                )}
              </li>
            )
          })}
        </ol>
      </CardContent>
    </Card>
  )
}

export function TopicTimeline({
  meetingId,
  onSeek,
}: {
  meetingId: string
  onSeek?: (utteranceId: string) => void
}) {
  const { data, isLoading, error } = useTopics(meetingId)
  if (isLoading) return <Spinner />
  if (error) return <p className="text-sm text-destructive">{error.message || "Không tải được chủ đề."}</p>
  if (!data || data.length === 0)
    return <p className="text-sm text-muted-foreground">Không có chủ đề nào cần theo dõi</p>
  return (
    <div className="space-y-3">
      {data.map((t) => (
        <TopicCard key={t.topic_id} topic={t} onSeek={onSeek} />
      ))}
    </div>
  )
}
