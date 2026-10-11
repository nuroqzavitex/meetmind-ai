"use client"

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
    <div className="max-h-[calc(100vh-8rem)] overflow-y-auto rounded-lg border p-3 text-sm">
      <h2 className="mb-2 font-medium">Transcript</h2>
      {utterances.length === 0 && <p className="text-muted-foreground">Chưa có transcript.</p>}
      {utterances.map((u) => (
        <p
          key={u.id}
          id={`utt-${u.id}`}
          className={cn("rounded px-1 py-0.5", active === u.id && "bg-yellow-200 dark:bg-yellow-900/50")}
        >
          [{fmtSeconds(u.start)}] {u.speaker}: {u.text}
        </p>
      ))}
    </div>
  )
}
