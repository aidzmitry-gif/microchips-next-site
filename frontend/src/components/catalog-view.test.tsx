import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CatalogView, ProductCard } from "./catalog-view";
import type { CategoryPayload } from "@/lib/site-api";

const category: CategoryPayload = {
  kind: "category",
  site: {
    key: "microchips-by",
    domain: "microchips.by",
    countryCode: "BY",
    currencyCode: "BYN",
    defaultLocale: "ru-BY",
    name: "Аккумуляторные решения",
    locales: [],
  },
  path: "/catalog/akkumulyatory",
  category: { name: "Промышленные аккумуляторы", slug: "akkumulyatory" },
  seo: {
    locale: "ru-BY",
    title: "Каталог",
    description: null,
    canonicalPath: "/catalog/akkumulyatory",
    isIndexable: true,
    hreflang: {},
  },
};

describe("ProductCard", () => {
  it("does not invent price or identifiers and links to the product page", () => {
    render(
      <ProductCard
        product={{
          slug: "fiamm-12fgl120",
          name: "Аккумулятор Fiamm 12FGL120",
          sku: null,
          mpn: null,
          availability: "on_request",
          price: null,
          price_observed_at: "2026-06-23T00:00:00+03:00",
          currency: "BYN",
        }}
      />,
    );

    expect(screen.getByText("Цена по запросу")).toBeTruthy();
    expect(screen.getByText("Идентификатор требует подтверждения")).toBeTruthy();
    expect(screen.queryByText("SKU")).toBeNull();
    expect(screen.queryByText(/Цена по данным на/)).toBeNull();
    expect(screen.getByRole("link", { name: "Запросить позицию" }).getAttribute("href")).toBe("#quote-request");
  });

  it("shows only identifiers and commercial values supplied by the API", () => {
    render(
      <ProductCard
        product={{
          slug: "verified",
          path: "/catalog/verified-battery",
          name: "Verified Battery",
          sku: "SKU-01",
          mpn: "MPN-01",
          manufacturer: "FIAMM",
          summary_attributes: { technology: "AGM", nominal_voltage: "12 V", capacity: "7 Ah" },
          availability: "in_stock",
          price: "120.00",
          price_observed_at: "2026-06-23T00:00:00+03:00",
          currency: "BYN",
        }}
      />,
    );

    expect(screen.getByText("SKU-01")).toBeTruthy();
    expect(screen.getByText("MPN-01")).toBeTruthy();
    expect(screen.getByText("FIAMM")).toBeTruthy();
    expect(screen.getByText("AGM")).toBeTruthy();
    expect(screen.getByText("12 V")).toBeTruthy();
    expect(screen.getByText("7 Ah")).toBeTruthy();
    expect(screen.getByText("120.00 BYN")).toBeTruthy();
    expect(screen.getByText("Цена по данным на 23.06.2026 · уточняйте")).toBeTruthy();
    expect(screen.getByText("В наличии")).toBeTruthy();
    expect(screen.getAllByRole("link")[0].getAttribute("href")).toBe("/catalog/verified-battery");
  });
});

describe("CatalogView", () => {
  it("keeps the catalog tree compact until a mobile visitor opens it", () => {
    render(
      <CatalogView
        category={category}
        categories={[
          { name: "Аккумуляторы", slug: "akkumulyatory", path: "/catalog/akkumulyatory", children: [] },
        ]}
        catalog={{ data: [], meta: { current_page: 1, last_page: 1, total: 0 }, available: true }}
      />,
    );

    const toggle = screen.getByRole("button", { name: "Разделы каталога" });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(toggle.getAttribute("aria-controls")).toBeTruthy();
    expect(toggle.textContent).toContain("Показать");

    fireEvent.click(toggle);

    expect(screen.getByRole("button", { name: "Разделы каталога" }).getAttribute("aria-expanded")).toBe("true");
    expect(toggle.textContent).toContain("Скрыть");
    expect(document.getElementById(toggle.getAttribute("aria-controls") ?? "")?.classList.contains("is-open")).toBe(true);
  });

  it("renders the reviewed market-specific category introduction", () => {
    render(
      <CatalogView
        category={{
          ...category,
          seo: { ...category.seo, description: "Проверенный текст раздела для рынка Беларуси." },
        }}
        catalog={{ data: [], meta: { current_page: 1, last_page: 1, total: 0 }, available: true }}
      />,
    );

    expect(screen.getByText("Проверенный текст раздела для рынка Беларуси.")).toBeTruthy();
  });

  it("renders an honest empty state with a quote request", () => {
    render(
      <CatalogView
        category={category}
        catalog={{ data: [], meta: { current_page: 1, last_page: 1, total: 0 }, available: true }}
      />,
    );

    expect(screen.getByText("Публикация позиций ещё не завершена")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "Запросить КП" })[0].getAttribute("href")).toBe("#quote-request");
    expect(screen.queryByRole("heading", { name: "Реквизиты и порядок работы" })).toBeNull();
  });

  it("renders simple SSR pagination and preserves the search query", () => {
    render(
      <CatalogView
        category={category}
        query="Fiamm"
        catalog={{
          data: [{
            slug: "fiamm",
            name: "Fiamm",
            sku: null,
            mpn: null,
            availability: "on_request",
            price: null,
            currency: "BYN",
          }],
          meta: { current_page: 2, last_page: 4, total: 37 },
          available: true,
        }}
      />,
    );

    expect(screen.getByText("Результаты поиска: 37")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Далее" }).getAttribute("href")).toBe(
      "/catalog/akkumulyatory?q=Fiamm&page=3",
    );
    expect(screen.getByRole("link", { name: "2" }).getAttribute("aria-current")).toBe("page");
  });

  it("keeps the selected sort order on previous and next catalog pages", () => {
    render(
      <CatalogView
        category={category}
        query="Fiamm"
        sort="name_desc"
        filters={{ manufacturer: "FIAMM", technology: "AGM" }}
        catalog={{
          data: [{
            slug: "fiamm-6sla100",
            name: "FIAMM 6SLA100",
            sku: null,
            mpn: "6SLA100",
            availability: "on_request",
            price: null,
            currency: "BYN",
          }],
          meta: {
            current_page: 2,
            last_page: 4,
            total: 37,
            facets: {
              manufacturer: [{ value: "FIAMM", label: "FIAMM", count: 37 }],
              technology: [{ value: "AGM", label: "AGM", count: 37 }],
              nominal_voltage: [],
              capacity: [],
            },
          },
          available: true,
        }}
      />,
    );

    expect(screen.getByRole("link", { name: "Назад" }).getAttribute("href")).toBe(
      "/catalog/akkumulyatory?q=Fiamm&sort=name_desc&manufacturer=FIAMM&technology=AGM",
    );
    expect(screen.getByRole("link", { name: "Далее" }).getAttribute("href")).toBe(
      "/catalog/akkumulyatory?q=Fiamm&sort=name_desc&manufacturer=FIAMM&technology=AGM&page=3",
    );
    expect((screen.getByLabelText("Производитель") as HTMLSelectElement).value).toBe("FIAMM");
    expect((screen.getByLabelText("Технология") as HTMLSelectElement).value).toBe("AGM");
    expect(screen.queryByRole("option", { name: /Цена:/ })).toBeNull();
    expect(screen.getByRole("link", { name: "Сбросить" }).getAttribute("href")).toBe("/catalog/akkumulyatory");
  });

  it("renders source-backed power facets and preserves them in SSR pagination", () => {
    render(
      <CatalogView
        category={{
          ...category,
          path: "/catalog/power-systems/ups-systems",
          category: { name: "Источники бесперебойного питания", slug: "catalog/power-systems/ups-systems" },
        }}
        filters={{ power: "6 кВт", phase: "1/1", topology: "On-line", device_type: "ИБП" }}
        catalog={{
          data: [{
            slug: "hiden-udc9206s",
            name: "Hiden Expert UDC9206S",
            sku: null,
            mpn: "Expert UDC9206S",
            summary_attributes: { power: "6 кВт", phase: "1/1", topology: "On-line", device_type: "ИБП" },
            availability: "on_request",
            price: null,
            currency: "BYN",
          }],
          meta: {
            current_page: 1,
            last_page: 2,
            total: 13,
            facets: {
              power: [{ value: "6 кВт", label: "6 кВт", count: 1 }],
              phase: [{ value: "1/1", label: "1/1", count: 1 }],
              topology: [{ value: "On-line", label: "On-line", count: 1 }],
              device_type: [{ value: "ИБП", label: "ИБП", count: 1 }],
            },
          },
          available: true,
        }}
      />,
    );

    expect((screen.getByLabelText("Мощность") as HTMLSelectElement).value).toBe("6 кВт");
    expect(screen.getByRole("group", { name: "Фильтры каталога" })).toBeTruthy();
    expect((screen.getByLabelText("Фазность") as HTMLSelectElement).value).toBe("1/1");
    expect((screen.getByLabelText("Топология") as HTMLSelectElement).value).toBe("On-line");
    expect((screen.getByLabelText("Тип устройства") as HTMLSelectElement).value).toBe("ИБП");
    expect(screen.getByText("6 кВт")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Далее" }).getAttribute("href")).toBe(
      "/catalog/power-systems/ups-systems?power=6+%D0%BA%D0%92%D1%82&phase=1%2F1&topology=On-line&device_type=%D0%98%D0%91%D0%9F&page=2",
    );
  });
});
