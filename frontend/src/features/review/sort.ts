import { ITEM_TYPES } from "@/lib/format"
import type { ItemOut, ItemType } from "@/lib/types"

export function groupByType(items: ItemOut[]): Record<ItemType, ItemOut[]> {
  const out = {} as Record<ItemType, ItemOut[]>
  for (const t of ITEM_TYPES) out[t] = []
  for (const i of items) out[i.type]?.push(i)
  return out
}

export function countPending(items: ItemOut[]): number {
  return items.filter((i) => i.review_state === "pending").length
}
