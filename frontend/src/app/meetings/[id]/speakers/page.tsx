"use client"

import { useParams } from "next/navigation"

import { PageHeader, PageShell } from "@/components/page-header"
import { SpeakerForm } from "@/features/speakers/speaker-form"

export default function SpeakersPage() {
  const { id } = useParams<{ id: string }>()
  return (
    <PageShell>
      <PageHeader
        title="Gán tên người nói"
        description="Đặt tên thật cho từng người nói trong bản ghi âm và đánh dấu ai có quyền chốt quyết định."
      />
      <SpeakerForm meetingId={id} />
    </PageShell>
  )
}
