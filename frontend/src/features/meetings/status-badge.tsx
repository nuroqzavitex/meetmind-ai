import { Badge } from "@/components/ui/badge"
import { MEETING_STATUS_LABEL } from "@/lib/format"
import { MEETING_STATUS_STYLE } from "@/lib/item-style"
import { cn } from "@/lib/utils"

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge
      variant="outline"
      className={cn("border-transparent ring-1 ring-inset", MEETING_STATUS_STYLE[status] ?? MEETING_STATUS_STYLE.draft)}
    >
      {MEETING_STATUS_LABEL[status] ?? status}
    </Badge>
  )
}
