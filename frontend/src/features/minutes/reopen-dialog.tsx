"use client"

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
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { ApiError } from "@/lib/api-client"
import { useReopenItem } from "./hooks"

export function ReopenDialog({ itemId, meetingId }: { itemId: string; meetingId: string }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const reopen = useReopenItem(meetingId)

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger render={<Button variant="outline" size="sm" />}>Mở lại</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Mở lại mục</DialogTitle>
          <DialogDescription>Cuộc họp sẽ quay về trạng thái đang duyệt.</DialogDescription>
        </DialogHeader>
        <div className="space-y-2">
          <Label htmlFor={`reopen-${itemId}`}>Lý do (không bắt buộc)</Label>
          <Textarea
            id={`reopen-${itemId}`}
            value={reason}
            maxLength={1000}
            onChange={(e) => setReason(e.target.value)}
          />
          {reopen.isError && (
            <p role="alert" className="text-sm text-destructive">
              {reopen.error instanceof ApiError ? reopen.error.message : "Không mở lại được."}
            </p>
          )}
        </div>
        <DialogFooter showCloseButton>
          <Button
            disabled={reopen.isPending}
            onClick={() => reopen.mutate({ id: itemId, reason: reason.trim() || undefined })}
          >
            Mở lại để sửa
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
