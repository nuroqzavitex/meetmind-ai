"use client"

import { useMutation, useQuery } from "@tanstack/react-query"

import { useApi } from "@/lib/use-api"
import type { AgendaOut, DecisionsOut, TasksOut } from "@/lib/types"

function query(params: Record<string, string | null>): string {
  const q = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v) q.set(k, v)
  const s = q.toString()
  return s ? `?${s}` : ""
}

export function useAgenda(project: string | null) {
  const { get } = useApi()
  return useQuery({
    queryKey: ["overview", "agenda", project],
    queryFn: () => get<AgendaOut>(`/overview/agenda${query({ project })}`),
  })
}

export function useSendAgenda(project: string | null) {
  const { post } = useApi()
  return useMutation({
    mutationFn: () => post<{ sent: boolean }>(`/overview/agenda/discord${query({ project })}`),
  })
}

export function useTasks(project: string | null, owner: string | null) {
  const { get } = useApi()
  return useQuery({
    queryKey: ["overview", "tasks", project, owner],
    queryFn: () => get<TasksOut>(`/overview/tasks${query({ project, owner })}`),
  })
}

export function useDecisions(project: string | null) {
  const { get } = useApi()
  return useQuery({
    queryKey: ["overview", "decisions", project],
    queryFn: () => get<DecisionsOut>(`/overview/decisions${query({ project })}`),
  })
}
