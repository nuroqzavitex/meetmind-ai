"use client"

import Link from "next/link"
import { useSearchParams } from "next/navigation"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { ItemCard } from "@/features/review/item-card"
import { useItems } from "@/features/review/hooks"
import { TranscriptPanel } from "@/features/review/transcript-panel"
import { useMeeting } from "@/features/meetings/hooks"
import { ITEM_TYPES, ITEM_TYPE_LABEL, fmtDate } from "@/lib/format"
import { useApi } from "@/lib/use-api"
import { ReopenDialog } from "./reopen-dialog"
import { ReportDialog } from "./report-dialog"

const noop = () => {}

export function MinutesView({ meetingId }: { meetingId: string }) {
  const { download } = useApi()
  const meeting = useMeeting(meetingId)
  const items = useItems(meetingId)
  const initial = useSearchParams().get("u")
  const [open, setOpen] = useState(!!initial)
  const [hl, setHl] = useState<{ id: string | null; nonce: number }>({ id: initial, nonce: 1 })
  const [dlError, setDlError] = useState<string | null>(null)

  if (meeting.isPending || items.isPending) return <Spinner />
  if (meeting.isError || items.isError || !meeting.data || !items.data) {
    return <p role="alert">Không tải được biên bản.</p>
  }
  const m = meeting.data

  const shown = items.data.filter(
    (i) => (i.review_state === "approved" || i.review_state === "edited") && i.status !== "superseded",
  )
  const onEvidence = (id: string) => {
    setOpen(true)
    setHl((h) => ({ id, nonce: h.nonce + 1 }))
  }
  const dl = (format: "md" | "json") => {
    setDlError(null)
    download(`/meetings/${meetingId}/export?format=${format}`, `bien-ban.${format}`).catch(() =>
      setDlError("Không tải được tệp."),
    )
  }

  return (
    <div className="space-y-6">
      {m.status !== "published" && (
        <div role="status" className="rounded-lg border border-yellow-400 bg-yellow-50 p-3 text-sm dark:bg-yellow-950/30">
          <span>Biên bản đang được chỉnh sửa lại</span>{" "}
          <Link className="underline" href={`/meetings/${meetingId}/review`}>
            Đến màn hình duyệt
          </Link>
        </div>
      )}
      <header className="space-y-1">
        <h1 className="text-2xl font-semibold">{m.title}</h1>
        <p className="text-sm text-muted-foreground">
          {m.meeting_date ? fmtDate(m.meeting_date) : ""}
          {m.project ? ` · ${m.project}` : ""}
          {m.published_at ? ` · Phát hành: ${fmtDate(m.published_at)}` : ""}
        </p>
        <div className="flex gap-2 pt-1">
          <Button variant="outline" size="sm" onClick={() => dl("md")}>
            Tải .md
          </Button>
          <Button variant="outline" size="sm" onClick={() => dl("json")}>
            Tải .json
          </Button>
        </div>
        {dlError && (
          <p role="alert" className="text-sm text-destructive">
            {dlError}
          </p>
        )}
      </header>

      {ITEM_TYPES.map((t) => {
        const group = shown.filter((i) => i.type === t)
        if (group.length === 0) return null
        return (
          <section key={t} className="space-y-3">
            <h2 className="text-lg font-medium">{ITEM_TYPE_LABEL[t]}</h2>
            {group.map((i) => (
              <div key={i.id} className="space-y-1">
                <ItemCard item={i} readOnly onAction={noop} onEvidenceClick={onEvidence} />
                {m.status === "published" && (
                  <div className="flex gap-2">
                    <ReportDialog itemId={i.id} />
                    <ReopenDialog itemId={i.id} meetingId={meetingId} />
                  </div>
                )}
              </div>
            ))}
          </section>
        )
      })}
      {shown.length === 0 && <p className="text-muted-foreground">Chưa có mục nào trong biên bản.</p>}

      <section className="space-y-2">
        <Button variant="outline" size="sm" onClick={() => setOpen((o) => !o)}>
          {open ? "Ẩn transcript" : "Xem transcript"}
        </Button>
        {open && <TranscriptPanel utterances={m.utterances} highlightId={hl.id} nonce={hl.nonce} />}
      </section>
    </div>
  )
}
