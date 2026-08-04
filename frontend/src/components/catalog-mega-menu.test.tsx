import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CatalogMegaMenu } from "./catalog-mega-menu";

const categories = [
  {
    slug: "industrial",
    name: "Аккумуляторы для бизнеса",
    path: "/catalog/industrial-batteries",
    children: [{
      slug: "ups",
      name: "Аккумуляторы для ИБП",
      path: "/catalog/industrial-batteries/batteries-ups",
      children: [{ slug: "agm", name: "AGM", path: "/catalog/industrial-batteries/batteries-ups/agm", children: [] }],
    }],
  },
  {
    slug: "power",
    name: "Системы питания",
    path: "/catalog/power-systems",
    children: [{ slug: "ups-systems", name: "ИБП", path: "/catalog/power-systems/ups-systems", children: [] }],
  },
];

describe("CatalogMegaMenu", () => {
  it("selects the root containing the current canonical path", () => {
    render(<CatalogMegaMenu categories={categories} currentPath="/catalog/power-systems/ups-systems" />);

    expect(screen.getByRole("tab", { name: /Системы питания/ }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("link", { name: "ИБП" }).getAttribute("href")).toBe("/catalog/power-systems/ups-systems");
  });

  it("switches panels by click and keyboard while preserving API paths", () => {
    render(<CatalogMegaMenu categories={categories} currentPath="/catalog/industrial-batteries" />);
    const power = screen.getByRole("tab", { name: /Системы питания/ });
    fireEvent.click(power);

    expect(power.getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("link", { name: "Все товары раздела" }).getAttribute("href")).toBe("/catalog/power-systems");

    fireEvent.keyDown(power, { key: "Home" });
    expect(screen.getByRole("tab", { name: /Аккумуляторы для бизнеса/ }).getAttribute("aria-selected")).toBe("true");
  });

  it("keeps pathless nodes as text", () => {
    render(<CatalogMegaMenu categories={[{ ...categories[0], children: [{ ...categories[0].children[0], path: null }] }]} />);

    expect(screen.getByText("Аккумуляторы для ИБП")).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Аккумуляторы для ИБП" })).toBeNull();
  });
});
