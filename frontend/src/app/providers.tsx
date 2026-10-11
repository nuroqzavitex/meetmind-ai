"use client"

import { useAuth } from "@clerk/nextjs"
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query"
import { Fragment, useRef, useState } from "react"

import { ApiError } from "@/lib/api-client"

// Clears the cache synchronously during render (it renders before its
// siblings and before the keyed remount below), so no child reads the previous
// org's data; safe because TanStack batches notifications via notifyManager.
function OrgCacheReset() {
  const { orgId } = useAuth()
  const queryClient = useQueryClient()
  const prev = useRef(orgId)

  if (prev.current && prev.current !== orgId) queryClient.clear()
  prev.current = orgId

  return null
}

export function Providers({ children }: { children: React.ReactNode }) {
  const { orgId } = useAuth()
  const orgKey = orgId ?? "none"
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 5_000,
            retry: (failureCount, error) => {
              if (error instanceof ApiError && error.status >= 400 && error.status < 500)
                return false
              return failureCount < 1
            },
          },
        },
      }),
  )
  return (
    <QueryClientProvider client={client}>
      <OrgCacheReset />
      <Fragment key={orgKey}>{children}</Fragment>
    </QueryClientProvider>
  )
}
