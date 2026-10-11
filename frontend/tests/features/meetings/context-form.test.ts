import { expect, test } from "vitest"

import { buildContext, validateDraft, type ContextDraft } from "@/features/meetings/context-form"

const base: ContextDraft = {
  title: " Họp sprint ",
  meetingDate: "2026-10-10",
  project: "  ",
  organizer: "",
  participantsText: "Lan | Trưởng nhóm | *\nMinh\n\nHoa | QA",
  glossaryText: "Postgres\n\nMongoDB ",
}

test("buildContext parses participants and glossary", () => {
  const c = buildContext(base)
  expect(c.title).toBe("Họp sprint")
  expect(c.participants).toEqual([
    { name: "Lan", role: "Trưởng nhóm", is_decision_maker: true },
    { name: "Minh", is_decision_maker: false },
    { name: "Hoa", role: "QA", is_decision_maker: false },
  ])
  expect(c.glossary).toEqual(["Postgres", "MongoDB"])
})

test("blank project and organizer omitted", () => {
  const c = buildContext(base)
  expect("project" in c).toBe(false)
  expect("organizer" in c).toBe(false)
})

test("validateDraft", () => {
  expect(validateDraft({ ...base, title: " " })).toContain("Cần nhập tiêu đề")
  expect(validateDraft({ ...base, meetingDate: "" })).toContain("Cần chọn ngày họp")
  expect(validateDraft(base)).toEqual([])
})

test("lone star in second field marks decision maker without role", () => {
  const c = buildContext({ ...base, participantsText: "Lan | *" })
  expect(c.participants).toEqual([{ name: "Lan", is_decision_maker: true }])
})
