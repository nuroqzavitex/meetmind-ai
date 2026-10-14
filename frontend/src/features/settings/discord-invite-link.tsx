"use client"

import { useOrganization } from "@clerk/nextjs"
import { MessageCircle } from "lucide-react"

import { useDiscordSettings } from "./hooks"

/** Header link to the team's Discord server, for every member, once an admin has shared one. */
export function DiscordInviteLink() {
  const { organization } = useOrganization()
  if (!organization) return null
  return <InviteLink />
}

function InviteLink() {
  const settings = useDiscordSettings()
  const url = settings.data?.invite_url
  if (!url) return null
  return (
    <a
      href={url}
      target="_blank"
      rel="noopener noreferrer"
      title="Tham gia kênh Discord của nhóm"
      aria-label="Tham gia kênh Discord của nhóm"
      className="flex h-9 items-center gap-1.5 rounded-lg px-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      <MessageCircle className="size-4" aria-hidden />
      <span className="sr-only sm:not-sr-only">Discord</span>
    </a>
  )
}
