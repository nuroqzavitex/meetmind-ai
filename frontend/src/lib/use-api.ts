"use client"

import { useAuth } from "@clerk/nextjs"
import { useMemo } from "react"

import { apiDownload, apiFetch } from "@/lib/api-client"

export function useApi() {
  const { getToken } = useAuth()
  return useMemo(
    () => ({
      get: <T,>(path: string) => apiFetch<T>(path, { getToken }),
      post: <T,>(path: string, json?: unknown) =>
        apiFetch<T>(path, { getToken, method: "POST", json }),
      postForm: <T,>(path: string, form: FormData) =>
        apiFetch<T>(path, { getToken, method: "POST", form }),
      patch: <T,>(path: string, json: unknown) =>
        apiFetch<T>(path, { getToken, method: "PATCH", json }),
      download: async (path: string, fallbackName?: string): Promise<void> => {
        const { blob, filename } = await apiDownload(path, getToken, fallbackName)
        const url = URL.createObjectURL(blob)
        const a = document.createElement("a")
        a.href = url
        a.download = filename
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)
      },
    }),
    [getToken],
  )
}
