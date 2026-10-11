import { fmtSeconds } from "@/lib/format"
import type { TopicOut } from "@/lib/types"

export type TimelineEvent = {
  ts: number
  tsText: string
  option: string
  act: string
  actLabel: string
  stateAfter: string
  stateLabel: string
}

export const ACT_LABEL: Record<string, string> = {
  propose: "Đề xuất",
  support: "Ủng hộ",
  object: "Phản đối",
  amend: "Sửa đổi",
  decide: "Chốt",
  reject: "Bác",
  defer: "Hoãn",
  reopen: "Mở lại",
}

export const STATE_LABEL: Record<string, string> = {
  proposed: "Đề xuất",
  discussed: "Đang bàn",
  decided: "Đã chốt",
  rejected: "Bị bác",
  superseded: "Bị thay thế",
  open: "Còn mở",
}

export function buildTimeline(topic: TopicOut): TimelineEvent[] {
  const events: TimelineEvent[] = []
  for (const [key, opt] of Object.entries(topic.options)) {
    const option = opt.label || key
    for (const [ts, act, stateAfter] of opt.history) {
      events.push({
        ts,
        tsText: fmtSeconds(ts),
        option,
        act,
        actLabel: ACT_LABEL[act] ?? act,
        stateAfter,
        stateLabel: STATE_LABEL[stateAfter] ?? stateAfter,
      })
    }
  }
  return events.sort((a, b) => a.ts - b.ts || a.option.localeCompare(b.option))
}

export function finalSummary(topic: TopicOut): {
  decided: string | null
  superseded: { label: string; by: string | null }[]
  rejected: string[]
} {
  const opts = Object.values(topic.options)
  const decided = opts.find((o) => o.state === "decided")
  const by = decided?.label ?? null
  return {
    decided: decided?.label ?? null,
    superseded: opts
      .filter((o) => o.state === "superseded")
      .map((o) => ({ label: o.label, by: o.superseded_by ?? by })),
    rejected: opts.filter((o) => o.state === "rejected").map((o) => o.label),
  }
}
