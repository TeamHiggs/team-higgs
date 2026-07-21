import { describe, it, expect } from "vitest";
import { fmtTokens, fmtInt, fmtCost, relativeTime, riskDotClass, severityRank } from "./format";

describe("format helpers", () => {
  it("fmtTokens abbreviates thousands", () => {
    expect(fmtTokens(52310)).toBe("52.3k");
    expect(fmtTokens(127757)).toBe("128k");
    expect(fmtTokens(640)).toBe("640");
    expect(fmtTokens(null)).toBe("—");
  });

  it("fmtInt localises and handles null", () => {
    expect(fmtInt(1234)).toBe((1234).toLocaleString());
    expect(fmtInt(null)).toBe("—");
  });

  it("fmtCost renders a dollar figure or a dash", () => {
    expect(fmtCost("0.83")).toBe("$0.83");
    expect(fmtCost(null)).toBe("—");
    expect(fmtCost("")).toBe("—");
  });

  it("relativeTime speaks the mockup's coarse register", () => {
    const now = Date.parse("2026-07-21T12:00:00Z");
    expect(relativeTime("2026-07-21T11:59:40Z", now)).toBe("just now");
    expect(relativeTime("2026-07-21T09:00:00Z", now)).toBe("3h ago");
    expect(relativeTime("2026-07-20T12:00:00Z", now)).toBe("yesterday");
    expect(relativeTime("2026-07-19T12:00:00Z", now)).toBe("2d ago");
    expect(relativeTime(null, now)).toBe("—");
  });

  it("maps risk + severity to presentation classes", () => {
    expect(riskDotClass("high")).toBe("hi");
    expect(riskDotClass("medium")).toBe("md");
    expect(riskDotClass("low")).toBe("lo");
    expect(severityRank("high")).toBeLessThan(severityRank("medium"));
    expect(severityRank("medium")).toBeLessThan(severityRank("low"));
  });
});
