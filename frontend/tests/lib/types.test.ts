import { describe, expect, it } from "vitest";
import type { MeetingContextIn } from "@/lib/types";

describe("types", () => {
  it("MeetingContextIn needs only title and meeting_date", () => {
    const ctx: MeetingContextIn = { title: "Họp", meeting_date: "2026-10-08" };
    // @ts-expect-error meeting_id is not part of the input model
    const bad: MeetingContextIn = { title: "x", meeting_date: "d", meeting_id: 1 };
    expect(ctx.title).toBe("Họp");
    expect(bad).toBeTruthy();
  });
});
