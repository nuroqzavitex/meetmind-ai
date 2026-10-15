"use client"

import { OrganizationSwitcher, SignedIn, UserButton } from "@clerk/nextjs"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { BrandMark } from "@/components/brand"
import { NavLinks } from "@/components/nav-links"
import { JoinRequestsBell } from "@/features/orgs/join-requests-bell"
import { DiscordInviteLink } from "@/features/settings/discord-invite-link"

/** Pages drawn by AuthShell have their own full-height layout and no app navigation. */
const AUTH_PAGES = ["/sign-in", "/sign-up", "/select-org"]

export function AppHeader() {
  const pathname = usePathname()
  if (AUTH_PAGES.some((p) => pathname === p || pathname.startsWith(`${p}/`))) return null
  return (
    <SignedIn>
    <header className="sticky top-0 z-30 border-b bg-background/80 backdrop-blur supports-[backdrop-filter]:bg-background/70">
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-6 px-4 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold">
          <BrandMark />
          <span>MeetMind</span>
        </Link>
        <NavLinks />
        <div className="ml-auto flex items-center gap-3">
          <DiscordInviteLink />
          <JoinRequestsBell />
          <OrganizationSwitcher hidePersonal afterSelectOrganizationUrl="/" />
          <UserButton />
        </div>
      </div>
    </header>
    </SignedIn>
  )
}
