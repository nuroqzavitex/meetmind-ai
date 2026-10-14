import { CheckCircle2, MessagesSquare, Quote, ShieldCheck } from "lucide-react"

import { BrandMark } from "@/components/brand"

const FEATURES = [
  { icon: CheckCircle2, text: "Giữ đúng kết luận cuối khi ý kiến thay đổi giữa buổi họp" },
  { icon: Quote, text: "Mỗi mục kèm trích dẫn nguyên văn và mốc thời gian" },
  { icon: MessagesSquare, text: "Hỏi đáp trên các biên bản đã phát hành, có nguồn" },
  { icon: ShieldCheck, text: "Dữ liệu tách riêng theo từng tổ chức" },
]

/** Two-column page for sign-in / sign-up / org selection: product pitch left, Clerk widget right. */
export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <main className="grid min-h-screen lg:grid-cols-2">
      <section className="relative hidden overflow-hidden bg-gradient-to-br from-indigo-600 via-indigo-700 to-violet-800 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div aria-hidden className="pointer-events-none absolute -top-24 -right-24 size-96 rounded-full bg-white/10 blur-3xl" />
        <div aria-hidden className="pointer-events-none absolute -bottom-32 -left-16 size-96 rounded-full bg-violet-400/20 blur-3xl" />
        <div className="relative flex items-center gap-2 text-lg font-semibold">
          <BrandMark className="bg-none bg-white/15 ring-1 ring-white/25" />
          MeetMind AI
        </div>
        <div className="relative space-y-8">
          <h2 className="max-w-lg text-4xl leading-tight font-semibold text-balance">
            Biến transcript cuộc họp thành biên bản đáng tin cậy.
          </h2>
          <ul className="space-y-4">
            {FEATURES.map(({ icon: Icon, text }) => (
              <li key={text} className="flex items-start gap-3 text-indigo-50">
                <Icon className="mt-0.5 size-5 shrink-0 text-indigo-200" aria-hidden />
                <span>{text}</span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-sm text-indigo-200">Phân tích bằng AI · con người duyệt trước khi phát hành</p>
      </section>
      <section className="flex flex-col items-center justify-center gap-6 p-6">
        <div className="flex items-center gap-2 text-lg font-semibold lg:hidden">
          <BrandMark />
          MeetMind AI
        </div>
        {children}
      </section>
    </main>
  )
}
