"use client"

import { ScrollText } from "lucide-react"
import { useEffect, useState } from "react"

import { cn } from "@/lib/utils"
import { fmtSeconds } from "@/lib/format"
import type { Utterance } from "@/lib/types"

export function TranscriptPanel({
  utterances,
  highlightId,
  nonce = 0,
}: {
  utterances: Utterance[]
  highlightId: string | null
  /** Increment to re-trigger scroll + highlight for the same id. */
  nonce?: number
}) {
  const [expired, setExpired] = useState<string | null>(null)
  const key = highlightId ? `${highlightId}:${nonce}` : null

  useEffect(() => {
    if (!highlightId) return
    document.getElementById(`utt-${highlightId}`)?.scrollIntoView({ block: "center" })
    const timer = setTimeout(() => setExpired(key), 2000)
    return () => clearTimeout(timer)
  }, [highlightId, key])

  const active = highlightId && expired !== key ? highlightId : null

  return (
    <div className="max-h-[calc(100vh-7rem)] overflow-y-auto rounded-xl border bg-card text-sm shadow-xs">
      <h2 className="sticky top-0 z-10 flex items-center gap-2 border-b bg-card/95 px-4 py-3 font-semibold backdrop-blur">
        <ScrollText className="size-4 text-muted-foreground" aria-hidden />
        Transcript
        <span className="ml-auto text-xs font-normal text-muted-foreground">{utterances.length} câu</span>
      </h2>
      <div className="space-y-0.5 p-2">
        {utterances.length === 0 && <p className="p-2 text-muted-foreground">Chưa có transcript.</p>}
        {utterances.map((u) => (
          <p
            key={u.id}
            id={`utt-${u.id}`}
            className={cn(
              "rounded-lg px-2 py-1.5 leading-relaxed transition-colors",
              active === u.id ? "bg-yellow-200 dark:bg-yellow-900/50" : "hover:bg-muted/60",
            )}
          >
            <span className="font-mono text-xs text-muted-foreground">[{fmtSeconds(u.start)}]</span>{" "}
            <span className="font-semibold">{u.speaker}:</span> {u.text}
          </p>
        ))}
      </div>
    </div>
  )
}
