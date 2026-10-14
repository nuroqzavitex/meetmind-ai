"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Bot, Check, Copy, ExternalLink, RefreshCw, Unlink } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { useIsOrgAdmin } from "@/features/orgs/hooks"
import { useApi } from "@/lib/use-api"
import type { DiscordBotOut } from "@/lib/types"

const KEY = ["settings", "discord-bot"]

/** Admin card: link the org to a Discord server so members can ask `/hoi` there. */
export function DiscordBotSettings() {
  const admin = useIsOrgAdmin()
  if (!admin) return null
  return <BotCard />
}

function BotCard() {
  const { get, post } = useApi()
  const qc = useQueryClient()
  const bot = useQuery({ queryKey: KEY, queryFn: () => get<DiscordBotOut>("/settings/discord-bot") })
  const action = useMutation({
    mutationFn: (path: "rotate-code" | "unlink") => post<DiscordBotOut>(`/settings/discord-bot/${path}`),
    onSuccess: (data) => qc.setQueryData(KEY, data),
  })
  const [copied, setCopied] = useState(false)

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      // clipboard blocked: the command is on screen to copy by hand
    }
  }

  return (
    <section className="max-w-2xl space-y-4 rounded-xl border bg-card p-6 shadow-xs">
      <div className="flex items-center gap-3">
        <span className="flex size-9 items-center justify-center rounded-full bg-accent text-accent-foreground">
          <Bot className="size-4" aria-hidden />
        </span>
        <div>
          <h2 className="font-semibold">Bot hỏi đáp Discord</h2>
          <p className="text-sm text-muted-foreground">
            Mọi người trong server đã liên kết gõ <code>/hoi &lt;câu hỏi&gt;</code> để hỏi về các cuộc họp đã phát hành.
          </p>
        </div>
      </div>

      {bot.isPending ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Spinner /> Đang tải…
        </p>
      ) : bot.isError ? (
        <p role="alert" className="text-sm text-destructive">{bot.error.message}</p>
      ) : !bot.data.available ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          Backend chưa cấu hình bot (thiếu <code>DISCORD_APP_ID</code> / <code>DISCORD_PUBLIC_KEY</code>).
        </p>
      ) : (
        <>
          <p className="text-sm" data-testid="bot-status">
            {bot.data.linked
              ? "✅ Đã liên kết với một server Discord."
              : "Chưa liên kết server Discord nào."}
          </p>
          <ol className="list-inside list-decimal space-y-2 text-sm">
            <li>
              Thêm bot vào server:{" "}
              {bot.data.install_url && (
                <a
                  href={bot.data.install_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 font-medium text-primary underline-offset-4 hover:underline"
                >
                  Mời bot MeetMind <ExternalLink className="size-3.5" aria-hidden />
                </a>
              )}
            </li>
            <li className="space-y-1.5">
              <span>Trong server, người có quyền quản lý server gõ lệnh:</span>
              <div className="flex flex-wrap items-center gap-2">
                <code className="rounded-lg bg-muted px-3 py-1.5 font-mono" data-testid="link-command">
                  /ketnoi ma:{bot.data.link_code}
                </code>
                <Button type="button" size="sm" variant="outline" onClick={() => copy(bot.data.link_code)}>
                  {copied ? <Check aria-hidden /> : <Copy aria-hidden />}
                  {copied ? "Đã sao chép" : "Sao chép mã"}
                </Button>
              </div>
            </li>
          </ol>
          <div className="flex flex-wrap justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" disabled={action.isPending} onClick={() => action.mutate("rotate-code")}>
              <RefreshCw aria-hidden />
              Đổi mã
            </Button>
            {bot.data.linked && (
              <Button type="button" variant="outline" size="sm" disabled={action.isPending} onClick={() => action.mutate("unlink")}>
                <Unlink aria-hidden />
                Huỷ liên kết
              </Button>
            )}
          </div>
          {action.error && <p role="alert" className="text-sm text-destructive">{action.error.message}</p>}
        </>
      )}
    </section>
  )
}
