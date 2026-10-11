"use client"

import Link from "next/link"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
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
        : null
  const title = <span className="font-medium">{m.title}</span>
  return (
    <li className="space-y-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          {href ? (
            <Link href={href} className="hover:underline">
              {title}
            </Link>
          ) : (
            title
          )}
          <p className="text-sm text-muted-foreground">
            {fmtDate(m.meeting_date)}
            {m.project ? ` · ${m.project}` : ""}
          </p>
        </div>
        <StatusBadge status={m.status} />
      </div>
      {m.status === "analyzing" && <AnalyzingInfo id={m.id} />}
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
      <div className="flex flex-wrap items-end gap-3">
        <select
          aria-label="Lọc theo trạng thái"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
        >
          <option value="">Tất cả trạng thái</option>
          {Object.entries(MEETING_STATUS_LABEL).map(([k, v]) => (
            <option key={k} value={k}>
              {v}
            </option>
          ))}
        </select>
        <Input
          aria-label="Lọc theo dự án"
          placeholder="Dự án"
          className="w-48"
          value={project}
          onChange={(e) => setProject(e.target.value)}
        />
        <Link
          href="/meetings/new"
          className="ml-auto text-sm font-medium text-primary hover:underline"
        >
          Tải transcript mới
        </Link>
      </div>
      {isPending && <p className="text-sm text-muted-foreground">Đang tải…</p>}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error.message}
        </p>
      )}
      {data && data.length === 0 && (
        <div className="space-y-2 py-8 text-center">
          <p>Chưa có cuộc họp nào. Tải transcript đầu tiên lên nhé.</p>
          <Link href="/meetings/new" className="text-sm font-medium text-primary hover:underline">
            Tải transcript
          </Link>
        </div>
      )}
      {data && data.length > 0 && (
        <ul className="space-y-2">
          {data.map((m) => (
            <MeetingRow key={m.id} m={m} />
          ))}
        </ul>
      )}
    </div>
  )
}
