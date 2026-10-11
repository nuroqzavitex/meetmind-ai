import type { MeetingContextIn, Participant } from "@/lib/types"

export type ContextDraft = {
  title: string
  meetingDate: string
  project: string
  organizer: string
  participantsText: string
  glossaryText: string
}

const lines = (text: string) =>
  text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean)

function parseParticipant(line: string): Participant | null {
  const parts = line.split("|").map((p) => p.trim())
  const name = parts[0]
  if (!name) return null
  const lone = parts[1] === "*" && parts.length === 2
  const p: Participant = { name, is_decision_maker: lone || parts[2] === "*" }
  if (parts[1] && !lone) p.role = parts[1]
  return p
}

export function buildContext(d: ContextDraft): MeetingContextIn {
  const ctx: MeetingContextIn = {
    title: d.title.trim(),
    meeting_date: d.meetingDate,
    participants: lines(d.participantsText)
      .map(parseParticipant)
      .filter((p): p is Participant => p !== null),
    glossary: lines(d.glossaryText),
  }
  if (d.project.trim()) ctx.project = d.project.trim()
  if (d.organizer.trim()) ctx.organizer = d.organizer.trim()
  return ctx
}

export function validateDraft(d: ContextDraft): string[] {
  const errors: string[] = []
  if (!d.title.trim()) errors.push("Cần nhập tiêu đề")
  if (!d.meetingDate) errors.push("Cần chọn ngày họp")
  return errors
}
