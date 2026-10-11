"use client"

import { useQueryClient } from "@tanstack/react-query"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { fmtPercent, STEP_LABEL } from "@/lib/format"
import { useJob, useReanalyze } from "./hooks"

export function JobProgress({
  jobId,
  meetingId,
  autoNavigate = false,
}: {
  jobId: string
  meetingId: string
  autoNavigate?: boolean
}) {
  const [currentId, setCurrentId] = useState(jobId)
  const router = useRouter()
  const qc = useQueryClient()
  const { data: job, error: jobError, refetch } = useJob(currentId)
  const reanalyze = useReanalyze(meetingId)
  const status = job?.status
  const reviewHref = `/meetings/${meetingId}/review`

  useEffect(() => {
    setCurrentId(jobId)
  }, [jobId])

  useEffect(() => {
    if (status === "succeeded" || status === "failed") {
      qc.invalidateQueries({ queryKey: ["meetings"] })
      qc.invalidateQueries({ queryKey: ["meeting", meetingId] })
    }
    if (status === "succeeded") {
      qc.invalidateQueries({ queryKey: ["items", meetingId] })
      qc.invalidateQueries({ queryKey: ["topics", meetingId] })
    }
    if (status === "succeeded" && autoNavigate) router.push(reviewHref)
  }, [status, qc, meetingId, router, reviewHref, autoNavigate])

  if (!job && jobError) {
    return (
      <div role="alert" className="space-y-2 text-sm">
        <p className="text-destructive">{jobError.message}</p>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Thử lại
        </Button>
      </div>
    )
  }
  if (!job) return <p className="text-sm text-muted-foreground">Đang tải tiến độ…</p>

  const stepLabel = job.step ? (STEP_LABEL[job.step] ?? job.step) : "Bắt đầu"

  if (job.status === "failed") {
    return (
      <div
        role="alert"
        className="space-y-2 rounded-lg border border-destructive/40 bg-destructive/10 p-3 text-sm"
      >
        <p className="font-medium">
          Phân tích thất bại ở bước: <span>{stepLabel}</span>
        </p>
        {job.error && <p>{job.error}</p>}
        <Button
          variant="outline"
          disabled={reanalyze.isPending}
          onClick={() =>
            reanalyze.mutate(undefined, { onSuccess: (r) => setCurrentId(r.job_id) })
          }
        >
          Phân tích lại
        </Button>
        {reanalyze.error && <p>{reanalyze.error.message}</p>}
      </div>
    )
  }

  if (job.status === "succeeded") {
    return (
      <div className="space-y-2 text-sm">
        <p>Phân tích hoàn tất</p>
        <Link
          href={reviewHref}
          className="font-medium text-primary underline-offset-4 hover:underline"
        >
          Bắt đầu duyệt
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-1 text-sm">
      <div className="flex justify-between">
        <span>{stepLabel}</span>
        <span>{fmtPercent(job.progress)}</span>
      </div>
      <div
        role="progressbar"
        aria-label="Tiến độ phân tích"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(job.progress * 100)}
        className="h-2 overflow-hidden rounded-full bg-muted"
      >
        <div
          className="h-full bg-primary transition-all"
          style={{ width: fmtPercent(job.progress) }}
        />
      </div>
    </div>
  )
}
