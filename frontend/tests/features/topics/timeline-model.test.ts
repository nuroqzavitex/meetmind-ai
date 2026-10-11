import { expect, test } from "vitest"

import { buildTimeline, finalSummary } from "@/features/topics/timeline-model"
import type { TopicOut } from "@/lib/types"

export const topic = {
  topic_id: "t1",
  question: "Chọn cơ sở dữ liệu nào?",
  deferred: false,
  ambiguous_decides: [],
  needs_confirmation: false,
  options: {
    Postgres: {
      label: "Postgres",
      state: "decided",
      superseded_by: null,
      decided_act: null,
      acts: [],
      history: [[135, "propose", "proposed"], [210, "decide", "decided"]],
    },
    MongoDB: {
      label: "MongoDB",
      state: "superseded",
      superseded_by: "Postgres",
      decided_act: null,
      acts: [],
      history: [[20, "propose", "proposed"], [210, "decide", "superseded"]],
    },
  },
} as unknown as TopicOut

test("buildTimeline orders events by time then option", () => {
  const ev = buildTimeline(topic)
  expect(ev.map((e) => [e.ts, e.option])).toEqual([
    [20, "MongoDB"], [135, "Postgres"], [210, "MongoDB"], [210, "Postgres"],
  ])
  expect(ev[0].tsText).toBe("00:00:20")
  expect(ev[2]).toMatchObject({ stateLabel: "Bị thay thế" })
  expect(ev[3]).toMatchObject({ actLabel: "Chốt", stateLabel: "Đã chốt" })
})

test("finalSummary", () => {
  expect(finalSummary(topic)).toEqual({
    decided: "Postgres",
    superseded: [{ label: "MongoDB", by: "Postgres" }],
    rejected: [],
  })
})
