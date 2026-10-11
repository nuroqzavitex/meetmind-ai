import { expect, test } from "vitest"
import { countPending, groupByType } from "@/features/review/sort"
import { ITEM_TYPES } from "@/lib/format"
import type { ItemOut } from "@/lib/types"

const it = (id: string, type: string, review_state = "pending") =>
  ({ id, type, review_state }) as unknown as ItemOut

test("groupByType keeps order and covers all keys", () => {
  const g = groupByType([it("1", "action_item"), it("2", "decision"), it("3", "action_item")])
  expect(Object.keys(g).sort()).toEqual([...ITEM_TYPES].sort())
  expect(g.action_item.map((i) => i.id)).toEqual(["1", "3"])
  expect(g.feedback).toEqual([])
})

test("countPending counts only pending", () => {
  expect(countPending([it("1", "decision"), it("2", "decision", "approved"), it("3", "decision", "edited")])).toBe(1)
})
