"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { useApi } from "@/lib/use-api"
import type { MeetingCreated, SpeakerAssignment, SpeakerOut } from "@/lib/types"

export function useSpeakers(meetingId: string) {
  const { get } = useApi()
  return useQuery({
    queryKey: ["speakers", meetingId],
    queryFn: () => get<SpeakerOut[]>(`/meetings/${meetingId}/speakers`),
    retry: false,
  })
}

export function useAssignSpeakers(meetingId: string) {
  const { post } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (speakers: SpeakerAssignment[]) =>
      post<MeetingCreated>(`/meetings/${meetingId}/speakers`, { speakers }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meetings"] })
      qc.invalidateQueries({ queryKey: ["meeting", meetingId] })
    },
  })
}
