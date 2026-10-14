import { PageHeader, PageShell } from "@/components/page-header"
import { JoinSettings } from "@/features/orgs/join-settings"
import { DiscordBotSettings } from "@/features/settings/discord-bot"
import { DiscordSettings } from "@/features/settings/discord-settings"

export default function SettingsPage() {
  return (
    <PageShell>
      <PageHeader
        title="Cài đặt"
        description="Thành viên tổ chức và kết nối Discord để nhận tóm tắt cuộc họp, bản tin nhắc việc và yêu cầu tham gia."
      />
      <div className="space-y-6">
        <JoinSettings />
        <DiscordSettings />
        <DiscordBotSettings />
      </div>
    </PageShell>
  )
}
