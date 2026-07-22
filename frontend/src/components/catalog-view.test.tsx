import { render, screen } from "@testing-library/react";
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
          currency: "BYN",
        }}
      />,
    );

    expect(screen.getByText("Цена по запросу")).toBeTruthy();
    expect(screen.getByText("Идентификатор требует подтверждения")).toBeTruthy();
    expect(screen.queryByText("SKU")).toBeNull();
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
          availability: "in_stock",
          price: "120.00",
          currency: "BYN",
        }}
      />,
    );

    expect(screen.getByText("SKU-01")).toBeTruthy();
    expect(screen.getByText("MPN-01")).toBeTruthy();
    expect(screen.getByText("120.00 BYN")).toBeTruthy();
    expect(screen.getByText("В наличии")).toBeTruthy();
    expect(screen.getAllByRole("link")[0].getAttribute("href")).toBe("/catalog/verified-battery");
  });
});

describe("CatalogView", () => {
  it("renders an honest empty state with a quote request", () => {
    render(
      <CatalogView
        category={category}
        catalog={{ data: [], meta: { current_page: 1, last_page: 1, total: 0 }, available: true }}
      />,
    );

    expect(screen.getByText("Публикация позиций ещё не завершена")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: "Запросить КП" })[0].getAttribute("href")).toBe("#quote-request");
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
});
