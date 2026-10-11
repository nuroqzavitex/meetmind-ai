"use client"

import { useQuery } from "@tanstack/react-query"

import { useApi } from "@/lib/use-api"
import type { TopicOut } from "@/lib/types"

export function useTopics(meetingId: string) {
  const { get } = useApi()
  return useQuery({
    queryKey: ["topics", meetingId],
    queryFn: () => get<TopicOut[]>(`/meetings/${meetingId}/topics`),
  })
}
