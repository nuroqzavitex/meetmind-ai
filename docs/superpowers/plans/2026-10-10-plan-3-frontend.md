# Plan 3 — Frontend (Next.js + Clerk) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Vietnamese-language web app on top of the Plan 2 API: sign in with Clerk, pick an organization, upload a transcript and watch the analysis progress, review the 7 item types side by side with the transcript, see how each topic's options evolved, publish, read and download the minutes, and report/reopen items.

**Architecture:** Next.js App Router in `frontend/`. Clerk (`@clerk/nextjs`) guards every route through `middleware.ts`; client components call the FastAPI backend with the session token from `useAuth().getToken()` through one typed `apiFetch`. Server state lives in TanStack Query; switching org clears the cache. API types are generated from the backend's OpenAPI schema with `openapi-typescript` and committed. Feature code lives in `src/features/<feature>/`, shared UI in `src/components/ui/`.

**Tech Stack:** Next.js 15 (App Router, TypeScript, React 19), `@clerk/nextjs` 6, `@tanstack/react-query` 5, Tailwind CSS 4 + shadcn/ui-style components, `openapi-typescript` 7, Vitest 3 + Testing Library + jsdom.

**Spec:** `docs/superpowers/specs/2026-10-10-meetmind-mvp-design.md` (v3) — §2 (user flow), §5.1 (frontend auth), §12.1 (API), §12.2 (frontend routes), §13.1 (frontend tests). Backend contract: `docs/backend.md` and `backend/app/schemas/*.py`. `/qa` belongs to Plan 4; Playwright e2e to Plan 5.

## Global Constraints

- Every user-visible string is Vietnamese (labels, buttons, empty states, error messages). Code identifiers stay English.
- Versions: `next@15`, `react@19`, `@clerk/nextjs@6`, `@tanstack/react-query@5`, `tailwindcss@4`, `vitest@3`, `openapi-typescript@7`. Use npm (lockfile `frontend/package-lock.json` committed).
- All backend calls go through `src/lib/api-client.ts`; components never call `fetch` directly. API base URL from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`), paths prefixed `/api/v1`.
- Request/response types come only from the generated `src/types/api.ts` (aliases in `src/lib/types.ts`); no hand-written duplicates of backend models.
- The backend error envelope `{"error": {"code", "message"}}` is surfaced as `ApiError(status, code, message)`; UI shows `message` (already Vietnamese for domain errors) and a Vietnamese fallback otherwise.
- Item types and their Vietnamese labels, in this display order: `decision` "Quyết định", `action_item` "Việc cần làm", `blocker` "Vướng mắc", `request` "Yêu cầu", `open_question` "Câu hỏi mở", `knowledge` "Tri thức", `feedback` "Góp ý".
- Meeting status labels: `draft` "Nháp", `analyzing` "Đang phân tích", `in_review` "Đang duyệt", `published` "Đã phát hành", `failed` "Lỗi". Review-state labels: `pending` "Chờ duyệt", `approved` "Đã duyệt", `edited` "Đã sửa", `rejected` "Đã bác".
- Pipeline step labels (job `step`): `start` "Bắt đầu", `normalize` "Chuẩn hoá transcript", `extract` "Trích xuất hành vi", `check_quotes` "Kiểm tra trích dẫn", `topics` "Gom chủ đề", `state_machine` "Xác định trạng thái cuối", `arbitrate` "Phân xử mâu thuẫn", `build_items` "Tạo mục", `validate` "Kiểm tra trường bắt buộc", `done` "Hoàn tất".
- Dates shown `dd/mm/yyyy`; timestamps `hh:mm:ss` as the backend sends them.
- Tests live in `frontend/tests/**/*.test.{ts,tsx}` (Ruling: not repo-root `tests/frontend/` as spec §6/§14 say, because Vite resolves bare imports from the test file's directory and `tests/frontend` cannot see `frontend/node_modules`). Tests never hit the network or real Clerk: mock `@clerk/nextjs` with `vi.mock` and the API with a fake `apiFetch`/`fetch`.
- Checks that must stay clean after every task: `cd frontend && npm run lint && npm run typecheck && npm test`. `npm run build` must succeed from Task 3 on (with a dummy publishable key, see Task 3).
- Commits: conventional messages, **no `Co-Authored-By` trailer and no "Generated with" line**. Never modify `backend/` except where a task says so.

## Review Focus

1. Switching organization while on a page → cached data of the old org must never render for the new org (query cache cleared, pages refetch). (Task 3 test.)
2. API errors (401/403/404/409/422/503, network failure, non-JSON 500) → readable Vietnamese message in the UI, no crash, no infinite spinner. (Task 2 tests + used in Tasks 4–7.)
3. Job polling stops when the job reaches `succeeded`/`failed`, and a failed analysis shows the step + error and offers "Phân tích lại". (Task 4 test.)
4. Editing a decision's content/status without a reason → the backend 422 `reason_required` is pre-empted by the UI asking for a reason; an empty edit is not sent. (Task 5 test.)
5. Clicking evidence scrolls the transcript to that utterance even when the utterance is far down the list; `?u=<id>` on the minutes page does the same on load. (Tasks 5 and 7 tests.)

---

### Task 1: Scaffold the Next.js app with test tooling

**Files:**
- Create: `frontend/` via `npx create-next-app@15 frontend --ts --tailwind --eslint --app --src-dir --import-alias "@/*" --use-npm --no-turbopack` (answer non-interactively), then remove the starter page content.
- Create: `frontend/vitest.config.ts`, `frontend/tests/setup.ts`, `frontend/tests/smoke.test.tsx`
- Create: `frontend/src/components/ui/{button,badge,card,input,textarea,label,tabs,dialog,checkbox,spinner}.tsx` and `frontend/src/lib/utils.ts` (`cn()` with `clsx` + `tailwind-merge`) — shadcn/ui components added with `npx shadcn@latest init -d` + `npx shadcn@latest add button badge card input textarea label tabs dialog checkbox -y`; if the CLI fails or prompts, hand-write equivalent minimal Tailwind components with the same file names and exported names (`Button` with `variant: "default"|"outline"|"ghost"|"destructive"` and `size: "sm"|"default"`, `Badge` with `variant: "default"|"secondary"|"destructive"|"outline"`, `Card`/`CardHeader`/`CardTitle`/`CardContent`, `Tabs`/`TabsList`/`TabsTrigger`/`TabsContent`, `Dialog`/`DialogContent`/`DialogHeader`/`DialogTitle`/`DialogFooter`). `Spinner` is always hand-written.
- Modify: `frontend/package.json` scripts: `dev`, `build`, `start`, `lint` (`next lint`), `typecheck` (`tsc --noEmit`), `test` (`vitest run`), `test:watch`.
- Modify: `.gitignore` (add `frontend/.next/`, `frontend/node_modules/`, `frontend/.env*.local`).

**Interfaces:**
- Produces: `cn(...classes)`; the UI components above; `vitest.config.ts` with `environment: "jsdom"`, `include: ["tests/**/*.test.{ts,tsx}"]`, `setupFiles: ["tests/setup.ts"]` (imports `@testing-library/jest-dom/vitest`), the `@/*` alias resolved to `src/*` (via `vite-tsconfig-paths` or `resolve.alias`), `@vitejs/plugin-react`.

- [ ] **Step 1:** Scaffold; install `vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/user-event @testing-library/jest-dom vite-tsconfig-paths` as dev deps; `clsx tailwind-merge` as deps.
- [ ] **Step 2: Write the smoke test** `tests/smoke.test.tsx`: renders `<Button>Lưu</Button>` and asserts `screen.getByRole("button", { name: "Lưu" })` is in the document; renders `<Badge variant="destructive">Lỗi</Badge>` and asserts the text.
- [ ] **Step 3:** `npm test` → PASS; `npm run lint`, `npm run typecheck`, `npm run build` → clean.
- [ ] **Step 4:** Commit `chore(frontend): scaffold Next.js app with Tailwind, UI kit and Vitest`.

---

### Task 2: Typed API client, generated types, formatting helpers

**Files:**
- Create: `backend/scripts/export_openapi.py` (prints `json.dumps(create_app(Settings(_env_file=None)).openapi(), ensure_ascii=False, indent=2)`), `frontend/openapi.json` (generated), `frontend/src/types/api.ts` (generated: `npx openapi-typescript openapi.json -o src/types/api.ts`)
- Create: `frontend/src/lib/api-client.ts`, `frontend/src/lib/types.ts`, `frontend/src/lib/format.ts`
- Modify: `frontend/package.json` script `gen:types` = `cd ../backend && uv run python scripts/export_openapi.py > ../frontend/openapi.json && cd ../frontend && openapi-typescript openapi.json -o src/types/api.ts`
- Test: `frontend/tests/lib/api-client.test.ts`, `frontend/tests/lib/format.test.ts`

**Interfaces:**
- Produces:
  - `src/lib/types.ts`: aliases from `components["schemas"]`: `MeetingSummary`, `MeetingDetail`, `MeetingCreated`, `MeetingContextIn`, `Participant`, `Utterance`, `JobOut`, `ItemOut`, `ItemAction`, `ItemPatch`, `ItemEventOut`, `TopicOut`, `ApproveCleanOut`, plus `type ItemType = ItemOut["type"]`, `type ReviewState = NonNullable<ItemOut["review_state"]>`.
  - `src/lib/api-client.ts`:
    - `class ApiError extends Error { status: number; code: string }` (message = server message or Vietnamese fallback).
    - `type TokenGetter = () => Promise<string | null>`.
    - `async function apiFetch<T>(path: string, opts: { getToken: TokenGetter; method?: "GET"|"POST"|"PATCH"; json?: unknown; form?: FormData; signal?: AbortSignal }): Promise<T>` — URL = `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1${path}`; sets `Authorization: Bearer <token>` when the getter returns one; JSON body sets `Content-Type: application/json`; `204` → `undefined as T`; non-2xx → parse envelope if JSON else `ApiError(status, "http_error", fallback)`; `fetch` rejection → `ApiError(0, "network_error", "Không kết nối được máy chủ")`.
    - `async function apiDownload(path: string, getToken: TokenGetter): Promise<{ blob: Blob; filename: string }>` — filename from `Content-Disposition` (`filename="..."`), fallback `bien-ban`.
    - Vietnamese fallbacks by status: 401 "Phiên đăng nhập đã hết hạn", 403 "Bạn cần chọn một tổ chức", 404 "Không tìm thấy dữ liệu", 409 "Thao tác xung đột với trạng thái hiện tại", 413 "File quá lớn", 422 "Dữ liệu không hợp lệ", 503 "Dịch vụ tạm thời không khả dụng", other "Đã có lỗi xảy ra".
  - `src/lib/format.ts`: `ITEM_TYPES: ItemType[]` (display order above), `ITEM_TYPE_LABEL`, `MEETING_STATUS_LABEL`, `REVIEW_STATE_LABEL`, `STEP_LABEL` (values from Global Constraints), `fmtDate(iso: string): string` (`"2026-10-08"` → `"08/10/2026"`; ISO datetimes too, in local time), `fmtPercent(p: number): string` (`0.6` → `"60%"`).

- [ ] **Step 1: Write the failing tests**
  - `api-client.test.ts` (stub `global.fetch` with `vi.fn`): sends `Authorization: Bearer t1` and the `/api/v1` prefix; `json` body serialized with content type; `form` body sent without a content-type header; 204 resolves `undefined`; 409 envelope `{"error":{"code":"pending_items","message":"Còn 3 mục chưa duyệt"}}` → `ApiError` with status 409, code `pending_items`, that message; 500 with `text/plain` body → `ApiError(500, "http_error", "Đã có lỗi xảy ra")`; fetch throwing `TypeError` → `ApiError(0, "network_error", "Không kết nối được máy chủ")`; `apiDownload` reads `attachment; filename="hop-sprint-2026-10-08.md"`.
  - `format.test.ts`: `fmtDate("2026-10-08") === "08/10/2026"`; `fmtPercent(0.6) === "60%"`; `ITEM_TYPES` equals the 7 types in order; every `ItemType` has a label.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement; run `npm run gen:types` (backend venv exists) and commit the generated files. **Step 4:** PASS; lint/typecheck/test clean.
- [ ] **Step 5:** Commit `feat(frontend): typed API client and Vietnamese formatting helpers`.

---

### Task 3: Clerk auth, org gate, app shell, query provider

**Files:**
- Create: `frontend/src/middleware.ts`, `frontend/src/app/layout.tsx` (replace), `frontend/src/app/providers.tsx`, `frontend/src/app/sign-in/[[...sign-in]]/page.tsx`, `frontend/src/app/sign-up/[[...sign-up]]/page.tsx`, `frontend/src/app/select-org/page.tsx`, `frontend/src/components/app-header.tsx`, `frontend/src/lib/use-api.ts`
- Create: `frontend/.env.example` (or document the vars in the root `.env.example` Frontend section — root is the single source; `frontend/next.config.ts` loads nothing extra)
- Test: `frontend/tests/app/providers.test.tsx`, `frontend/tests/lib/use-api.test.tsx`

**Interfaces:**
- Produces:
  - `middleware.ts`: `clerkMiddleware` — public routes `/sign-in(.*)`, `/sign-up(.*)`; everything else `auth.protect()`; signed-in without `orgId` on any route except `/select-org` → redirect to `/select-org`. Matcher = Clerk's recommended matcher (skip `_next` and static files).
  - `providers.tsx` (`"use client"`): `ClerkProvider` is in `layout.tsx` (with `localization` from `@clerk/localizations` `viVN`); `Providers` creates one `QueryClient` (`staleTime: 5_000`, `retry`: no retry on `ApiError` with status 4xx, at most 1 otherwise) and wraps children in `QueryClientProvider`; an `OrgCacheReset` child watches `useAuth().orgId` and calls `queryClient.clear()` whenever it changes from one defined value to another (and on sign-out).
  - `use-api.ts`: `function useApi(): { get<T>(path): Promise<T>; post<T>(path, json?): Promise<T>; postForm<T>(path, form): Promise<T>; patch<T>(path, json): Promise<T>; download(path): Promise<void> }` — binds `getToken` from `useAuth()`; `download` creates an object URL and clicks a temporary `<a download>`.
  - Query keys convention (used by later tasks): `["meetings", filters]`, `["meeting", id]`, `["items", meetingId]`, `["topics", meetingId]`, `["job", jobId]`, `["events", itemId]`.
  - `app-header.tsx`: app name "MeetMind", nav links "Cuộc họp" (`/`) and "Tải lên" (`/meetings/new`), `<OrganizationSwitcher hidePersonal afterSelectOrganizationUrl="/" />`, `<UserButton />`.
  - `select-org/page.tsx`: heading "Chọn tổ chức để tiếp tục", `<OrganizationList hidePersonal afterSelectOrganizationUrl="/" afterCreateOrganizationUrl="/" />`.
  - Build with no real Clerk keys: `npm run build` must pass with `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_ZXhhbXBsZS5jbGVyay5hY2NvdW50cy5kZXYk` and `CLERK_SECRET_KEY=sk_test_dummy` set in the shell; document this in `docs/frontend.md` (Task 8).

- [ ] **Step 1: Write the failing tests** (mock `@clerk/nextjs`: `useAuth` returns a mutable `{ orgId, getToken }`):
  - `providers.test.tsx`: `test_org_switch_clears_cache` — render `Providers` with a child that runs `useQuery(["meetings", {}], fn)`; after data resolves, change the mocked `orgId` from `org_a` to `org_b` and re-render → the query function is called again and the old data is not shown while refetching (assert the child renders the loading state, not org_a's data). Also: same `orgId` re-render → no refetch.
  - `use-api.test.tsx`: `get` passes the token from `getToken()` to `apiFetch` (mock `@/lib/api-client`); `download` calls `URL.createObjectURL` and clicks a link with the filename.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Install `@clerk/nextjs@6 @clerk/localizations @tanstack/react-query@5`, implement. **Step 4:** PASS; lint/typecheck/test clean; `npm run build` with the dummy keys succeeds.
- [ ] **Step 5:** Commit `feat(frontend): Clerk sign-in, organization gate and query provider`.

---

### Task 4: Meetings list, upload form, analysis progress

**Files:**
- Create: `frontend/src/app/page.tsx` (replace starter), `frontend/src/app/meetings/new/page.tsx`
- Create: `frontend/src/features/meetings/{meeting-list.tsx,status-badge.tsx,upload-form.tsx,context-form.ts,job-progress.tsx,hooks.ts}`
- Test: `frontend/tests/features/meetings/{context-form.test.ts,upload-form.test.tsx,job-progress.test.tsx,meeting-list.test.tsx}`

**Interfaces:**
- Consumes: `useApi`, query keys, labels, types (Tasks 2–3).
- Produces:
  - `hooks.ts`: `useMeetings(filters: { project?: string; status?: string })`, `useMeeting(id)`, `useJob(jobId: string | null)` (polls every 1000 ms while status is `queued`/`running`, stops otherwise), `useCreateMeeting()` (mutation → `MeetingCreated`), `useReanalyze(meetingId)`.
  - `context-form.ts` (pure): `type ContextDraft = { title: string; meetingDate: string; project: string; organizer: string; participantsText: string; glossaryText: string }`; `function buildContext(d: ContextDraft): MeetingContextIn` — trims; empty project/organizer → omitted; `participantsText` one per line in the form `Tên | vai trò | *` where `*` marks the decision maker (role and `*` optional) → `{name, role?, is_decision_maker}`; `glossaryText` one term per line; blank lines skipped. `function validateDraft(d): string[]` → Vietnamese messages: "Cần nhập tiêu đề", "Cần chọn ngày họp", "Cần chọn file transcript" (file checked by the form).
  - `upload-form.tsx`: file input accepting `.txt,.srt,.vtt,.docx`; fields: Tiêu đề, Ngày họp, Dự án, Người chủ trì, Người tham gia (textarea with the format hint above), Thuật ngữ (textarea); submit "Phân tích" builds `FormData` (`file`, `context` = JSON string) and calls `useCreateMeeting`; on success renders `JobProgress` for the returned job; on error shows the `ApiError` message.
  - `job-progress.tsx`: `JobProgress({ jobId, meetingId })` — shows `STEP_LABEL[step]` and a progress bar `fmtPercent(progress)`; `succeeded` → link "Bắt đầu duyệt" to `/meetings/{id}/review` (and auto-navigate with `router.push`); `failed` → error box with step label + `error` text and a "Phân tích lại" button (`useReanalyze`) that switches to the new job id.
  - `meeting-list.tsx` on `/`: table/cards with title, date, project, `StatusBadge`; filter by status (select) and project (text); row link: `in_review` → `/review`, `published` → `/minutes`, `analyzing` → detail with live `JobProgress` (render it inline using `active_job_id`), `failed` → shows `latest_job.error` and "Phân tích lại"; empty state "Chưa có cuộc họp nào. Tải transcript đầu tiên lên nhé." with a link to `/meetings/new`.

- [ ] **Step 1: Write the failing tests**
  - `context-form.test.ts`: `"Lan | Trưởng nhóm | *\nMinh\n\nHoa | QA"` → 3 participants, Lan `is_decision_maker: true` with role, Minh no role false, Hoa role QA; glossary `"Postgres\n\nMongoDB "` → `["Postgres","MongoDB"]`; blank project omitted; `validateDraft` empty title → contains "Cần nhập tiêu đề".
  - `upload-form.test.tsx` (mock `useApi`): submitting without a file shows "Cần chọn file transcript" and does not call `postForm`; with file + title + date calls `postForm("/meetings", FormData)` whose `context` parses to the built context; an `ApiError(422,"transcript_parse_error","Không đọc được transcript: ...")` shows that message.
  - `job-progress.test.tsx` (fake timers, mock `get`): `running` step `topics` 0.6 shows "Gom chủ đề" and "60%"; then `succeeded` → polling stops (no further `get` calls after advancing 5 s) and the review link is shown; `failed` with step `topics` and error → shows "Gom chủ đề" + error + "Phân tích lại"; clicking it posts `/meetings/{id}/reanalyze` and starts polling the new job.
  - `meeting-list.test.tsx`: renders status labels in Vietnamese and the correct link per status; empty list → the empty-state text.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS; lint/typecheck/test/build clean.
- [ ] **Step 5:** Commit `feat(frontend): meetings list, transcript upload and live analysis progress`.

---

### Task 5: Review screen — items, transcript panel, approve/edit/reject, publish

**Files:**
- Create: `frontend/src/app/meetings/[id]/review/page.tsx`
- Create: `frontend/src/features/review/{review-screen.tsx,item-card.tsx,item-edit-form.tsx,transcript-panel.tsx,review-toolbar.tsx,hooks.ts,sort.ts}`
- Test: `frontend/tests/features/review/{item-card.test.tsx,transcript-panel.test.tsx,review-screen.test.tsx,sort.test.ts}`

**Interfaces:**
- Produces:
  - `hooks.ts`: `useItems(meetingId)`, `useItemAction(meetingId)` (PATCH `/items/{id}` with `ItemAction`; on success updates the item in the `["items", meetingId]` cache), `useApproveClean(meetingId)`, `usePublish(meetingId)` (on success invalidates `["meeting", id]` and navigates to `/meetings/{id}/minutes`).
  - `sort.ts`: `groupByType(items: ItemOut[]): Record<ItemType, ItemOut[]>` (keeps server order inside a type); `countPending(items): number`.
  - `item-card.tsx`: `ItemCard({ item, onAction, onEvidenceClick, readOnly? })` — shows content; `status === "superseded"` → content with `line-through` and badge "Bị thay thế"; `supersedes` listed as "Thay cho: A, B" (struck-through option names); owner / requester / due date (`fmtDate`) / condition / rationale when present; review-state badge (`REVIEW_STATE_LABEL`); confidence badge `fmtPercent` (destructive variant when `< 0.6`); one badge per flag with Vietnamese labels `missing_owner` "Thiếu người phụ trách", `missing_due_date` "Thiếu hạn chót", `missing_requester` "Thiếu người yêu cầu", `low_confidence` "Độ tin cậy thấp", `needs_confirmation` "Cần xác nhận" (unknown flag → raw text); evidence list `[ts · speaker] "quote"` each clickable → `onEvidenceClick(utterance_id)`; buttons "Duyệt", "Sửa", "Bác" (hidden when `readOnly`).
  - `item-edit-form.tsx`: inline form for `content`, `owner`, `requester`, `due_date` (date input), `status` (select: final/superseded/rejected/open with Vietnamese labels "Chốt", "Bị thay thế", "Bị bác", "Còn mở"), `rationale`, `condition`, plus `reason` textarea. Sends only changed fields as `patch`; no change → button disabled. For `type === "decision"` when `content` or `status` changed, `reason` is required: the submit stays disabled and the hint "Sửa quyết định cần ghi lý do" is shown until a reason is typed.
  - `transcript-panel.tsx`: `TranscriptPanel({ utterances, highlightId })` — each row `id="utt-<id>"`, `[hh:mm:ss] Tên: text` (ts formatted from `start` seconds); when `highlightId` changes, `scrollIntoView({ block: "center" })` on that row and highlight it (e.g. yellow background) for 2 s.
  - `review-toolbar.tsx`: counts per review state; button "Chấp nhận mục sạch" (calls approve-clean, then toast/inline text "Đã duyệt N mục"); button "Phát hành" disabled with tooltip "Còn N mục chưa duyệt" while `countPending > 0`; 409 errors shown as returned.
  - `review-screen.tsx`: two columns on ≥ `lg` (stack on small screens): left = `Tabs` with one tab per item type in `ITEM_TYPES` order labelled `"<label> (n)"` plus a last tab "Diễn biến chủ đề" (placeholder component slot filled by Task 6 — render `<TopicTimeline meetingId=... />` imported from `@/features/topics/topic-timeline`; Task 5 creates that file as a stub that renders "Đang cập nhật…" so the import resolves); right = sticky `TranscriptPanel`. Flagged items stay first (server order). If the meeting is not `in_review`, show a banner ("Cuộc họp đang ở trạng thái: <label>") and render cards `readOnly`.
- [ ] **Step 1: Write the failing tests**
  - `item-card.test.tsx`: superseded decision renders with `line-through` class and "Bị thay thế"; `supersedes: ["MongoDB"]` renders "Thay cho" and "MongoDB"; flags render their Vietnamese labels; confidence 0.55 → "55%" badge with the destructive variant; clicking an evidence quote calls `onEvidenceClick("u0007")`; "Duyệt" calls `onAction({action: "approve"})`; `readOnly` hides the three buttons.
  - Edit form (in `item-card.test.tsx`): editing an action item's due date sends `{action:"edit", patch:{due_date:"2026-10-20"}}` only; editing a decision's content keeps submit disabled with "Sửa quyết định cần ghi lý do" until a reason is typed, then sends `{action:"edit", patch:{content:"…"}, reason:"…"}`; no change → submit disabled.
  - `transcript-panel.test.tsx`: with 200 utterances and `highlightId="u0150"`, `Element.prototype.scrollIntoView` (mocked) is called on the `utt-u0150` row.
  - `sort.test.ts`: grouping keeps order and covers all 7 keys (empty arrays included); `countPending` counts only `pending`.
  - `review-screen.test.tsx` (mock hooks/useApi): tab labels show counts; "Phát hành" disabled when pending > 0 and enabled at 0; clicking evidence in a card highlights the matching transcript row; a meeting with status `published` shows the banner and no "Duyệt" buttons.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS; lint/typecheck/test/build clean.
- [ ] **Step 5:** Commit `feat(frontend): review screen with item cards, transcript panel and publish`.

---

### Task 6: Topic timeline ("Diễn biến chủ đề")

**Files:**
- Modify: `frontend/src/features/topics/topic-timeline.tsx` (replace the Task 5 stub)
- Create: `frontend/src/features/topics/{timeline-model.ts,hooks.ts}`
- Test: `frontend/tests/features/topics/{timeline-model.test.ts,topic-timeline.test.tsx}`

**Interfaces:**
- Consumes: `TopicOut` = `{ topic_id, question, options: Record<label, { label, state, superseded_by, decided_act, acts, history: [ts: number, act: string, state_after: string][] }>, deferred, ambiguous_decides, needs_confirmation }` (check the generated type; history tuples may be typed as arrays).
- Produces:
  - `hooks.ts`: `useTopics(meetingId)`.
  - `timeline-model.ts` (pure): `type TimelineEvent = { ts: number; tsText: string; option: string; act: string; actLabel: string; stateAfter: string; stateLabel: string }`; `function buildTimeline(topic: TopicOut): TimelineEvent[]` — flattens every option's `history`, sorted by `ts` then option label; `tsText` `hh:mm:ss`. Act labels: propose "Đề xuất", support "Ủng hộ", object "Phản đối", amend "Sửa đổi", decide "Chốt", reject "Bác", defer "Hoãn", reopen "Mở lại", other → raw. State labels: proposed "Đề xuất", discussed "Đang bàn", decided "Đã chốt", rejected "Bị bác", superseded "Bị thay thế", open "Còn mở". `function finalSummary(topic): { decided: string | null; superseded: { label: string; by: string | null }[]; rejected: string[] }`.
  - `topic-timeline.tsx`: `TopicTimeline({ meetingId, onSeek? })` — one card per topic: question as title; badges "Cần xác nhận" when `needs_confirmation`, "Chờ cấp trên" when `deferred`; summary line "Kết luận: <decided>" (or "Chưa chốt"), "Bị thay thế: A → B" for superseded options; a vertical timeline of `TimelineEvent`s (time, option, act label, arrow to state label), decided rows emphasised, superseded/rejected options struck through; clicking an event calls `onSeek(utterance_id)` when the history entry can be linked to an act in `option.acts` with the same `start` (best effort; if none, not clickable). Empty → "Không có chủ đề nào cần theo dõi".
- [ ] **Step 1: Write the failing tests**
  - `timeline-model.test.ts` with a fixture topic where MongoDB is proposed at 20 s, Postgres proposed at 135 s, Postgres decided at 210 s and MongoDB superseded at 210 s: events ordered by time; the 210 s events include "Chốt" for Postgres and state "Bị thay thế" for MongoDB; `finalSummary` → `{decided: "Postgres", superseded: [{label: "MongoDB", by: "Postgres"}], rejected: []}`.
  - `topic-timeline.test.tsx` (mock `useTopics`): renders the question, "Kết luận: Postgres", "MongoDB → Postgres"; `needs_confirmation` topic shows "Cần xác nhận"; empty list shows the empty text.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement; wire `onSeek` in `review-screen.tsx` to the transcript highlight. **Step 4:** PASS; lint/typecheck/test/build clean.
- [ ] **Step 5:** Commit `feat(frontend): topic timeline showing how options were proposed, decided and superseded`.

---

### Task 7: Minutes page — read, download, report, reopen

**Files:**
- Create: `frontend/src/app/meetings/[id]/minutes/page.tsx`
- Create: `frontend/src/features/minutes/{minutes-view.tsx,report-dialog.tsx,reopen-dialog.tsx,hooks.ts}`
- Test: `frontend/tests/features/minutes/{minutes-view.test.tsx,dialogs.test.tsx}`

**Interfaces:**
- Produces:
  - `hooks.ts`: `useReportItem()` (POST `/items/{id}/report` `{reason}`), `useReopenItem(meetingId)` (POST `/items/{id}/reopen` `{reason?}`; on success invalidates meeting + items and navigates to `/meetings/{id}/review`).
  - `minutes-view.tsx`: header with title, `fmtDate(meeting_date)`, project, "Phát hành: <fmtDate(published_at)>"; buttons "Tải .md" and "Tải .json" (`useApi().download("/meetings/{id}/export?format=md|json")`); one section per item type in `ITEM_TYPES` order (headings = labels) listing only `approved`/`edited` items that are not `superseded`, rendered with `ItemCard readOnly` plus two small buttons "Báo sai" and "Mở lại"; a collapsible transcript (`TranscriptPanel`) below; reads `?u=<utterance_id>` with `useSearchParams` and highlights/scrolls to it on load (opening the transcript section). If the meeting is not `published` (e.g. reopened → `in_review`): banner "Biên bản đang được chỉnh sửa lại" with a link to the review screen.
  - `report-dialog.tsx`: textarea "Mô tả chỗ sai" (required, ≤ 1000 chars), submit "Gửi báo sai", success text "Đã ghi nhận báo sai".
  - `reopen-dialog.tsx`: optional reason, confirm "Mở lại để sửa", explains "Cuộc họp sẽ quay về trạng thái đang duyệt".
- [ ] **Step 1: Write the failing tests**
  - `minutes-view.test.tsx`: only approved/edited, non-superseded items render, grouped under Vietnamese headings in order; "Tải .md" calls `download` with `format=md`; with search param `u=u0005` the transcript is open and `scrollIntoView` is called on `utt-u0005`; non-published meeting shows the banner.
  - `dialogs.test.tsx`: report with empty text cannot submit; with text posts `{reason}` and shows "Đã ghi nhận báo sai"; reopen posts and navigates to the review route.
- [ ] **Step 2:** Run → FAIL. **Step 3:** Implement. **Step 4:** PASS; lint/typecheck/test/build clean.
- [ ] **Step 5:** Commit `feat(frontend): minutes page with downloads, report and reopen`.

---

### Task 8: Run it — Dockerfile, compose service, Makefile, docs

**Files:**
- Create: `frontend/Dockerfile` (multi-stage: `node:22-alpine` deps → build with build args `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` → runtime `next start` on port 3000; set `output: "standalone"` in `next.config.ts` and run `node server.js`), `frontend/.dockerignore`
- Modify: `docker-compose.yml` (add `frontend` service: build context `./frontend` with the two build args from env, `env_file: { path: .env, required: false }` for `CLERK_SECRET_KEY`, port 3000, `depends_on: [backend]`), `Makefile` (targets `fe-dev` = `cd frontend && npm run dev`, `fe-test` = `cd frontend && npm run lint && npm run typecheck && npm test`, `types` = `cd frontend && npm run gen:types`; extend `test` to also run `fe-test`), `.env.example` (Frontend section: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, `CLERK_SECRET_KEY`, plus `NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in`, `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up`)
- Create: `docs/frontend.md` (Vietnamese): run locally (`npm install`, `.env.local` or root `.env` values, `npm run dev`), Clerk setup reminders (enable Organizations, disable personal accounts, session token claim `name` — link to `docs/backend.md`), regenerating API types, tests, the dummy-key build command, route table (spec §12.2 minus `/qa`).

- [ ] **Step 1:** Write the files.
- [ ] **Step 2:** Verify: `docker compose config` OK; `docker compose build frontend` succeeds with dummy build args; if Docker is up, `docker compose up -d db redis backend frontend`, `curl -s -o /dev/null -w "%{http_code}" localhost:3000/sign-in` → `200` (Clerk renders with the dummy key or redirects — record the actual result), then `docker compose down` (no `-v`). Record outputs in the report.
- [ ] **Step 3:** `make fe-test` clean; backend suite still green (`cd backend && uv run pytest -q`).
- [ ] **Step 4:** Commit `chore(frontend): containerize frontend, Makefile targets and frontend docs`.
