import { AlertTriangle } from "lucide-react"

import type { Hold } from "@/lib/types"
import { cn } from "@/lib/utils"

/** Why the analysis held a decision or task back, in the reviewer's words. */
export const HOLD_INFO: Record<Hold["reason"], { label: string; why: string }> = {
  declined: {
    label: "Người nhận từ chối",
    why: "Người được giao đã từ chối ngay sau đó, nên đây chưa phải việc có người làm.",
  },
  conditional: {
    label: "Có điều kiện",
    why: "Việc chỉ xảy ra khi điều kiện được đáp ứng, chưa phải việc chắc chắn.",
  },
  negation: {
    label: "Có thể hiểu ngược ý",
    why: "Câu chốt mang ý phủ định nhưng kết luận AI rút ra lại không. Kiểm tra lại trước khi phát hành.",
  },
  waiting: {
    label: "Chỉ là chờ phản hồi",
    why: "Người nói chỉ chờ người khác báo lại, không nhận việc gì.",
  },
  tentative: {
    label: "Mới là gợi ý",
    why: "Câu nói còn lưỡng lự hoặc chỉ gợi ý, chưa ai cam kết.",
  },
  no_owner: {
    label: "Chưa có người nhận",
    why: "Không ai được giao hoặc tự nhận việc này.",
  },
}

/** Split `quote` around the first occurrence of `phrase` so it can be highlighted. */
export function splitPhrase(quote: string, phrase?: string | null): [string, string, string] {
  if (!phrase) return [quote, "", ""]
  const at = quote.indexOf(phrase)
  if (at < 0) return [quote, "", ""]
  return [quote.slice(0, at), phrase, quote.slice(at + phrase.length)]
}

export function HoldQuote({ hold, className }: { hold: Hold; className?: string }) {
  const [before, match, after] = splitPhrase(hold.quote, hold.phrase)
  return (
    <p className={cn("text-sm leading-relaxed", className)}>
      {(hold.ts || hold.speaker) && (
        <span className="mr-1.5 font-mono text-xs text-muted-foreground">
          [{[hold.ts, hold.speaker].filter(Boolean).join(" · ")}]
        </span>
      )}
      <span className="italic">
        &quot;{before}
        {match && (
          <mark className="rounded bg-amber-200 px-0.5 font-semibold not-italic text-amber-950 dark:bg-amber-400/40 dark:text-amber-50">
            {match}
          </mark>
        )}
        {after}&quot;
      </span>
    </p>
  )
}

/** "Why is this not settled" box shown on an item card. */
export function HoldNote({ hold }: { hold: Hold }) {
  const info = HOLD_INFO[hold.reason]
  return (
    <div className="space-y-1.5 rounded-lg border border-amber-200 bg-amber-50/70 px-3 py-2 dark:border-amber-500/30 dark:bg-amber-950/30">
      <p className="flex items-center gap-1.5 text-sm font-medium text-amber-900 dark:text-amber-200">
        <AlertTriangle aria-hidden className="size-4" />
        Chưa chốt · {info.label}
      </p>
      <p className="text-sm text-amber-900/80 dark:text-amber-100/80">{info.why}</p>
      <HoldQuote hold={hold} />
    </div>
  )
}
