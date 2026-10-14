import type { ItemType, ReviewState } from "@/lib/types";

/** Per-type accent classes (static strings so Tailwind keeps them). */
export const ITEM_TYPE_STYLE: Record<ItemType, { dot: string; badge: string; border: string }> = {
  decision: {
    dot: "bg-indigo-500",
    badge: "bg-indigo-50 text-indigo-700 ring-indigo-200",
    border: "border-l-indigo-500",
  },
  action_item: {
    dot: "bg-sky-500",
    badge: "bg-sky-50 text-sky-700 ring-sky-200",
    border: "border-l-sky-500",
  },
  blocker: {
    dot: "bg-rose-500",
    badge: "bg-rose-50 text-rose-700 ring-rose-200",
    border: "border-l-rose-500",
  },
  request: {
    dot: "bg-amber-500",
    badge: "bg-amber-50 text-amber-800 ring-amber-200",
    border: "border-l-amber-500",
  },
  open_question: {
    dot: "bg-orange-500",
    badge: "bg-orange-50 text-orange-700 ring-orange-200",
    border: "border-l-orange-500",
  },
  knowledge: {
    dot: "bg-teal-500",
    badge: "bg-teal-50 text-teal-700 ring-teal-200",
    border: "border-l-teal-500",
  },
  feedback: {
    dot: "bg-fuchsia-500",
    badge: "bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200",
    border: "border-l-fuchsia-500",
  },
};

export const MEETING_STATUS_STYLE: Record<string, string> = {
  draft: "bg-slate-100 text-slate-700 ring-slate-200",
  analyzing: "bg-sky-50 text-sky-700 ring-sky-200",
  in_review: "bg-amber-50 text-amber-800 ring-amber-200",
  published: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  failed: "bg-rose-50 text-rose-700 ring-rose-200",
};

export const REVIEW_STATE_STYLE: Record<ReviewState, string> = {
  pending: "bg-amber-50 text-amber-800 ring-amber-200",
  approved: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  edited: "bg-sky-50 text-sky-700 ring-sky-200",
  rejected: "bg-slate-100 text-slate-600 ring-slate-200",
};
