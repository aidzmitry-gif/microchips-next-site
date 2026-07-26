import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SiteHeader } from "./site-header";

const site = {
  key: "microchips-by",
  domain: "microchips.by",
  countryCode: "BY",
  currencyCode: "BYN",
  defaultLocale: "ru-BY",
  name: "Аккумуляторные решения",
  availablePagePaths: ["/solutions", "/delivery", "/warranty-and-documents", "/services", "/about", "/contacts"],
  locales: [],
};

describe("SiteHeader", () => {
  it("renders the complete B2B desktop navigation and quote CTA", () => {
    render(<SiteHeader site={site} currentPath="/catalog/akkumulyatory/dlya_ibp" />);

    expect(screen.getAllByText("Каталог").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Решения").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Доставка и оплата").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Гарантия и документы").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Услуги").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("О компании").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByText("Контакты").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByRole("link", { name: "Запросить КП" }).length).toBe(2);
  });

  it("provides a native mobile accordion menu", () => {
    const { container } = render(<SiteHeader site={site} currentPath="/" />);

    expect(screen.getByText("Меню")).toBeTruthy();
    expect(container.querySelector("details.mobile-nav")).toBeTruthy();
    expect(container.querySelector(".mobile-nav .category-tree--mobile")).toBeTruthy();
  });

  it("does not render links to planned or unpublished pages", () => {
    render(<SiteHeader site={{ ...site, availablePagePaths: ["/contacts"] }} currentPath="/" />);

    expect(screen.queryByRole("link", { name: "Решения" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Доставка и оплата" })).toBeNull();
    expect(screen.getAllByRole("link", { name: "Контакты" }).length).toBeGreaterThanOrEqual(2);
  });

  it("shows only verified https hreflang alternatives as the locale switcher", () => {
    render(
      <SiteHeader
        site={site}
        currentPath="/catalog"
        currentLocale="ru-BY"
        localeAlternates={{
          "ru-RU": "https://microchips.ru/catalog",
          "uz-UZ": "https://microchips.uz/uz/catalog",
          unsafe: "//example.test/catalog",
        }}
      />,
    );

    expect(screen.getByText("ru-BY")).toBeTruthy();
    expect(screen.getByRole("link", { name: "ru-RU" }).getAttribute("href")).toBe("https://microchips.ru/catalog");
    expect(screen.getByRole("link", { name: "uz-UZ" }).getAttribute("lang")).toBe("uz");
    expect(screen.queryByRole("link", { name: "unsafe" })).toBeNull();
  });
});
