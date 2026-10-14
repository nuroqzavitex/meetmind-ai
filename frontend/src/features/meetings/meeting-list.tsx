"use client"

import { CalendarDays, ChevronRight, FileText, Filter, FolderKanban, Inbox, Search } from "lucide-react"
import Link from "next/link"
import { useEffect, useState } from "react"

import { Button, buttonVariants } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { fmtDate, MEETING_STATUS_LABEL } from "@/lib/format"
import type { MeetingSummary } from "@/lib/types"
import { useMeeting, useMeetings, useReanalyze } from "./hooks"
import { JobProgress } from "./job-progress"
import { StatusBadge } from "./status-badge"

function FailedInfo({ id }: { id: string }) {
  const { data } = useMeeting(id)
  const reanalyze = useReanalyze(id)
  const [jobId, setJobId] = useState<string | null>(null)
  if (jobId) return <JobProgress jobId={jobId} meetingId={id} />
  return (
    <div className="space-y-2 text-sm">
      {data?.latest_job?.error && <p className="text-destructive">{data.latest_job.error}</p>}
      <Button
        variant="outline"
        size="sm"
        disabled={reanalyze.isPending}
        onClick={() => reanalyze.mutate(undefined, { onSuccess: (r) => setJobId(r.job_id) })}
      >
        Phân tích lại
      </Button>
    </div>
  )
}

function AnalyzingInfo({ id }: { id: string }) {
  const { data } = useMeeting(id)
  const reanalyze = useReanalyze(id)
  const [jobId, setJobId] = useState<string | null>(null)
  const activeJob = jobId ?? data?.active_job_id ?? null
  return (
    <div className="space-y-2">
      {activeJob && <JobProgress jobId={activeJob} meetingId={id} />}
      {/* A stuck job cannot be detected client-side; the backend rejects (409) while it is fresh. */}
      <Button
        variant="outline"
        size="sm"
        disabled={reanalyze.isPending}
        onClick={() => reanalyze.mutate(undefined, { onSuccess: (r) => setJobId(r.job_id) })}
      >
        Phân tích lại
      </Button>
      {reanalyze.error && (
        <p role="alert" className="text-sm text-destructive">
          {reanalyze.error.message}
        </p>
      )}
    </div>
  )
}

function MeetingRow({ m }: { m: MeetingSummary }) {
  const href =
    m.status === "in_review"
      ? `/meetings/${m.id}/review`
      : m.status === "published"
        ? `/meetings/${m.id}/minutes`
        : m.status === "awaiting_speakers"
          ? `/meetings/${m.id}/speakers`
          : null
  const title = <span className="font-semibold">{m.title}</span>
  return (
    <li className="group space-y-3 rounded-xl border bg-card p-4 shadow-xs transition-shadow hover:shadow-md">
      <div className="flex flex-wrap items-center gap-3">
        <span
          aria-hidden
          className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-foreground"
        >
          <FileText className="size-5" />
        </span>
        <div className="min-w-0 flex-1">
          {href ? (
            <Link href={href} className="hover:text-primary">
              {title}
            </Link>
          ) : (
            title
          )}
          <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <CalendarDays className="size-3.5" aria-hidden />
              {fmtDate(m.meeting_date)}
            </span>
            {m.project ? (
              <span className="inline-flex items-center gap-1">
                <FolderKanban className="size-3.5" aria-hidden />
                {m.project}
              </span>
            ) : null}
          </p>
        </div>
        <StatusBadge status={m.status} />
        {href && (
          <Link
            href={href}
            aria-hidden
            tabIndex={-1}
            className="hidden text-muted-foreground transition-colors group-hover:text-primary sm:block"
          >
            <ChevronRight className="size-5" />
          </Link>
        )}
      </div>
      {(m.status === "analyzing" || m.status === "transcribing") && <AnalyzingInfo id={m.id} />}
      {m.status === "failed" && <FailedInfo id={m.id} />}
    </li>
  )
}

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

export function MeetingList() {
  const [status, setStatus] = useState("")
  const [project, setProject] = useState("")
  const debouncedProject = useDebounced(project.trim(), 300)
  const { data, isPending, error } = useMeetings({
    ...(status ? { status } : {}),
    ...(debouncedProject ? { project: debouncedProject } : {}),
  })

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-3 shadow-xs">
        <Filter className="ml-1 size-4 text-muted-foreground" aria-hidden />
        <select
          aria-label="Lọc theo trạng thái"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="h-9 rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
        >
          <option value="">Tất cả trạng thái</option>
          {Object.entries(MEETING_STATUS_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
          <Input
            aria-label="Lọc theo dự án"
            placeholder="Dự án"
            className="h-9 w-56 pl-8"
            value={project}
            onChange={(e) => setProject(e.target.value)}
          />
        </div>
        {data && <span className="ml-auto pr-1 text-sm text-muted-foreground">{data.length} cuộc họp</span>}
      </div>
      {isPending && (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Đang tải…
        </p>
      )}
      {error && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {error.message}
        </p>
      )}
      {data && data.length === 0 && (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed bg-card px-6 py-14 text-center">
          <span className="flex size-12 items-center justify-center rounded-full bg-accent text-accent-foreground">
            <Inbox className="size-6" aria-hidden />
          </span>
          <p className="text-muted-foreground">Chưa có cuộc họp nào. Tải transcript đầu tiên lên nhé.</p>
          <Link href="/meetings/new" className={buttonVariants()}>
            Tải transcript
          </Link>
        </div>
      )}
      {data && data.length > 0 && (
        <ul className="space-y-3">
          {data.map((m) => (
            <MeetingRow key={m.id} m={m} />
          ))}
        </ul>
      )}
    </div>
  )
}
