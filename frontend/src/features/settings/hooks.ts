"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import { useApi } from "@/lib/use-api"
import type { DiscordSettingsIn, DiscordSettingsOut } from "@/lib/types"

const KEY = ["settings", "discord"]

export function useDiscordSettings() {
  const { get } = useApi()
  return useQuery({ queryKey: KEY, queryFn: () => get<DiscordSettingsOut>("/settings/discord") })
}

export function useSaveDiscordSettings() {
  const { put } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: DiscordSettingsIn) => put<DiscordSettingsOut>("/settings/discord", body),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  })
}

export function useTestDiscord() {
  const { post } = useApi()
  return useMutation({ mutationFn: () => post<void>("/settings/discord/test") })
}
