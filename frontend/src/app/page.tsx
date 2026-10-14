"use client"

import { Upload } from "lucide-react"
import Link from "next/link"

import { buttonVariants } from "@/components/ui/button"
import { PageHeader, PageShell } from "@/components/page-header"
import { MeetingList } from "@/features/meetings/meeting-list"

export default function Home() {
  return (
    <PageShell>
      <PageHeader
        title="Cuộc họp"
        description="Transcript đã tải lên của tổ chức: phân tích, duyệt rồi phát hành thành biên bản."
        actions={
          <Link href="/meetings/new" className={buttonVariants({ size: "lg" })}>
            <Upload aria-hidden />
            Tải transcript mới
          </Link>
        }
      />
      <MeetingList />
    </PageShell>
  )
}
