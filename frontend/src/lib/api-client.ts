export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export type TokenGetter = () => Promise<string | null>;

const FALLBACKS: Record<number, string> = {
  401: "Phiên đăng nhập đã hết hạn",
  403: "Bạn cần chọn một tổ chức",
  404: "Không tìm thấy dữ liệu",
  409: "Thao tác xung đột với trạng thái hiện tại",
  413: "File quá lớn",
  422: "Dữ liệu không hợp lệ",
  503: "Dịch vụ tạm thời không khả dụng",
};

// Codes whose server message may be English/generic: always use the Vietnamese fallback.
const GENERIC_CODES = new Set([
  "validation_error",
  "unauthorized",
  "no_active_org",
  "not_found",
  "http_error",
  "internal_error",
  "auth_unavailable",
  "queue_unavailable",
]);

function fallbackMessage(status: number): string {
  return FALLBACKS[status] ?? "Đã có lỗi xảy ra";
}

function baseUrl(): string {
  return `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/v1`;
}

async function send(path: string, init: RequestInit): Promise<Response> {
  try {
    return await fetch(`${baseUrl()}${path}`, init);
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(0, "network_error", "Không kết nối được máy chủ");
  }
}

async function toError(res: Response): Promise<ApiError> {
  const fallback = fallbackMessage(res.status);
  const type = res.headers.get("content-type") ?? "";
  if (type.includes("json")) {
    try {
      const body = await res.json();
      const err = body?.error;
      if (err && typeof err === "object") {
        const code = typeof err.code === "string" ? err.code : "http_error";
        const useFallback =
          res.status === 401 ||
          res.status === 403 ||
          GENERIC_CODES.has(code) ||
          typeof err.message !== "string" ||
          !err.message;
        return new ApiError(res.status, code, useFallback ? fallback : err.message);
      }
    } catch {
      // fall through
    }
  }
  return new ApiError(res.status, "http_error", fallback);
}

async function authHeaders(getToken: TokenGetter): Promise<Headers> {
  const headers = new Headers();
  const token = await getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  return headers;
}

export async function apiFetch<T>(
  path: string,
  opts: {
    getToken: TokenGetter;
    method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
    json?: unknown;
    form?: FormData;
    signal?: AbortSignal;
  },
): Promise<T> {
  const headers = await authHeaders(opts.getToken);
  let body: BodyInit | undefined;
  if (opts.form) {
    body = opts.form;
  } else if (opts.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(opts.json);
  }
  const res = await send(path, {
    method: opts.method ?? "GET",
    headers,
    body,
    signal: opts.signal,
  });
  if (!res.ok) throw await toError(res);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function apiDownload(
  path: string,
  getToken: TokenGetter,
  fallbackName = "bien-ban",
): Promise<{ blob: Blob; filename: string }> {
  const res = await send(path, { method: "GET", headers: await authHeaders(getToken) });
  if (!res.ok) throw await toError(res);
  const match = /filename="([^"]+)"/.exec(res.headers.get("Content-Disposition") ?? "");
  return { blob: await res.blob(), filename: match?.[1] ?? fallbackName };
}
