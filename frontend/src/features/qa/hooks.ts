"use client"

import { useMutation } from "@tanstack/react-query"
import { useMemo } from "react"

import { useMeetings } from "@/features/meetings/hooks"
import type { QARequest, QAResponse } from "@/lib/types"
import { useApi } from "@/lib/use-api"

export function useAsk() {
  const { post } = useApi()
  return useMutation({
    mutationFn: (req: QARequest) => post<QAResponse>("/qa", req),
  })
}

export function useProjects(): string[] {
  const { data } = useMeetings({ status: "published" })
  return useMemo(() => {
    const set = new Set<string>()
    for (const m of data ?? []) if (m.project) set.add(m.project)
    return [...set].sort((a, b) => a.localeCompare(b))
  }, [data])
}
