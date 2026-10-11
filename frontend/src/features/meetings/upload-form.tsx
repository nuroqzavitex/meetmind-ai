"use client"

import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { useCreateMeeting } from "./hooks"
import { buildContext, validateDraft, type ContextDraft } from "./context-form"
import { JobProgress } from "./job-progress"

function today(): string {
  const d = new Date()
  const p = (n: number) => String(n).padStart(2, "0")
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

export function UploadForm() {
  const [draft, setDraft] = useState<ContextDraft>({
    title: "",
    meetingDate: today(),
    project: "",
    organizer: "",
    participantsText: "",
    glossaryText: "",
  })
  const [file, setFile] = useState<File | null>(null)
  const [errors, setErrors] = useState<string[]>([])
  const create = useCreateMeeting()

  const set = (k: keyof ContextDraft) => (e: { target: { value: string } }) =>
    setDraft((d) => ({ ...d, [k]: e.target.value }))

  function submit(e: React.FormEvent) {
    e.preventDefault()
    const errs = validateDraft(draft)
    if (!file) errs.push("Cần chọn file transcript")
    setErrors(errs)
    if (errs.length || !file) return
    const form = new FormData()
    form.append("file", file)
    form.append("context", JSON.stringify(buildContext(draft)))
    create.mutate(form)
  }

  if (create.data) {
    return (
      <div className="space-y-3">
        <h2 className="text-lg font-medium">Đang phân tích transcript</h2>
        <JobProgress
          jobId={create.data.job_id}
          meetingId={create.data.meeting_id}
          autoNavigate
        />
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="max-w-xl space-y-4" noValidate>
      <div className="space-y-1">
        <Label htmlFor="file">File transcript</Label>
        <Input
          id="file"
          type="file"
          accept=".txt,.srt,.vtt,.docx"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="title">Tiêu đề</Label>
        <Input id="title" maxLength={200} value={draft.title} onChange={set("title")} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="date">Ngày họp</Label>
        <Input id="date" type="date" value={draft.meetingDate} onChange={set("meetingDate")} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="project">Dự án</Label>
        <Input id="project" value={draft.project} onChange={set("project")} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="organizer">Người chủ trì</Label>
        <Input id="organizer" value={draft.organizer} onChange={set("organizer")} />
      </div>
      <div className="space-y-1">
        <Label htmlFor="participants">Người tham gia</Label>
        <Textarea
          id="participants"
          rows={4}
          placeholder={"Tên | vai trò | *\n(mỗi người một dòng, * đánh dấu người quyết định)"}
          value={draft.participantsText}
          onChange={set("participantsText")}
        />
      </div>
      <div className="space-y-1">
        <Label htmlFor="glossary">Thuật ngữ</Label>
        <Textarea
          id="glossary"
          rows={3}
          placeholder="Mỗi thuật ngữ một dòng"
          value={draft.glossaryText}
          onChange={set("glossaryText")}
        />
      </div>
      {errors.length > 0 && (
        <ul role="alert" className="text-sm text-destructive">
          {errors.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      )}
      {create.error && (
        <p role="alert" className="text-sm text-destructive">
          {create.error.message}
        </p>
      )}
      <Button type="submit" disabled={create.isPending}>
        Phân tích
      </Button>
    </form>
  )
}
