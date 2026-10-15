"use client"

import { useMutation, useQueryClient } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { useState } from "react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { useIsOrgAdmin } from "@/features/orgs/hooks"
import { useApi } from "@/lib/use-api"

export function useDeleteMeeting(meetingId: string) {
  const { del } = useApi()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => del<void>(`/meetings/${meetingId}`),
    onSuccess: () => {
      qc.removeQueries({ queryKey: ["meeting", meetingId] })
      qc.invalidateQueries({ queryKey: ["meetings"] })
    },
  })
}

/** Admin-only "delete permanently" button with a confirmation dialog. */
export function DeleteMeetingButton({
  meetingId,
  title,
  compact = false,
  onDeleted,
}: {
  meetingId: string
  title: string
  compact?: boolean
  onDeleted?: () => void
}) {
  const admin = useIsOrgAdmin()
  const [open, setOpen] = useState(false)
  const remove = useDeleteMeeting(meetingId)
  if (!admin) return null

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (!o) remove.reset()
      }}
    >
      <DialogTrigger
        render={
          compact ? (
            <Button variant="ghost" size="icon-sm" aria-label={`Xoá cuộc họp ${title}`} title="Xoá cuộc họp" />
          ) : (
            <Button variant="outline" />
          )
        }
      >
        <Trash2 aria-hidden className={compact ? "size-4 text-muted-foreground" : undefined} />
        {!compact && "Xoá"}
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Xoá cuộc họp?</DialogTitle>
          <DialogDescription>
            Xoá vĩnh viễn cuộc họp “{title}”. Biên bản, các mục đã duyệt, lịch sử chỉnh sửa và dữ liệu hỏi đáp của
            cuộc họp này sẽ bị xoá, không khôi phục được. Tin đã gửi lên Discord vẫn còn trong kênh.
          </DialogDescription>
        </DialogHeader>
        {remove.error && (
          <p role="alert" className="text-sm text-destructive">
            {remove.error.message}
          </p>
        )}
        <DialogFooter showCloseButton>
          <Button
            variant="destructive"
            disabled={remove.isPending}
            onClick={() =>
              remove.mutate(undefined, {
                onSuccess: () => {
                  setOpen(false)
                  onDeleted?.()
                },
              })
            }
          >
            <Trash2 aria-hidden />
            Xoá vĩnh viễn
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
