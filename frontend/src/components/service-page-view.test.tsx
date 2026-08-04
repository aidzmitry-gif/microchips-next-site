import fs from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ServicePageView } from "@/components/service-page-view";
import { getServicePageDefinition, servicePagePaths } from "@/data/service-pages";
import type { SitePagePayload } from "@/lib/site-api";

const page: SitePagePayload = {
  kind: "page",
  path: "/services/forklift-battery-repair",
  site: {
    key: "microchips-by",
    domain: "microchips.by",
    countryCode: "BY",
    currencyCode: "BYN",
    defaultLocale: "ru-BY",
    name: "Аккумуляторные решения",
    commercialProfile: null,
    locales: [{ locale: "ru-BY", language: "ru", isDefault: true }],
  },
  page: {
    title: "Ремонт АКБ вилочных погрузчиков",
    h1: "Ремонт аккумуляторов вилочных погрузчиков",
    content: "Диагностика и ремонт тяговых аккумуляторов после проверки параметров.",
    locale: "ru-BY",
  },
  seo: {
    locale: "ru-BY",
    title: "Ремонт АКБ вилочных погрузчиков в Минске",
    description: "Диагностика и ремонт тяговых аккумуляторов.",
    canonicalPath: "/services/forklift-battery-repair",
    isIndexable: false,
    hreflang: {},
  },
};

describe("ServicePageView", () => {
  it("renders a verifiable service offer and quote form", () => {
    const definition = getServicePageDefinition(page.path);
    expect(definition).not.toBeNull();

    render(<ServicePageView page={page} definition={definition!} />);

    expect(screen.getByRole("heading", { level: 1, name: page.page.h1 })).toBeTruthy();
    expect(screen.getByText("модель погрузчика")).toBeTruthy();
    expect(screen.getByRole("heading", { name: /Рассчитать работы/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Отправить запрос" })).toBeTruthy();
    expect(screen.getByText(/Цена и срок — после проверки данных/)).toBeTruthy();
  });

  it("registers exactly the five approved service directions", () => {
    expect(servicePagePaths).toHaveLength(5);
    expect(servicePagePaths.every((path) => getServicePageDefinition(path))).toBe(true);
  });

  it("keeps the frontend definitions aligned with the noindex draft manifest", () => {
    const manifestPath = path.resolve(process.cwd(), "../docs/imports/rb-yandex-business-service-page-drafts.json");
    const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8")) as {
      pages: Array<{ path: string; title: string; h1: string; description: string; is_published: boolean; is_indexable: boolean }>;
    };

    expect(manifest.pages.map((draft) => draft.path)).toEqual(servicePagePaths);
    expect(manifest.pages.every((draft) => draft.title && draft.h1 && draft.description)).toBe(true);
    expect(manifest.pages.every((draft) => draft.is_published === false && draft.is_indexable === false)).toBe(true);
  });
});
