"use client"

import { UploadForm } from "@/features/meetings/upload-form"

export default function NewMeetingPage() {
  return (
    <main className="mx-auto max-w-4xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Tải transcript mới</h1>
      <UploadForm />
    </main>
  )
}
