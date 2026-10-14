"use client"

import { Bell } from "lucide-react"
import Link from "next/link"

import { useIsOrgAdmin, usePendingJoinRequests } from "./hooks"

/** Header bell for org admins: number of pending join requests, links to /settings. */
export function JoinRequestsBell() {
  const admin = useIsOrgAdmin()
  const pending = usePendingJoinRequests(admin)
  if (!admin) return null
  const n = pending.data?.length ?? 0
  const label = n ? `${n} yêu cầu tham gia đang chờ duyệt` : "Không có yêu cầu tham gia"
  return (
    <Link
      href="/settings#join-requests"
      aria-label={label}
      title={label}
      className="relative flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      <Bell className="size-4" aria-hidden />
      {n > 0 && (
        <span className="absolute -top-0.5 -right-0.5 flex min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] leading-4 font-semibold text-white">
          {n > 9 ? "9+" : n}
        </span>
      )}
    </Link>
  )
}
