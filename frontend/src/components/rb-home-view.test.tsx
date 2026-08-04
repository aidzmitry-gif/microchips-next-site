import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { RbHomeView } from "@/components/rb-home-view";
import type { SitePagePayload } from "@/lib/site-api";

vi.mock("@/components/quote-form", () => ({ QuoteForm: () => <form aria-label="quote" /> }));

describe("RbHomeView", () => {
  it("renders useful B2B navigation and only real category links", () => {
    render(<RbHomeView page={page} categories={[
      { slug: "industrial", name: "Промышленные аккумуляторы", path: "/catalog/industrial", children: [] },
      { slug: "draft", name: "Черновик", path: null, children: [] },
    ]} />);

    expect(screen.getByRole("heading", { level: 1 }).textContent).toContain("Промышленные аккумуляторы");
    expect(screen.getByRole("link", { name: /Промышленные аккумуляторы/ }).getAttribute("href")).toBe("/catalog/industrial");
    expect(screen.queryByRole("link", { name: "Черновик" })).toBeNull();
    expect(screen.getByRole("link", { name: "Доставка" }).getAttribute("href")).toBe("/delivery");
    expect(screen.getByRole("form", { name: "quote" })).not.toBeNull();
  });
});

const page: SitePagePayload = {
  kind: "page",
  path: "/",
  site: {
    key: "microchips-by", domain: "microchips.by", countryCode: "BY", currencyCode: "BYN",
    defaultLocale: "ru-BY", name: "Microchips Беларусь", locales: [],
    availablePages: { delivery: "/delivery", payment: "/payment", warranty: "/warranty", contacts: "/contacts" },
  },
  page: { title: "Главная", h1: "Промышленные аккумуляторы", content: "Подбор для организаций.", locale: "ru-BY" },
  seo: { locale: "ru-BY", title: "Главная", description: "Описание", canonicalPath: "/", isIndexable: false, hreflang: {} },
};
