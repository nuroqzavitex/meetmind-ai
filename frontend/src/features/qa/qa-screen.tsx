"use client"

import { useState } from "react"

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
      <h1 className="text-2xl font-semibold">Hỏi đáp</h1>

      <div className="space-y-3">
        <label htmlFor="qa-question" className="text-sm font-medium">
          Câu hỏi của bạn
        </label>
        <Textarea
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
          <label htmlFor="qa-project" className="text-sm">
            Dự án
          </label>
          <select
            id="qa-project"
            value={project}
            onChange={(e) => setProject(e.target.value)}
            className="h-8 rounded-lg border border-input bg-transparent px-2 text-sm"
          >
            <option value="">Tất cả dự án</option>
            {projects.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <Button onClick={() => submit(question)} disabled={ask.isPending}>
            Hỏi
          </Button>
        </div>
        <div className="flex flex-wrap gap-2">
          {SAMPLES.map((s) => (
            <Button
              key={s}
              variant="outline"
              size="sm"
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
        <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Đang tìm câu trả lời…
        </p>
      )}
      {ask.isError && (
        <p role="alert" className="text-sm text-destructive">
          {ask.error.message}
        </p>
      )}
      {result && !ask.isPending && (
        <section className="space-y-4">
          {refused ? (
            <div className="rounded-lg border bg-muted p-4 text-sm text-muted-foreground">{result.answer}</div>
          ) : (
            <>
              <AnswerText answer={result.answer} citations={result.citations} />
              <div className="space-y-2">
                <h2 className="text-sm font-semibold">Nguồn</h2>
                <ul className="space-y-2">
                  {result.citations.map((c) => (
                    <li key={c.ref} className="text-sm">
                      <CitationChip citation={c} />
                      <span className="text-muted-foreground">{c.quote}</span>
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
