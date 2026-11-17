import { describe, expect, it } from "vitest";

import { formatStatus, minimumTravelDate, safeReturnPath } from "./display";

describe("display helpers", () => {
  it("turns workflow values into readable labels", () => {
    expect(formatStatus("pending_availability")).toBe("pending availability");
  });

  it("calculates tomorrow without depending on the current clock", () => {
    expect(minimumTravelDate(new Date("2026-11-17T08:00:00Z"))).toBe("2026-11-18");
  });

  it("rejects external and protocol-relative login return targets", () => {
    expect(safeReturnPath("/operator?view=queue")).toBe("/operator?view=queue");
    expect(safeReturnPath("https://evil.example")).toBe("/operator");
    expect(safeReturnPath("//evil.example")).toBe("/operator");
  });
});
