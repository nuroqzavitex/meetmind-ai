import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, expect, test } from "vitest"

import { AnswerText } from "@/features/qa/answer-text"

afterEach(cleanup)

const c = {
  ref: 1, meeting_id: "m1", title: "Họp tuần", date: "2026-03-05", ts: "00:12",
  speaker: "An", quote: "q", utterance_id: "u0007",
}

test("replaces known marker with a chip", () => {
  const { container } = render(<AnswerText answer="Dùng Postgres [1]." citations={[c]} />)
  expect(screen.getAllByRole("link")).toHaveLength(1)
  expect(container.textContent).toContain("Dùng Postgres ")
  expect(container.textContent).not.toContain("[1]")
})

test("unknown marker stays text", () => {
  render(<AnswerText answer="Ý kiến [9]." citations={[c]} />)
  expect(screen.queryAllByRole("link")).toHaveLength(0)
  expect(screen.getByText(/\[9\]/)).toBeInTheDocument()
})
