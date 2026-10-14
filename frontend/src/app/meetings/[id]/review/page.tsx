"use client"

import { useParams } from "next/navigation"

import { PageShell } from "@/components/page-header"
import { ReviewScreen } from "@/features/review/review-screen"

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>()
  return (
    <PageShell>
      <ReviewScreen meetingId={id} />
    </PageShell>
  )
}
