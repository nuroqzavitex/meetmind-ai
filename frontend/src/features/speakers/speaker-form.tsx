"use client"

import { Sparkles, UserRound } from "lucide-react"
import Link from "next/link"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import { JobProgress } from "@/features/meetings/job-progress"
import type { SpeakerOut } from "@/lib/types"
import { useAssignSpeakers, useSpeakers } from "./hooks"

type Row = { name: string; isDecisionMaker: boolean }

// Mirrors the backend rule: names end up in "[hh:mm:ss] Name: text" transcript lines.
const NAME_RE = /^[\p{L}][^:\n]{0,39}$/u

/** Client-side checks before submitting; the backend enforces the same rules. */
export function validateRows(speakers: SpeakerOut[], rows: Record<string, Row>): string[] {
  const errors: string[] = []
  const seen = new Set<string>()
  for (const s of speakers) {
    const name = (rows[s.label]?.name ?? "").trim().replace(/\s+/g, " ")
    if (!name) errors.push(`Chưa nhập tên cho ${s.label}`)
    else if (!NAME_RE.test(name))
      errors.push(`Tên của ${s.label} phải bắt đầu bằng chữ cái, tối đa 40 ký tự, không chứa dấu ':'`)
    else if (seen.has(name.toLocaleLowerCase("vi"))) errors.push(`Tên "${name}" bị trùng`)
    else seen.add(name.toLocaleLowerCase("vi"))
  }
  return errors
}

export function SpeakerForm({ meetingId }: { meetingId: string }) {
  const speakers = useSpeakers(meetingId)
  const assign = useAssignSpeakers(meetingId)
  const [rows, setRows] = useState<Record<string, Row>>({})
  const [errors, setErrors] = useState<string[]>([])

  if (speakers.isPending)
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Đang tải…
      </p>
    )
  if (speakers.isError)
    return (
      <div role="alert" className="space-y-2 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        <p>{speakers.error.message}</p>
        <Link href="/" className="font-medium underline">
          Về danh sách cuộc họp
        </Link>
      </div>
    )

  if (assign.data) {
    return (
      <div className="max-w-2xl space-y-3 rounded-xl border bg-card p-6 shadow-xs">
        <h2 className="text-lg font-semibold">Đang phân tích cuộc họp</h2>
        <JobProgress jobId={assign.data.job_id} meetingId={meetingId} autoNavigate />
      </div>
    )
  }

  const list = speakers.data
  const row = (label: string): Row => rows[label] ?? { name: "", isDecisionMaker: false }
  const update = (label: string, patch: Partial<Row>) =>
    setRows((r) => ({ ...r, [label]: { ...row(label), ...patch } }))

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const errs = validateRows(list, rows)
    setErrors(errs)
    if (errs.length) return
    assign.mutate(
      list.map((s) => ({
        label: s.label,
        name: row(s.label).name.trim().replace(/\s+/g, " "),
        is_decision_maker: row(s.label).isDecisionMaker,
      })),
    )
  }

  return (
    <form onSubmit={submit} className="max-w-3xl space-y-4" noValidate>
      {list.map((s, i) => {
        const id = `speaker-${i}`
        return (
          <section key={s.label} className="space-y-4 rounded-xl border bg-card p-5 shadow-xs">
            <div className="flex items-center gap-3">
              <span className="flex size-9 items-center justify-center rounded-full bg-accent text-accent-foreground">
                <UserRound className="size-4" aria-hidden />
              </span>
              <div>
                <h2 className="font-semibold">{s.label}</h2>
                <p className="text-xs text-muted-foreground">{s.count} câu</p>
              </div>
            </div>
            <ul className="space-y-1.5">
              {s.samples.map((t, j) => (
                <li key={j} className="rounded-lg border-l-2 border-primary/30 bg-muted/60 px-3 py-2 text-sm italic">
                  &quot;{t}&quot;
                </li>
              ))}
            </ul>
            <div className="flex flex-wrap items-end gap-4">
              <div className="min-w-56 flex-1 space-y-1.5">
                <Label htmlFor={`${id}-name`}>Tên của {s.label}</Label>
                <Input
                  id={`${id}-name`}
                  maxLength={40}
                  value={row(s.label).name}
                  onChange={(e) => update(s.label, { name: e.target.value })}
                />
              </div>
              <label className="flex items-center gap-2 pb-2 text-sm">
                <Checkbox
                  checked={row(s.label).isDecisionMaker}
                  onCheckedChange={(v) => update(s.label, { isDecisionMaker: v === true })}
                  aria-label={`${s.label} là người quyết định`}
                />
                Người quyết định
              </label>
            </div>
          </section>
        )
      })}
      {errors.length > 0 && (
        <ul role="alert" className="list-inside list-disc rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {errors.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      )}
      {assign.error && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {assign.error.message}
        </p>
      )}
      <div className="flex justify-end">
        <Button type="submit" size="lg" className="px-5" disabled={assign.isPending}>
          <Sparkles aria-hidden />
          Phân tích
        </Button>
      </div>
    </form>
  )
}
