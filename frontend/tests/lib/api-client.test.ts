import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiDownload, apiFetch } from "@/lib/api-client";

const getToken = async () => "t1";

function stub(res: Response | Error) {
  const f = vi.fn(async () => {
    if (res instanceof Error) throw res;
    return res;
  });
  vi.stubGlobal("fetch", f);
  return f;
}

afterEach(() => vi.unstubAllGlobals());

describe("apiFetch", () => {
  it("sends bearer token and /api/v1 prefix", async () => {
    const f = stub(Response.json({ ok: 1 }));
    await expect(apiFetch("/meetings", { getToken })).resolves.toEqual({ ok: 1 });
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/meetings");
    expect(new Headers(init.headers).get("Authorization")).toBe("Bearer t1");
  });
  it("serializes json body", async () => {
    const f = stub(Response.json({}));
    await apiFetch("/x", { getToken, method: "POST", json: { a: 1 } });
    const [, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.method).toBe("POST");
    expect(init.body).toBe('{"a":1}');
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
  });
  it("sends form without content-type", async () => {
    const f = stub(Response.json({}));
    const form = new FormData();
    form.append("a", "b");
    await apiFetch("/x", { getToken, method: "POST", form });
    const [, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(init.body).toBe(form);
    expect(new Headers(init.headers).get("Content-Type")).toBeNull();
  });
  it("resolves undefined on 204", async () => {
    stub(new Response(null, { status: 204 }));
    await expect(apiFetch("/x", { getToken })).resolves.toBeUndefined();
  });
  it("parses error envelope", async () => {
    stub(
      Response.json(
        { error: { code: "pending_items", message: "Còn 3 mục chưa duyệt" } },
        { status: 409 },
      ),
    );
    const err = await apiFetch("/x", { getToken }).then(() => null as never, (e: ApiError) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.code).toBe("pending_items");
    expect(err.message).toBe("Còn 3 mục chưa duyệt");
  });
  it("falls back for non-json errors", async () => {
    stub(new Response("boom", { status: 500, headers: { "content-type": "text/plain" } }));
    const err = await apiFetch("/x", { getToken }).then(() => null as never, (e: ApiError) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect([err.status, err.code, err.message]).toEqual([500, "http_error", "Đã có lỗi xảy ra"]);
  });
  it("maps network failure", async () => {
    stub(new TypeError("fail"));
    const err = await apiFetch("/x", { getToken }).then(() => null as never, (e: ApiError) => e);
    expect([err.status, err.code, err.message]).toEqual([
      0,
      "network_error",
      "Không kết nối được máy chủ",
    ]);
  });
});

describe("apiDownload", () => {
  it("reads filename from Content-Disposition", async () => {
    stub(
      new Response("# hi", {
        headers: { "Content-Disposition": 'attachment; filename="hop-sprint-2026-10-08.md"' },
      }),
    );
    const { blob, filename } = await apiDownload("/x", getToken);
    expect(filename).toBe("hop-sprint-2026-10-08.md");
    expect(blob.size).toBe(4);
  });
});

describe("generic error codes use Vietnamese fallback", () => {
  const cases: [number, string, string, string][] = [
    [422, "validation_error", "field required", "Dữ liệu không hợp lệ"],
    [401, "unauthorized", "Invalid token", "Phiên đăng nhập đã hết hạn"],
    [401, "weird_code", "Missing or malformed Authorization header", "Phiên đăng nhập đã hết hạn"],
    [403, "no_active_org", "No active organization", "Bạn cần chọn một tổ chức"],
    [403, "forbidden_x", "Forbidden", "Bạn cần chọn một tổ chức"],
    [404, "not_found", "Not Found", "Không tìm thấy dữ liệu"],
    [405, "http_error", "Method Not Allowed", "Đã có lỗi xảy ra"],
    [500, "internal_error", "Internal", "Đã có lỗi xảy ra"],
    [503, "auth_unavailable", "JWKS down", "Dịch vụ tạm thời không khả dụng"],
    [503, "queue_unavailable", "redis down", "Dịch vụ tạm thời không khả dụng"],
  ];
  it.each(cases)("%i %s", async (status, code, message, expected) => {
    stub(Response.json({ error: { code, message } }, { status }));
    const err = await apiFetch("/x", { getToken }).then(() => null as never, (e: ApiError) => e);
    expect([err.code, err.message]).toEqual([code, expected]);
  });
  it.each([
    [409, "pending_items", "Còn 3 mục chưa duyệt"],
    [409, "not_failed", "Phân tích đang chạy"],
    [413, "file_too_large", "File quá lớn (tối đa 5MB)"],
    [422, "reason_required", "Cần ghi lý do"],
  ])("keeps domain message %i %s", async (status, code, message) => {
    stub(Response.json({ error: { code, message } }, { status }));
    const err = await apiFetch("/x", { getToken }).then(() => null as never, (e: ApiError) => e);
    expect(err.message).toBe(message);
  });
});

describe("apiDownload fallback", () => {
  it("uses fallback filename without Content-Disposition", async () => {
    stub(new Response("x"));
    expect((await apiDownload("/x", getToken, "bien-ban.md")).filename).toBe("bien-ban.md");
    stub(new Response("x"));
    expect((await apiDownload("/x", getToken)).filename).toBe("bien-ban");
  });
});

describe("apiFetch edge cases", () => {
  it("rethrows AbortError", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => { throw new DOMException("aborted", "AbortError"); }));
    const err: unknown = await apiFetch("/x", { getToken }).catch((e: unknown) => e);
    expect(err).not.toBeInstanceOf(ApiError);
    expect((err as DOMException).name).toBe("AbortError");
  });
  it("falls back for JSON without envelope", async () => {
    stub(Response.json({ detail: "x" }, { status: 404 }));
    const err = await apiFetch("/x", { getToken }).then(() => null as never, (e: ApiError) => e);
    expect([err.status, err.code, err.message]).toEqual([404, "http_error", "Không tìm thấy dữ liệu"]);
  });
});
