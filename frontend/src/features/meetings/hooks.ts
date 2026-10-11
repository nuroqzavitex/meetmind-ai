"use client"

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { useApi } from "@/lib/use-api"
import type { JobOut, MeetingCreated, MeetingDetail, MeetingSummary } from "@/lib/types"

export type MeetingFilters = { project?: string; status?: string }

export const isJobActive = (job?: JobOut | null) =>
  job?.status === "queued" || job?.status === "running"

export function useMeetings(filters: MeetingFilters) {
  const { get } = useApi()
  return useQuery({
    queryKey: ["meetings", filters],
    placeholderData: keepPreviousData,
    queryFn: () => {
      const qs = new URLSearchParams()
      if (filters.project) qs.set("project", filters.project)
      if (filters.status) qs.set("status", filters.status)
      const s = qs.toString()
      return get<MeetingSummary[]>(`/meetings${s ? `?${s}` : ""}`)
    },
  })
}

export function useMeeting(id: string | null, enabled = true) {
  const { get } = useApi()
  return useQuery({
    queryKey: ["meeting", id],
    queryFn: () => get<MeetingDetail>(`/meetings/${id}`),
    enabled: enabled && !!id,
  })
}

export function useJob(jobId: string | null) {
  const { get } = useApi()
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => get<JobOut>(`/jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (query) => (isJobActive(query.state.data) ? 1000 : false),
  })
}

export function useCreateMeeting() {
  const { postForm } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (form: FormData) => postForm<MeetingCreated>("/meetings", form),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["meetings"] }),
  })
}

export function useReanalyze(meetingId: string) {
  const { post } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => post<MeetingCreated>(`/meetings/${meetingId}/reanalyze`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meetings"] })
      qc.invalidateQueries({ queryKey: ["meeting", meetingId] })
    },
  })
}
