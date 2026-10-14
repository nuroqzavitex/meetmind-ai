"use client"

import { useOrganizationList } from "@clerk/nextjs"
import { KeyRound } from "lucide-react"
import { useRouter } from "next/navigation"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import type { JoinRequestOut } from "@/lib/types"
import { cn } from "@/lib/utils"
import { useCancelJoinRequest, useCreateJoinRequest, useMyJoinRequests } from "./hooks"

const STATUS: Record<JoinRequestOut["status"], { label: string; className: string }> = {
  pending: { label: "Đang chờ duyệt", className: "bg-amber-50 text-amber-800 ring-amber-200" },
  approved: { label: "Đã được duyệt", className: "bg-emerald-50 text-emerald-800 ring-emerald-200" },
  rejected: { label: "Bị từ chối", className: "bg-rose-50 text-rose-800 ring-rose-200" },
  cancelled: { label: "Đã huỷ", className: "bg-muted text-muted-foreground ring-border" },
}

/** "Ask to join an existing organization" panel on /select-org. */
export function JoinByCode() {
  const [code, setCode] = useState("")
  const create = useCreateJoinRequest()
  const mine = useMyJoinRequests()

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (!code.trim()) return
    create.mutate(code.trim(), { onSuccess: () => setCode("") })
  }

  return (
    <section className="space-y-4 rounded-xl border bg-card p-5 shadow-xs">
      <div className="flex items-center gap-2">
        <KeyRound className="size-4 text-primary" aria-hidden />
        <h2 className="font-semibold">Xin vào tổ chức có sẵn</h2>
      </div>
      <form onSubmit={submit} className="space-y-2" noValidate>
        <Label htmlFor="join-code">Mã tham gia</Label>
        <div className="flex gap-2">
          <Input
            id="join-code"
            placeholder="MM-XXXX-XXXX"
            autoComplete="off"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          <Button type="submit" disabled={create.isPending || !code.trim()}>
            Gửi yêu cầu
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">Admin của tổ chức xem mã ở trang Cài đặt và sẽ duyệt yêu cầu của bạn.</p>
        {create.error && (
          <p role="alert" className="text-sm text-destructive">
            {create.error.message}
          </p>
        )}
      </form>
      {mine.data && mine.data.length > 0 && (
        <ul className="space-y-2">
          {mine.data.map((r) => (
            <MyRequest key={r.id} request={r} />
          ))}
        </ul>
      )}
    </section>
  )
}

function MyRequest({ request }: { request: JoinRequestOut }) {
  const cancel = useCancelJoinRequest()
  const { setActive } = useOrganizationList()
  const router = useRouter()
  const [enterError, setEnterError] = useState<string | null>(null)
  const status = STATUS[request.status]

  async function enter() {
    setEnterError(null)
    try {
      await setActive?.({ organization: request.org_id })
      router.push("/")
    } catch {
      setEnterError("Chưa vào được, hãy tải lại trang rồi chọn tổ chức ở danh sách phía trên.")
    }
  }

  return (
    <li className="space-y-1.5 rounded-lg border px-3 py-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{request.org_name}</span>
        <span className={cn("rounded-full px-2 py-0.5 text-xs ring-1 ring-inset", status.className)}>{status.label}</span>
        <span className="ml-auto flex gap-2">
          {request.status === "pending" && (
            <Button size="sm" variant="ghost" onClick={() => cancel.mutate(request.id)} disabled={cancel.isPending}>
              Huỷ
            </Button>
          )}
          {request.status === "approved" && request.discord_invite_url && (
            <a
              href={request.discord_invite_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-8 items-center rounded-lg border px-3 text-sm font-medium hover:bg-muted"
            >
              Tham gia Discord
            </a>
          )}
          {request.status === "approved" && (
            <Button size="sm" onClick={enter}>
              Vào tổ chức
            </Button>
          )}
        </span>
      </div>
      {enterError && <p className="text-xs text-destructive">{enterError}</p>}
    </li>
  )
}
