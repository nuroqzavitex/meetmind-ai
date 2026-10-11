import { describe, expect, it } from "vitest";
import {
  ITEM_TYPES,
  ITEM_TYPE_LABEL,
  fmtDate,
  fmtSeconds,
  fmtPercent,
} from "@/lib/format";

describe("format", () => {
  it("formats date-only strings without timezone shift", () => {
    expect(fmtDate("2026-10-08")).toBe("08/10/2026");
  });
  it("formats datetimes in local time", () => {
    expect(fmtDate("2026-10-08T12:00:00")).toBe("08/10/2026");
  });
  it("formats percent", () => {
    expect(fmtPercent(0.6)).toBe("60%");
  });
  it("lists the 7 item types in order", () => {
    expect(ITEM_TYPES).toEqual([
      "decision",
      "action_item",
      "blocker",
      "request",
      "open_question",
      "knowledge",
      "feedback",
    ]);
  });
  it("labels every type", () => {
    for (const t of ITEM_TYPES) expect(ITEM_TYPE_LABEL[t]).toBeTruthy();
  });
});

describe("fmtSeconds", () => {
  it("formats seconds as hh:mm:ss", () => {
    expect(fmtSeconds(0)).toBe("00:00:00");
    expect(fmtSeconds(65.7)).toBe("00:01:05");
    expect(fmtSeconds(3725)).toBe("01:02:05");
  });
});
