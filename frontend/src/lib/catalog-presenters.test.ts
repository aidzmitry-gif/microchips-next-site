import { describe, expect, it } from "vitest";
import { priceEvidenceLabel } from "./catalog-presenters";

describe("priceEvidenceLabel", () => {
  it("formats the observed calendar date without timezone shifting it", () => {
    expect(priceEvidenceLabel("42.00", "2026-06-23T00:00:00+03:00"))
      .toBe("Цена по данным на 23.06.2026 · уточняйте");
  });

  it("does not label a missing numeric price", () => {
    expect(priceEvidenceLabel(null, "2026-06-23T00:00:00+03:00")).toBeNull();
    expect(priceEvidenceLabel("", "2026-06-23T00:00:00+03:00")).toBeNull();
  });

  it("does not invent a date when current evidence is absent or malformed", () => {
    expect(priceEvidenceLabel("42.00", null)).toBeNull();
    expect(priceEvidenceLabel("42.00", "yesterday")).toBeNull();
  });
});
