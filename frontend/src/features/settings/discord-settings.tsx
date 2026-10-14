"use client"

import { BellRing, Send, Trash2 } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Spinner } from "@/components/ui/spinner"
import type { DiscordSettingsOut } from "@/lib/types"
import { useDiscordSettings, useSaveDiscordSettings, useTestDiscord } from "./hooks"

// Mirrors the backend check; the server is the authority.
export const WEBHOOK_RE = /^https:\/\/(?:discord|discordapp)\.com\/api\/webhooks\/\d+\/[\w-]+$/

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
    save.mutate(trimmed ? { webhook_url: trimmed, digest_enabled: digest } : { digest_enabled: digest }, {
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
