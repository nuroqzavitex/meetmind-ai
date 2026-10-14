import type { ItemType, ReviewState } from "@/lib/types";

export const ITEM_TYPES: ItemType[] = [
  "decision",
  "action_item",
  "blocker",
  "request",
  "open_question",
  "knowledge",
  "feedback",
];

export const ITEM_TYPE_LABEL: Record<ItemType, string> = {
  decision: "Quyết định",
  action_item: "Việc cần làm",
  blocker: "Vướng mắc",
  request: "Yêu cầu",
  open_question: "Câu hỏi mở",
  knowledge: "Tri thức",
  feedback: "Góp ý",
};

export const MEETING_STATUS_LABEL: Record<string, string> = {
  draft: "Nháp",
  transcribing: "Đang chuyển giọng nói",
  awaiting_speakers: "Chờ gán người nói",
  analyzing: "Đang phân tích",
  in_review: "Đang duyệt",
  published: "Đã phát hành",
  failed: "Lỗi",
};

export const REVIEW_STATE_LABEL: Record<ReviewState, string> = {
  pending: "Chờ duyệt",
  approved: "Đã duyệt",
  edited: "Đã sửa",
  rejected: "Đã bác",
};

export const STEP_LABEL: Record<string, string> = {
  start: "Bắt đầu",
  transcribe: "Chuyển giọng nói thành văn bản",
  normalize: "Chuẩn hoá transcript",
  extract: "Trích xuất hành vi",
  check_quotes: "Kiểm tra trích dẫn",
  topics: "Gom chủ đề",
  state_machine: "Xác định trạng thái cuối",
  arbitrate: "Phân xử mâu thuẫn",
  build_items: "Tạo mục",
  validate: "Kiểm tra trường bắt buộc",
  done: "Hoàn tất",
};

const pad = (n: number) => String(n).padStart(2, "0");

/** Audio files are transcribed (with speaker separation) before analysis. */
export const AUDIO_EXTENSIONS = [".mp3", ".m4a", ".wav", ".webm", ".mp4", ".mpeg", ".mpga"];
export const TRANSCRIPT_EXTENSIONS = [".txt", ".srt", ".vtt", ".docx"];

export function isAudioFile(name: string): boolean {
  const lower = name.toLowerCase();
  return AUDIO_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

export function fmtDate(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (m) return `${m[3]}/${m[2]}/${m[1]}`;
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()}`;
}

export function fmtPercent(p: number): string {
  return `${Math.round(p * 100)}%`;
}

export function fmtSeconds(sec: number): string {
  const s = Math.max(0, Math.floor(sec));
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor((s % 3600) / 60))}:${pad(s % 60)}`;
}
