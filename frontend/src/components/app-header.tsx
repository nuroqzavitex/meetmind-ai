import { OrganizationSwitcher, SignedIn, UserButton } from "@clerk/nextjs"
import Link from "next/link"

export function AppHeader() {
  return (
    <SignedIn>
    <header className="border-b bg-background">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
        <Link href="/" className="font-semibold">
          MeetMind
        </Link>
        <nav className="flex flex-1 items-center gap-4 text-sm">
          <Link href="/" className="text-muted-foreground hover:text-foreground">
            Cuộc họp
          </Link>
          <Link
            href="/meetings/new"
            className="text-muted-foreground hover:text-foreground"
          >
            Tải lên
          </Link>
        </nav>
        <OrganizationSwitcher hidePersonal afterSelectOrganizationUrl="/" />
        <UserButton />
      </div>
    </header>
    </SignedIn>
  )
}
