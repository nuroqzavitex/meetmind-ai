"use client"

import { FileUp, ListChecks, MessagesSquare } from "lucide-react"
import Link from "next/link"
import { usePathname } from "next/navigation"

import { cn } from "@/lib/utils"

const LINKS = [
  { href: "/", label: "Cuộc họp", icon: ListChecks, match: (p: string) => p === "/" || p.startsWith("/meetings/") && !p.startsWith("/meetings/new") },
  { href: "/meetings/new", label: "Tải lên", icon: FileUp, match: (p: string) => p.startsWith("/meetings/new") },
  { href: "/qa", label: "Hỏi đáp", icon: MessagesSquare, match: (p: string) => p.startsWith("/qa") },
]

export function NavLinks() {
  const pathname = usePathname() ?? "/"
  return (
    <nav className="flex items-center gap-1 text-sm">
      {LINKS.map(({ href, label, icon: Icon, match }) => {
        const active = match(pathname)
        return (
          <Link
            key={href}
            href={href}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-1.5 rounded-lg px-3 py-1.5 font-medium transition-colors",
              active
                ? "bg-accent text-accent-foreground"
                : "text-muted-foreground hover:bg-muted hover:text-foreground",
            )}
          >
            <Icon className="size-4" aria-hidden />
            <span className="sr-only sm:not-sr-only">{label}</span>
          </Link>
        )
      })}
    </nav>
  )
}
