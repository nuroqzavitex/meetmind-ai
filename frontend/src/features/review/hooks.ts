"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"

import { useApi } from "@/lib/use-api"
import type { ApproveCleanOut, ItemAction, ItemOut, MeetingSummary } from "@/lib/types"

export function useItems(meetingId: string) {
  const { get } = useApi()
  return useQuery({
    queryKey: ["items", meetingId],
    queryFn: () => get<ItemOut[]>(`/meetings/${meetingId}/items`),
  })
}

export function useItemAction(meetingId: string) {
  const { patch } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, body }: { id: string; body: ItemAction }) =>
      patch<ItemOut>(`/items/${id}`, body),
    onSuccess: (updated) => {
      qc.setQueryData<ItemOut[]>(["items", meetingId], (old) =>
        old?.map((i) => (i.id === updated.id ? updated : i)),
      )
      qc.invalidateQueries({ queryKey: ["events", updated.id] })
    },
  })
}

export function useApproveClean(meetingId: string) {
  const { post } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => post<ApproveCleanOut>(`/meetings/${meetingId}/items/approve-clean`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["items", meetingId] }),
  })
}

export function usePublish(meetingId: string) {
  const { post } = useApi()
  const qc = useQueryClient()
  const router = useRouter()
  return useMutation({
    mutationFn: () => post<MeetingSummary>(`/meetings/${meetingId}/publish`),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["meeting", meetingId] }),
        qc.invalidateQueries({ queryKey: ["meetings"] }),
      ])
      router.push(`/meetings/${meetingId}/minutes`)
    },
  })
}
