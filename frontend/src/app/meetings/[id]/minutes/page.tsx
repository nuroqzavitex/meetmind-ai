"use client"

import { useParams } from "next/navigation"
import { Suspense } from "react"

import { PageShell } from "@/components/page-header"
import { MinutesView } from "@/features/minutes/minutes-view"

export default function MinutesPage() {
  const { id } = useParams<{ id: string }>()
  return (
    <PageShell className="max-w-4xl">
      <Suspense>
        <MinutesView meetingId={id} />
      </Suspense>
    </PageShell>
  )
}
