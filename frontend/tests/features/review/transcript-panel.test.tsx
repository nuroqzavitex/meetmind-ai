import { act, cleanup, render } from "@testing-library/react"
import { afterEach, expect, test, vi } from "vitest"
import { TranscriptPanel } from "@/features/review/transcript-panel"

afterEach(cleanup)

test("scrolls to and highlights the row", () => {
  const spy = vi.fn()
  Element.prototype.scrollIntoView = spy
  const utts = Array.from({ length: 200 }, (_, i) => ({
    id: `u${String(i).padStart(4, "0")}`, seq: i, speaker: "An", start: i * 10, end: null, text: `câu ${i}`,
  }))
  const { container, rerender } = render(<TranscriptPanel utterances={utts} highlightId={null} />)
  expect(spy).not.toHaveBeenCalled()
  rerender(<TranscriptPanel utterances={utts} highlightId="u0150" />)
  const row = container.querySelector("#utt-u0150")!
  expect(spy.mock.contexts[0]).toBe(row)
  expect(spy).toHaveBeenCalledWith({ block: "center" })
  expect(row.textContent).toContain("[00:25:00] An: câu 150")
  expect(row.className).toContain("bg-yellow")
})

test("same id with new nonce re-scrolls and re-highlights", () => {
  vi.useFakeTimers()
  const spy = vi.fn()
  Element.prototype.scrollIntoView = spy
  const utts = [{ id: "u1", seq: 1, speaker: "An", start: 0, end: null, text: "x" }]
  const { container, rerender } = render(<TranscriptPanel utterances={utts} highlightId="u1" nonce={1} />)
  expect(spy).toHaveBeenCalledTimes(1)
  act(() => { vi.advanceTimersByTime(2100) })
  expect(container.querySelector("#utt-u1")!.className).not.toContain("bg-yellow")
  rerender(<TranscriptPanel utterances={utts} highlightId="u1" nonce={2} />)
  expect(spy).toHaveBeenCalledTimes(2)
  expect(container.querySelector("#utt-u1")!.className).toContain("bg-yellow")
  vi.useRealTimers()
})
