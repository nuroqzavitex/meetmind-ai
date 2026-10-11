"use client"

import { MeetingList } from "@/features/meetings/meeting-list"

export default function Home() {
  return (
    <main className="mx-auto max-w-4xl space-y-4 p-6">
      <h1 className="text-2xl font-semibold">Cuộc họp</h1>
      <MeetingList />
    </main>
  )
}
