"use client"

import { PageHeader, PageShell } from "@/components/page-header"
import { UploadForm } from "@/features/meetings/upload-form"

export default function NewMeetingPage() {
  return (
    <PageShell>
      <PageHeader
        title="Tải transcript mới"
        description="AI sẽ trích xuất quyết định, việc cần làm, vướng mắc… kèm trích dẫn nguyên văn để bạn duyệt."
      />
      <UploadForm />
    </PageShell>
  )
}
