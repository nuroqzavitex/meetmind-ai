"use client"

import { Lightbulb, SearchX, SendHorizontal, Sparkles } from "lucide-react"
import { useState } from "react"

import { PageHeader } from "@/components/page-header"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import { AnswerText } from "./answer-text"
import { CitationChip } from "./citation-chip"
import { useAsk, useProjects } from "./hooks"

const SAMPLES = [
  "Dịch vụ thanh toán dùng cơ sở dữ liệu nào?",
  "Ai phụ trách dựng schema?",
  "Có quyết định nào bị thay đổi không?",
]

export function QaScreen() {
  const [question, setQuestion] = useState("")
  const [project, setProject] = useState("")
  const projects = useProjects()
  const ask = useAsk()

  const submit = (q: string) => {
    const text = q.trim()
    if (!text || ask.isPending) return
    ask.mutate(project ? { question: text, project } : { question: text })
  }

  const result = ask.data
  const refused = result && result.citations.length === 0

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title="Hỏi đáp"
        description="Hỏi về các cuộc họp đã phát hành của tổ chức. Mỗi câu trả lời kèm trích dẫn tới câu nói gốc."
      />

      <div className="space-y-4 rounded-2xl border bg-card p-5 shadow-sm">
        <label htmlFor="qa-question" className="text-sm font-semibold">
          Câu hỏi của bạn
        </label>
        <Textarea
          rows={3}
          placeholder="Ví dụ: Nhóm đã chốt dùng cơ sở dữ liệu nào cho dịch vụ thanh toán?"
          className="resize-none text-base"
          id="qa-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={1000}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing &&
              e.keyCode !== 229
            ) {
              e.preventDefault()
              submit(question)
            }
          }}
        />
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="qa-project" className="text-sm text-muted-foreground">
            Dự án
          </label>
          <select
            id="qa-project"
            value={project}
            onChange={(e) => setProject(e.target.value)}
            className="h-9 rounded-lg border border-input bg-background px-3 text-sm outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          >
            <option value="">Tất cả dự án</option>
            {projects.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <span className="hidden text-xs text-muted-foreground sm:inline">Enter để gửi · Shift+Enter xuống dòng</span>
          <Button size="lg" className="ml-auto px-5" onClick={() => submit(question)} disabled={ask.isPending}>
            <SendHorizontal aria-hidden />
            Hỏi
          </Button>
        </div>
      </div>
      <div className="space-y-2">
        <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          <Lightbulb className="size-3.5" aria-hidden />
          Câu hỏi gợi ý
        </p>
        <div className="flex flex-wrap gap-2">
          {SAMPLES.map((s) => (
            <Button
              key={s}
              variant="outline"
              size="sm"
              className="rounded-full"
              onClick={() => {
                setQuestion(s)
                submit(s)
              }}
            >
              {s}
            </Button>
          ))}
        </div>
      </div>

      {ask.isPending && (
        <p role="status" className="flex items-center gap-2 rounded-xl border bg-card p-4 text-sm text-muted-foreground shadow-xs">
          <Spinner /> Đang tìm câu trả lời…
        </p>
      )}
      {ask.isError && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {ask.error.message}
        </p>
      )}
      {result && !ask.isPending && (
        <section className="space-y-4">
          {refused ? (
            <div className="flex items-start gap-3 rounded-xl border border-dashed bg-card p-4 text-sm text-muted-foreground">
              <SearchX className="mt-0.5 size-4 shrink-0" aria-hidden />
              <span>{result.answer}</span>
            </div>
          ) : (
            <>
              <div className="rounded-2xl border bg-card p-5 shadow-sm">
                <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold tracking-wider text-primary uppercase">
                  <Sparkles className="size-3.5" aria-hidden />
                  Trả lời
                </p>
                <AnswerText answer={result.answer} citations={result.citations} />
              </div>
              <div className="space-y-2">
                <h2 className="text-sm font-semibold">Nguồn</h2>
                <ul className="space-y-2">
                  {result.citations.map((c) => (
                    <li key={c.ref} className="space-y-1.5 rounded-xl border bg-card p-3 text-sm shadow-xs">
                      <CitationChip citation={c} />
                      <p className="border-l-2 border-primary/30 pl-3 text-muted-foreground italic">{c.quote}</p>
                    </li>
                  ))}
                </ul>
              </div>
            </>
          )}
        </section>
      )}
    </div>
  )
}
