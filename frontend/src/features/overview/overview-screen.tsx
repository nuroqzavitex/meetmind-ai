"use client"

import { useUser } from "@clerk/nextjs"
import { CalendarClock, ClipboardList, Copy, GitCommitVertical, Send, UserRound } from "lucide-react"
import Link from "next/link"
import { useEffect, useState } from "react"

import { PageHeader } from "@/components/page-header"
import { Button } from "@/components/ui/button"
import { Spinner } from "@/components/ui/spinner"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { HOLD_INFO, HoldQuote } from "@/features/review/hold"
import { ApiError } from "@/lib/api-client"
import { fmtDate } from "@/lib/format"
import type { OverviewEntry } from "@/lib/types"
import { cn } from "@/lib/utils"
import { useAgenda, useDecisions, useSendAgenda, useTasks } from "./hooks"

const OWNER_KEY = "meetmind.overview.owner"
const EVERYONE = "*" // stored when the person chose "Mọi người", so we stop guessing

const DUE_STYLE: Record<NonNullable<OverviewEntry["due_state"]>, { label: string; className: string }> = {
  overdue: { label: "Quá hạn", className: "bg-rose-100 text-rose-900 dark:bg-rose-500/20 dark:text-rose-100" },
  today: { label: "Hôm nay", className: "bg-amber-100 text-amber-900 dark:bg-amber-500/20 dark:text-amber-100" },
  soon: { label: "Sắp đến hạn", className: "bg-sky-100 text-sky-900 dark:bg-sky-500/20 dark:text-sky-100" },
  later: { label: "Còn thời gian", className: "bg-muted text-muted-foreground" },
}

const selectClass =
  "h-9 rounded-lg border bg-background px-3 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"

function readOwner(): string | null {
  try {
    return localStorage.getItem(OWNER_KEY)
  } catch {
    return null
  }
}

function writeOwner(owner: string | null) {
  try {
    localStorage.setItem(OWNER_KEY, owner ?? EVERYONE)
  } catch {
    /* private mode: the choice just is not remembered */
  }
}

/** Link to the sentence in the minutes the entry came from. */
function Source({ e }: { e: OverviewEntry }) {
  const href = `/meetings/${e.meeting_id}/minutes${e.utterance_id ? `?u=${e.utterance_id}` : ""}`
  return (
    <Link href={href} className="text-xs text-muted-foreground hover:text-foreground hover:underline">
      {e.meeting_title} · {fmtDate(e.meeting_date)}
      {e.ts ? ` · ${e.ts}` : ""}
    </Link>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-xl border border-dashed bg-card py-8 text-center text-sm text-muted-foreground">{children}</p>
  )
}

function DueBadge({ e }: { e: OverviewEntry }) {
  if (!e.due_date || !e.due_state) return null
  const s = DUE_STYLE[e.due_state]
  return (
    <span className={cn("rounded-full px-2 py-0.5 text-xs font-medium", s.className)}>
      {s.label} · {fmtDate(e.due_date)}
    </span>
  )
}

function AgendaPanel({ project }: { project: string | null }) {
  const agenda = useAgenda(project)
  const send = useSendAgenda(project)
  const [copied, setCopied] = useState(false)
  if (agenda.isPending) return <Spinner />
  if (agenda.isError) return <p role="alert" className="text-sm text-destructive">Không tải được chương trình họp.</p>
  const a = agenda.data
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(a.markdown)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      setCopied(false)
    }
  }
  const sections: { title: string; hint: string; items: OverviewEntry[]; render: (e: OverviewEntry) => React.ReactNode }[] = [
    {
      title: "1. Cần quyết định",
      hint: "Câu hỏi mở và những gì các cuộc họp trước chưa chốt.",
      items: a.to_decide,
      render: (e) =>
        e.hold ? (
          <div className="space-y-1 rounded-md bg-amber-50/70 px-2.5 py-1.5 dark:bg-amber-950/30">
            <p className="text-xs font-medium text-amber-900 dark:text-amber-200">Chưa chốt · {HOLD_INFO[e.hold.reason].label}</p>
            <HoldQuote hold={e.hold} />
          </div>
        ) : null,
    },
    {
      title: "2. Theo dõi điều kiện",
      hint: "Quyết định và việc chỉ có hiệu lực khi điều kiện xảy ra.",
      items: a.conditions,
      render: (e) => <p className="text-sm text-muted-foreground">Điều kiện: {e.condition}</p>,
    },
    {
      title: "3. Việc quá hạn và sắp đến hạn",
      hint: "Trong vòng 7 ngày tới, hoặc đã trễ.",
      items: a.due,
      render: (e) => (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="font-medium">{e.owner ?? "Chưa có người nhận"}</span>
          <DueBadge e={e} />
        </div>
      ),
    },
  ]
  const empty = sections.every((s) => s.items.length === 0)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="mr-auto text-sm text-muted-foreground">
          Tự tổng hợp từ các biên bản đã phát hành, không dùng AI. Lập ngày {fmtDate(a.generated_on)}.
        </p>
        <Button variant="outline" size="sm" onClick={copy}>
          <Copy aria-hidden />
          {copied ? "Đã sao chép" : "Sao chép"}
        </Button>
        <Button size="sm" disabled={send.isPending} onClick={() => send.mutate()}>
          <Send aria-hidden />
          Gửi lên Discord
        </Button>
      </div>
      {send.isSuccess && <p role="status" className="text-sm text-emerald-700">Đã gửi chương trình họp lên Discord.</p>}
      {send.error && (
        <p role="alert" className="text-sm text-destructive">
          {send.error instanceof ApiError ? send.error.message : "Không gửi được lên Discord."}
        </p>
      )}
      {empty ? (
        <Empty>Không còn việc tồn đọng: mọi thứ trong các cuộc họp đã phát hành đều đã chốt.</Empty>
      ) : (
        sections.map((s) =>
          s.items.length === 0 ? null : (
            <section key={s.title} className="space-y-2">
              <div>
                <h2 className="font-semibold">{s.title}</h2>
                <p className="text-xs text-muted-foreground">{s.hint}</p>
              </div>
              <ul className="space-y-2">
                {s.items.map((e) => (
                  <li key={e.item_id} className="space-y-1.5 rounded-lg border bg-card p-3 shadow-xs">
                    <p className="font-medium">{e.content}</p>
                    {s.render(e)}
                    <Source e={e} />
                  </li>
                ))}
              </ul>
            </section>
          ),
        )
      )}
    </div>
  )
}

function TasksPanel({ project }: { project: string | null }) {
  const { user } = useUser()
  const [owner, setOwner] = useState<string | null>(null)
  // "pick": nobody chose yet, so the account's first name may be guessed (once).
  const [mode, setMode] = useState<"loading" | "pick" | "chosen">("loading")
  useEffect(() => {
    const saved = readOwner()
    setOwner(saved && saved !== EVERYONE ? saved : null)
    setMode(saved ? "chosen" : "pick")
  }, [])
  const all = useTasks(project, null)
  useEffect(() => {
    if (mode !== "pick" || !all.data || !user?.firstName) return
    const first = user.firstName.trim().toLowerCase()
    const match = all.data.owners.find((o) => o.toLowerCase() === first)
    if (match) setOwner(match)
    setMode("chosen")
  }, [mode, all.data, user?.firstName])
  const mine = useTasks(project, owner)

  if (all.isPending) return <Spinner />
  if (all.isError) return <p role="alert" className="text-sm text-destructive">Không tải được danh sách việc.</p>
  const shown = owner ? mine.data?.tasks : all.data.tasks
  return (
    <div className="space-y-4">
      <label className="flex flex-wrap items-center gap-2 text-sm">
        <UserRound aria-hidden className="size-4 text-muted-foreground" />
        <span className="font-medium">Tôi là</span>
        <select
          className={selectClass}
          value={owner ?? ""}
          onChange={(ev) => {
            const v = ev.target.value || null
            setOwner(v)
            setMode("chosen")
            writeOwner(v)
          }}
        >
          <option value="">Mọi người</option>
          {all.data.owners.map((o) => (
            <option key={o} value={o}>
              {o}
            </option>
          ))}
        </select>
        <span className="text-xs text-muted-foreground">Tên như trong biên bản. Lựa chọn được nhớ trên máy này.</span>
      </label>
      {!shown || mine.isPending ? (
        owner ? <Spinner /> : null
      ) : shown.length === 0 ? (
        <Empty>Không có việc nào{owner ? ` của ${owner}` : ""} trong các cuộc họp đã phát hành.</Empty>
      ) : (
        <ul className="space-y-2">
          {shown.map((e) => (
            <li key={e.item_id} className="flex flex-wrap items-start gap-x-3 gap-y-1 rounded-lg border bg-card p-3 shadow-xs">
              <div className="min-w-0 flex-1 space-y-1">
                <p className="font-medium">{e.content}</p>
                <Source e={e} />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {!owner && e.owner && <span className="text-sm font-medium">{e.owner}</span>}
                {e.due_date ? <DueBadge e={e} /> : <span className="text-xs text-muted-foreground">Chưa có hạn</span>}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

function DecisionsPanel({ project }: { project: string | null }) {
  const decisions = useDecisions(project)
  const [q, setQ] = useState("")
  if (decisions.isPending) return <Spinner />
  if (decisions.isError) return <p role="alert" className="text-sm text-destructive">Không tải được sổ quyết định.</p>
  const needle = q.trim().toLowerCase()
  const list = decisions.data.decisions.filter(
    (e) => !needle || e.content.toLowerCase().includes(needle) || e.supersedes.some((s) => s.toLowerCase().includes(needle)),
  )
  const byMeeting = new Map<string, OverviewEntry[]>()
  for (const e of list) byMeeting.set(e.meeting_id, [...(byMeeting.get(e.meeting_id) ?? []), e])
  return (
    <div className="space-y-4">
      <input
        type="search"
        value={q}
        onChange={(ev) => setQ(ev.target.value)}
        placeholder="Tìm quyết định, ví dụ: Postgres"
        aria-label="Tìm quyết định"
        className={cn(selectClass, "w-full max-w-sm")}
      />
      {list.length === 0 ? (
        <Empty>{needle ? "Không có quyết định nào khớp." : "Chưa có quyết định nào trong các cuộc họp đã phát hành."}</Empty>
      ) : (
        <ol className="space-y-5 border-l-2 border-primary/20 pl-5">
          {[...byMeeting.values()].map((group) => (
            <li key={group[0].meeting_id} className="relative space-y-2">
              <span aria-hidden className="absolute top-1 -left-[1.6rem] size-3 rounded-full border-2 border-primary bg-background" />
              <p className="text-sm font-semibold">
                {fmtDate(group[0].meeting_date)} · {group[0].meeting_title}
                {group[0].project ? <span className="font-normal text-muted-foreground"> · {group[0].project}</span> : null}
              </p>
              {group.map((e) => {
                const superseded = e.status === "superseded"
                return (
                  <div key={e.item_id} className={cn("space-y-1 rounded-lg border bg-card p-3 shadow-xs", superseded && "opacity-70")}>
                    <p className={cn("font-medium", superseded && "line-through")}>{e.content}</p>
                    {superseded && <p className="text-xs text-muted-foreground">Đã bị thay thế bằng một quyết định sau đó</p>}
                    {e.supersedes.length > 0 && (
                      <p className="text-sm text-muted-foreground">
                        Thay cho: {e.supersedes.map((s, i) => <span key={s}>{i > 0 && ", "}<s>{s}</s></span>)}
                      </p>
                    )}
                    {e.condition && <p className="text-sm text-muted-foreground">Điều kiện: {e.condition}</p>}
                    {e.quote && (
                      <p className="text-sm italic text-foreground/80">
                        &quot;{e.quote}&quot; <span className="not-italic text-muted-foreground">— {e.speaker}</span>
                      </p>
                    )}
                    <Source e={e} />
                  </div>
                )
              })}
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export function OverviewScreen() {
  const [project, setProject] = useState<string | null>(null)
  const projects = useDecisions(null).data?.projects ?? []
  return (
    <div className="space-y-6">
      <PageHeader
        title="Tổng hợp"
        description="Nhìn xuyên mọi cuộc họp đã phát hành: việc cần chốt tiếp, việc của từng người, các quyết định."
        actions={
          projects.length > 0 ? (
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Dự án</span>
              <select className={selectClass} value={project ?? ""} onChange={(ev) => setProject(ev.target.value || null)}>
                <option value="">Tất cả</option>
                {projects.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </label>
          ) : null
        }
      />
      <Tabs defaultValue="agenda" className="min-w-0">
        <TabsList className="h-auto w-full flex-wrap group-data-horizontal/tabs:h-auto justify-start gap-1 rounded-xl bg-muted p-1">
          <TabsTrigger value="agenda" className="h-auto flex-none gap-1.5 px-2.5 py-1.5">
            <CalendarClock aria-hidden className="size-3.5" />
            Chương trình họp kế tiếp
          </TabsTrigger>
          <TabsTrigger value="tasks" className="h-auto flex-none gap-1.5 px-2.5 py-1.5">
            <ClipboardList aria-hidden className="size-3.5" />
            Việc của tôi
          </TabsTrigger>
          <TabsTrigger value="decisions" className="h-auto flex-none gap-1.5 px-2.5 py-1.5">
            <GitCommitVertical aria-hidden className="size-3.5" />
            Sổ quyết định
          </TabsTrigger>
        </TabsList>
        <TabsContent value="agenda" className="pt-2">
          <AgendaPanel project={project} />
        </TabsContent>
        <TabsContent value="tasks" className="pt-2">
          <TasksPanel project={project} />
        </TabsContent>
        <TabsContent value="decisions" className="pt-2">
          <DecisionsPanel project={project} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
