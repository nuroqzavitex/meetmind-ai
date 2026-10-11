"use client"

import { useParams } from "next/navigation"

import { ReviewScreen } from "@/features/review/review-screen"

export default function ReviewPage() {
  const { id } = useParams<{ id: string }>()
  return <ReviewScreen meetingId={id} />
}
