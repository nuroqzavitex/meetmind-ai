"use client"

import { Check, Copy, RefreshCw, UserPlus, X } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { fmtDate } from "@/lib/format"
import { useDecideJoinRequest, useIsOrgAdmin, useJoinCode, usePendingJoinRequests, useRotateJoinCode } from "./hooks"

/** Admin-only cards on /settings: the join code and the pending join requests. */
export function JoinSettings() {
  const admin = useIsOrgAdmin()
  if (!admin) return null
  return (
    <>
      <JoinCodeCard />
      <PendingRequests />
    </>
  )
}

function JoinCodeCard() {
  const code = useJoinCode(true)
  const rotate = useRotateJoinCode()
  const [copied, setCopied] = useState(false)

  async function copy() {
    if (!code.data) return
    try {
      await navigator.clipboard.writeText(code.data.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard blocked: the code is on screen to copy by hand
    }
  }

  return (
    <section className="max-w-2xl space-y-3 rounded-xl border bg-card p-6 shadow-xs">
      <h2 className="font-semibold">Mã tham gia</h2>
      <p className="text-sm text-muted-foreground">
        Gửi mã này cho người muốn vào tổ chức. Họ nhập mã sau khi đăng ký, bạn duyệt yêu cầu ở bên dưới. Đổi mã thì mã cũ hết hiệu lực.
      </p>
      {code.isPending ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Đang tải…
        </p>
      ) : code.isError ? (
        <p role="alert" className="text-sm text-destructive">{code.error.message}</p>
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <code className="rounded-lg bg-muted px-3 py-1.5 font-mono text-lg tracking-wider" data-testid="join-code">
            {code.data.code}
          </code>
          <Button type="button" variant="outline" size="sm" onClick={copy}>
            {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
            {copied ? "Đã sao chép" : "Sao chép"}
          </Button>
          <Button type="button" variant="ghost" size="sm" onClick={() => rotate.mutate()} disabled={rotate.isPending}>
            <RefreshCw aria-hidden />
            Đổi mã
          </Button>
        </div>
      )}
    </section>
  )
}

function PendingRequests() {
  const pending = usePendingJoinRequests(true)
  const decide = useDecideJoinRequest()

  return (
    <section id="join-requests" className="max-w-2xl scroll-mt-24 space-y-3 rounded-xl border bg-card p-6 shadow-xs">
      <div className="flex items-center gap-2">
        <UserPlus className="size-4 text-primary" aria-hidden />
        <h2 className="font-semibold">Yêu cầu tham gia</h2>
      </div>
      {pending.isPending ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Đang tải…
        </p>
      ) : pending.isError ? (
        <p role="alert" className="text-sm text-destructive">{pending.error.message}</p>
      ) : pending.data.length === 0 ? (
        <p className="text-sm text-muted-foreground">Không có yêu cầu nào đang chờ.</p>
      ) : (
        <ul className="divide-y">
          {pending.data.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
              <div className="min-w-0 flex-1">
                <p className="font-medium">{r.user_name}</p>
                <p className="text-muted-foreground">
                  {r.user_email ?? "Không có email"} · {fmtDate(r.created_at)}
                </p>
              </div>
              <Button
                size="sm"
                variant="ghost"
                aria-label={`Từ chối ${r.user_name}`}
                disabled={decide.isPending}
                onClick={() => decide.mutate({ id: r.id, approve: false })}
              >
                <X aria-hidden />
                Từ chối
              </Button>
              <Button
                size="sm"
                aria-label={`Đồng ý ${r.user_name}`}
                disabled={decide.isPending}
                onClick={() => decide.mutate({ id: r.id, approve: true })}
              >
                <Check aria-hidden />
                Đồng ý
              </Button>
            </li>
          ))}
        </ul>
      )}
      {decide.error && (
        <p role="alert" className="text-sm text-destructive">{decide.error.message}</p>
      )}
    </section>
  )
}
