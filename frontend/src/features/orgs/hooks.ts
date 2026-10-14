"use client"

import { useOrganization } from "@clerk/nextjs"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { useApi } from "@/lib/use-api"
import type { JoinCodeOut, JoinRequestOut } from "@/lib/types"

const MINE = ["join-requests", "mine"]
const PENDING = ["join-requests", "pending"]
const CODE = ["settings", "join-code"]

/** Admin of the active organization (Clerk role key "org:admin"). */
export function useIsOrgAdmin(): boolean {
  const { membership } = useOrganization()
  return membership?.role === "org:admin"
}

export function useMyJoinRequests() {
  const { get } = useApi()
  return useQuery({
    queryKey: MINE,
    queryFn: () => get<JoinRequestOut[]>("/join-requests/mine"),
    // Keep checking while something is waiting for an admin.
    refetchInterval: (q) => (q.state.data?.some((r) => r.status === "pending") ? 15_000 : false),
  })
}

export function useCreateJoinRequest() {
  const { post } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (code: string) => post<JoinRequestOut>("/join-requests", { code }),
    onSuccess: () => qc.invalidateQueries({ queryKey: MINE }),
  })
}

export function useCancelJoinRequest() {
  const { del } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => del<void>(`/join-requests/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: MINE }),
  })
}

export function usePendingJoinRequests(enabled: boolean) {
  const { get } = useApi()
  return useQuery({
    queryKey: PENDING,
    queryFn: () => get<JoinRequestOut[]>("/join-requests"),
    enabled,
    refetchInterval: 60_000,
  })
}

export function useDecideJoinRequest() {
  const { post } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, approve }: { id: string; approve: boolean }) =>
      post<JoinRequestOut>(`/join-requests/${id}/${approve ? "approve" : "reject"}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: PENDING }),
  })
}

export function useJoinCode(enabled: boolean) {
  const { get } = useApi()
  return useQuery({ queryKey: CODE, queryFn: () => get<JoinCodeOut>("/settings/join-code"), enabled })
}

export function useRotateJoinCode() {
  const { post } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => post<JoinCodeOut>("/settings/join-code/rotate"),
    onSuccess: (data) => qc.setQueryData(CODE, data),
  })
}
