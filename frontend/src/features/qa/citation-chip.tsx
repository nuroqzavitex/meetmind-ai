import Link from "next/link"

import type { Citation } from "@/lib/types"

export function CitationChip({ citation: c }: { citation: Citation }) {
  return (
    <Link
      href={`/meetings/${encodeURIComponent(c.meeting_id)}/minutes?u=${encodeURIComponent(c.utterance_id)}`}
      title={c.quote}
      className="mx-0.5 inline-block rounded-md bg-accent px-1.5 py-0.5 align-baseline text-xs font-medium text-accent-foreground ring-1 ring-primary/15 transition-colors ring-inset hover:bg-primary hover:text-primary-foreground"
    >
      {`[${c.title} · ${c.ts} · ${c.speaker}]`}
    </Link>
  )
}
