import Link from "next/link"

import type { Citation } from "@/lib/types"

export function CitationChip({ citation: c }: { citation: Citation }) {
  return (
    <Link
      href={`/meetings/${encodeURIComponent(c.meeting_id)}/minutes?u=${encodeURIComponent(c.utterance_id)}`}
      title={c.quote}
      className="mx-0.5 inline-block rounded-md border bg-muted px-1.5 py-0.5 align-baseline text-xs text-foreground hover:bg-accent"
    >
      {`[${c.title} · ${c.ts} · ${c.speaker}]`}
    </Link>
  )
}
