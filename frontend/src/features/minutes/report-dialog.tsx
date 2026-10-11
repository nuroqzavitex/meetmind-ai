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
import { useReportItem } from "./hooks"

export function ReportDialog({ itemId }: { itemId: string }) {
  const [open, setOpen] = useState(false)
  const [reason, setReason] = useState("")
  const report = useReportItem()
  const text = reason.trim()

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (!o) {
          setReason("")
          report.reset()
        }
      }}
    >
      <DialogTrigger render={<Button variant="outline" size="sm" />}>Báo sai</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Báo sai</DialogTitle>
          <DialogDescription>Mô tả chỗ sai của mục này trong biên bản.</DialogDescription>
        </DialogHeader>
        {report.isSuccess ? (
          <p role="status">Đã ghi nhận báo sai</p>
        ) : (
          <div className="space-y-2">
            <Label htmlFor={`report-${itemId}`}>Mô tả chỗ sai</Label>
            <Textarea
              id={`report-${itemId}`}
              value={reason}
              maxLength={1000}
              onChange={(e) => setReason(e.target.value)}
            />
            {report.isError && (
              <p role="alert" className="text-sm text-destructive">
                {report.error instanceof ApiError ? report.error.message : "Không gửi được báo sai."}
              </p>
            )}
          </div>
        )}
        <DialogFooter showCloseButton>
          {!report.isSuccess && (
            <Button
              disabled={text.length === 0 || report.isPending}
              onClick={() => report.mutate({ id: itemId, reason: text })}
            >
              Gửi báo sai
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
