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
});
