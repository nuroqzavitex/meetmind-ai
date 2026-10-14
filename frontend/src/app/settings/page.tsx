import { PageHeader, PageShell } from "@/components/page-header"
import { DiscordSettings } from "@/features/settings/discord-settings"

export default function SettingsPage() {
  return (
    <PageShell>
      <PageHeader
        title="Cài đặt"
        description="Kết nối kênh Discord để nhận tóm tắt khi cuộc họp được phát hành và bản tin nhắc việc mỗi sáng."
      />
      <DiscordSettings />
    </PageShell>
  )
}
