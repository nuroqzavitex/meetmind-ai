import { Badge } from "@/components/ui/badge"
import { MEETING_STATUS_LABEL } from "@/lib/format"

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge variant={status === "failed" ? "destructive" : "secondary"}>
      {MEETING_STATUS_LABEL[status] ?? status}
    </Badge>
  )
}
