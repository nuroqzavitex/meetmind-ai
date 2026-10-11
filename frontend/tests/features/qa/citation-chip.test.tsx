import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, test } from "vitest"

import { CitationChip } from "@/features/qa/citation-chip"

afterEach(cleanup)

export const cit = (ref = 1) => ({
  ref, meeting_id: "m1", title: "Họp tuần", date: "2026-03-05", ts: "00:12",
  speaker: "An", quote: "Dùng Postgres", utterance_id: "u0007",
})

test("renders title, ts, speaker as link to minutes with quote title", () => {
  render(<CitationChip citation={cit()} />)
  const a = screen.getByRole("link", { name: /Họp tuần · 00:12 · An/ })
  expect(a).toHaveAttribute("href", "/meetings/m1/minutes?u=u0007")
  expect(a).toHaveAttribute("title", "Dùng Postgres")
})

test("encodes ids in the href", () => {
  render(<CitationChip citation={{ ...cit(), meeting_id: "a/b", utterance_id: "u 1&x" }} />)
  expect(screen.getByRole("link")).toHaveAttribute("href", "/meetings/a%2Fb/minutes?u=u%201%26x")
})
