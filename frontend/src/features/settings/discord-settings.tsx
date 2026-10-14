"use client"

import { BellRing, Send, Trash2 } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import type { DiscordSettingsIn, DiscordSettingsOut } from "@/lib/types"
import { useDiscordSettings, useSaveDiscordSettings, useTestDiscord } from "./hooks"

// Mirrors the backend check; the server is the authority.
export const WEBHOOK_RE = /^https:\/\/(?:discord|discordapp)\.com\/api\/webhooks\/\d+\/[\w-]+$/
export const INVITE_RE = /^https:\/\/(?:discord\.gg|(?:www\.)?(?:discord|discordapp)\.com\/invite)\/[A-Za-z0-9-]{2,32}$/

export function DiscordSettings() {
  const settings = useDiscordSettings()
  if (settings.isPending)
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Spinner /> Đang tải…
      </p>
    )
  if (settings.isError)
    return (
      <p role="alert" className="text-sm text-destructive">
        {settings.error.message}
      </p>
    )
  return <DiscordForm initial={settings.data} />
}

function DiscordForm({ initial }: { initial: DiscordSettingsOut }) {
  const save = useSaveDiscordSettings()
  const test = useTestDiscord()
  const current = save.data ?? initial
  const [url, setUrl] = useState("")
  const [digest, setDigest] = useState(initial.digest_enabled)
  const [invite, setInvite] = useState(initial.invite_url ?? "")
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  function reset() {
    setError(null)
    setNotice(null)
    test.reset()
  }

  function submit(e: React.FormEvent) {
    e.preventDefault()
    reset()
    const trimmed = url.trim()
    if (trimmed && !WEBHOOK_RE.test(trimmed)) {
      setError("URL webhook không hợp lệ. URL đúng có dạng https://discord.com/api/webhooks/<id>/<token>")
      return
    }
    const inviteTrimmed = invite.trim()
    if (inviteTrimmed && !INVITE_RE.test(inviteTrimmed)) {
      setError("Link mời Discord không hợp lệ. Link đúng có dạng https://discord.gg/<mã>")
      return
    }
    const body: DiscordSettingsIn = trimmed
      ? { webhook_url: trimmed, digest_enabled: digest }
      : { digest_enabled: digest }
    // Only send the invite when it changed, so saving the rest never touches it.
    if (inviteTrimmed !== (current.invite_url ?? "")) body.invite_url = inviteTrimmed
    save.mutate(body, {
      onSuccess: () => {
        setUrl("")
        setNotice("Đã lưu cài đặt")
      },
    })
  }

  function remove() {
    reset()
    save.mutate(
      { webhook_url: "", digest_enabled: digest },
      { onSuccess: () => setNotice("Đã xoá webhook") },
    )
  }

  function sendTest() {
    reset()
    test.mutate(undefined, { onSuccess: () => setNotice("Đã gửi tin thử, hãy kiểm tra kênh Discord") })
  }

  const failure = error ?? save.error?.message ?? test.error?.message ?? null

  return (
    <form onSubmit={submit} className="max-w-2xl space-y-5 rounded-xl border bg-card p-6 shadow-xs" noValidate>
      <div className="flex items-center gap-3">
        <span className="flex size-9 items-center justify-center rounded-full bg-accent text-accent-foreground">
          <BellRing className="size-4" aria-hidden />
        </span>
        <div>
          <h2 className="font-semibold">Thông báo Discord</h2>
          <p className="text-sm text-muted-foreground">
            {current.configured
              ? `Đã kết nối webhook (${current.webhook_hint})`
              : "Chưa kết nối. Tạo webhook trong Cài đặt kênh → Tích hợp → Webhook."}
          </p>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="webhook-url">{current.configured ? "Đổi URL webhook" : "URL webhook"}</Label>
        <Input
          id="webhook-url"
          type="password"
          autoComplete="off"
          placeholder="https://discord.com/api/webhooks/…"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          URL webhook là bí mật: ai có URL đều gửi được tin vào kênh. Hệ thống chỉ hiển thị 4 ký tự cuối.
        </p>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="invite-url">Link mời vào server Discord</Label>
        <Input
          id="invite-url"
          autoComplete="off"
          placeholder="https://discord.gg/…"
          value={invite}
          onChange={(e) => setInvite(e.target.value)}
        />
        <p className="text-xs text-muted-foreground">
          Không bắt buộc. Thành viên sẽ thấy nút Discord trên thanh điều hướng, người mới được duyệt cũng nhận link này.
          Tạo link: chuột phải tên server → Mời mọi người → đặt &quot;Không bao giờ hết hạn&quot;.
        </p>
      </div>

      <label className="flex items-start gap-2 text-sm">
        <Checkbox
          checked={digest}
          onCheckedChange={(v) => setDigest(v === true)}
          aria-label="Bản tin nhắc việc 8h sáng"
          className="mt-0.5"
        />
        <span>
          <span className="font-medium">Bản tin nhắc việc 8h sáng</span>
          <span className="block text-muted-foreground">
            Việc quá hạn (7 ngày gần nhất), đến hạn hôm nay và trong 2 ngày tới. Tóm tắt khi phát hành luôn được gửi.
          </span>
        </span>
      </label>

      {failure && (
        <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {failure}
        </p>
      )}
      {notice && !failure && (
        <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-900">
          {notice}
        </p>
      )}

      <div className="flex flex-wrap justify-end gap-2">
        {current.configured && (
          <>
            <Button type="button" variant="ghost" onClick={remove} disabled={save.isPending}>
              <Trash2 aria-hidden />
              Xoá webhook
            </Button>
            <Button type="button" variant="outline" onClick={sendTest} disabled={test.isPending}>
              <Send aria-hidden />
              Gửi thử
            </Button>
          </>
        )}
        <Button type="submit" disabled={save.isPending}>
          Lưu
        </Button>
      </div>
    </form>
  )
}
