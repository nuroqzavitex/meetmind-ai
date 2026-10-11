"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { useRouter } from "next/navigation"

import { useApi } from "@/lib/use-api"
import type { ItemOut } from "@/lib/types"

export function useReportItem() {
  const { post } = useApi()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      post<void>(`/items/${id}/report`, { reason }),
  })
}

export function useReopenItem(meetingId: string) {
  const { post } = useApi()
  const qc = useQueryClient()
  const router = useRouter()
  return useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      post<ItemOut>(`/items/${id}/reopen`, reason ? { reason } : {}),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["meeting", meetingId] }),
        qc.invalidateQueries({ queryKey: ["items", meetingId] }),
        qc.invalidateQueries({ queryKey: ["meetings"] }),
      ])
      router.push(`/meetings/${meetingId}/review`)
    },
  })
}
