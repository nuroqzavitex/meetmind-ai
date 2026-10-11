import type { Citation } from "@/lib/types"
import { CitationChip } from "./citation-chip"

export function AnswerText({ answer, citations }: { answer: string; citations: Citation[] }) {
  const parts = answer.split(/(\[\d+\])/g)
  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      {parts.map((part, i) => {
        const m = /^\[(\d+)\]$/.exec(part)
        const c = m ? citations.find((x) => x.ref === Number(m[1])) : undefined
        return c ? <CitationChip key={i} citation={c} /> : <span key={i}>{part}</span>
      })}
    </p>
  )
}
