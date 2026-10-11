"use client"

import { useParams } from "next/navigation"
import { Suspense } from "react"

import { MinutesView } from "@/features/minutes/minutes-view"

export default function MinutesPage() {
  const { id } = useParams<{ id: string }>()
  return (
    <Suspense>
      <MinutesView meetingId={id} />
    </Suspense>
  )
}
