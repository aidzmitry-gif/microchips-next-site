import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LegacyPreviewCatalogView } from "./legacy-preview-catalog";
import type { LegacyPreviewCatalog, LegacyPreviewCategory } from "@/lib/legacy-preview-api";

describe("LegacyPreviewCatalogView", () => {
  it("renders staging identity and image without storefront commercial claims", () => {
    render(<LegacyPreviewCatalogView catalog={catalog} categories={categories} query="" />);

    expect(screen.getByRole("heading", { name: "Предпросмотр перенесённого каталога" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Аккумулятор Test 12V" })).toBeTruthy();
    expect(screen.getAllByText("строго сопоставлен с 1С").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("1C-101")).toBeTruthy();
    expect(document.querySelector("img")?.getAttribute("src")).toBe("/api/legacy-preview/media/101");
    expect(screen.queryByText("В наличии")).toBeNull();
    expect(screen.queryByText(/BYN/)).toBeNull();
    expect(screen.queryByRole("button", { name: /КП|заказ/i })).toBeNull();
  });
});

const catalog: LegacyPreviewCatalog = {
  data: [{
    legacy_id: 101,
    name: "Аккумулятор Test 12V",
    preview_path: "/legacy-preview/product/101",
    legacy_url_candidate: "/catalog/legacy/101/",
    primary_section_path: "akkumulyatory/promyshlennye",
    matched_section_paths: ["akkumulyatory/promyshlennye"],
    description: "Исходное описание.",
    one_c: { external_id: "1C-101", name: "Test", article: null },
    transfer_status: "strict_mapped_evidence",
    has_staging_image: true,
    image_path: "/api/v1/sites/microchips-by/legacy-preview/media/101",
    source_notice: "Legacy evidence",
  }],
  meta: {
    snapshot_run_id: 742,
    current_page: 1,
    last_page: 1,
    per_page: 24,
    total: 1,
    snapshot_total: 1569,
    visible_scope_total: 1562,
    excluded_total: 7,
    status_counts: { strict_mapped_evidence: 79 },
    filters: { q: null, category: null, status: null, sort: "legacy_id" },
  },
};

const categories: LegacyPreviewCategory[] = [{
  external_id: "427",
  name: "Промышленные аккумуляторы",
  source_path: "akkumulyatory/promyshlennye",
  path: "/legacy-preview/catalog/akkumulyatory/promyshlennye",
  count: 1,
  children: [],
}];
