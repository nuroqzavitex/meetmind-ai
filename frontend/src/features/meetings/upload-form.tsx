"use client"

import { FileCheck2, Sparkles, UploadCloud } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"
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
      <div className="max-w-2xl space-y-4 rounded-xl border bg-card p-6 shadow-xs">
        <div className="flex items-center gap-3">
          <span className="flex size-10 items-center justify-center rounded-lg bg-accent text-accent-foreground">
            <Sparkles className="size-5" aria-hidden />
          </span>
          <div>
            <h2 className="text-lg font-semibold">Đang phân tích transcript</h2>
            <p className="text-sm text-muted-foreground">Xong sẽ tự chuyển sang màn hình duyệt.</p>
          </div>
        </div>
        <JobProgress
          jobId={create.data.job_id}
          meetingId={create.data.meeting_id}
          autoNavigate
        />
      </div>
    )
  }

  return (
    <form onSubmit={submit} className="max-w-3xl space-y-6" noValidate>
      <section className="space-y-3 rounded-xl border bg-card p-6 shadow-xs">
        <Label htmlFor="file" className="text-base font-semibold">File transcript</Label>
        <label
          htmlFor="file"
          className={cn(
            "flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed px-6 py-8 text-center transition-colors hover:border-primary/60 hover:bg-accent/40",
            file && "border-primary/50 bg-accent/40",
          )}
        >
          <span className="flex size-11 items-center justify-center rounded-full bg-accent text-accent-foreground">
            {file ? <FileCheck2 className="size-5" aria-hidden /> : <UploadCloud className="size-5" aria-hidden />}
          </span>
          <span className="font-medium">{file ? file.name : "Bấm để chọn file"}</span>
          <span className="text-xs text-muted-foreground">Hỗ trợ .txt, .srt, .vtt, .docx · tối đa 5 MB</span>
        </label>
        <Input
          id="file"
          type="file"
          accept=".txt,.srt,.vtt,.docx"
          className="sr-only"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </section>

      <section className="space-y-4 rounded-xl border bg-card p-6 shadow-xs">
        <h2 className="text-base font-semibold">Thông tin cuộc họp</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="title">Tiêu đề</Label>
            <Input id="title" maxLength={200} value={draft.title} onChange={set("title")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="date">Ngày họp</Label>
            <Input id="date" type="date" value={draft.meetingDate} onChange={set("meetingDate")} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="project">Dự án</Label>
            <Input id="project" value={draft.project} onChange={set("project")} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor="organizer">Người chủ trì</Label>
            <Input id="organizer" value={draft.organizer} onChange={set("organizer")} />
          </div>
        </div>
      </section>

      <section className="space-y-4 rounded-xl border bg-card p-6 shadow-xs">
        <div>
          <h2 className="text-base font-semibold">Ngữ cảnh cho AI</h2>
          <p className="text-sm text-muted-foreground">
            Giúp xác định ai có quyền chốt quyết định và nhận đúng thuật ngữ của nhóm.
          </p>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="participants">Người tham gia</Label>
          <Textarea
            id="participants"
            rows={4}
            placeholder={"Tên | vai trò | *\n(mỗi người một dòng, * đánh dấu người quyết định)"}
            value={draft.participantsText}
            onChange={set("participantsText")}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="glossary">Thuật ngữ</Label>
          <Textarea
            id="glossary"
            rows={3}
            placeholder="Mỗi thuật ngữ một dòng"
            value={draft.glossaryText}
            onChange={set("glossaryText")}
          />
        </div>
      </section>

      {errors.length > 0 && (
        <ul role="alert" className="list-inside list-disc rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {errors.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      )}
      {create.error && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {create.error.message}
        </p>
      )}
      <div className="flex justify-end">
        <Button type="submit" size="lg" className="px-5" disabled={create.isPending}>
          <Sparkles aria-hidden />
          Phân tích
        </Button>
      </div>
    </form>
  )
}
