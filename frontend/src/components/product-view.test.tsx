import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ProductView } from "./product-view";
import type { ProductPayload } from "@/lib/site-api";

const basePayload: ProductPayload = {
  kind: "product",
  site: {
    key: "microchips-by",
    domain: "microchips.by",
    countryCode: "BY",
    currencyCode: "BYN",
    defaultLocale: "ru-BY",
    name: "Аккумуляторные решения",
    locales: [],
  },
  path: "/catalog/product",
  product: {
    name: "Аккумуляторная батарея с очень длинным промышленным наименованием для источника бесперебойного питания",
    sku: null,
    mpn: null,
    manufacturer: null,
    description: null,
    attributes: null,
    availability: "unknown",
    price: null,
    currency: "BYN",
  },
  seo: {
    title: "Товар",
    description: null,
    canonicalPath: "/catalog/product",
    isIndexable: false,
    hreflang: {},
  },
};

describe("ProductView", () => {
  it("renders honest fallback states without inventing product data", () => {
    render(<ProductView payload={basePayload} />);

    expect(screen.getByRole("heading", { level: 1, name: basePayload.product.name })).toBeTruthy();
    expect(screen.getByText("Изображение пока не опубликовано")).toBeTruthy();
    expect(screen.getByText("Описание пока не опубликовано. Уточните параметры у менеджера.")).toBeTruthy();
    expect(screen.getAllByText("Не указано в опубликованных данных")).toHaveLength(3);
    expect(screen.getByText("Характеристики пока не опубликованы.")).toBeTruthy();
    expect(screen.getByText("Наличие требует подтверждения")).toBeTruthy();
    expect(screen.getByText("Цена по запросу")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Отправить запрос" })).toBeTruthy();
  });

  it("shows only commercial and technical values supplied by the API", () => {
    render(
      <ProductView
        payload={{
          ...basePayload,
          product: {
            ...basePayload.product,
            manufacturer: "FIAMM",
            sku: "SKU-01",
            mpn: "12FGL120",
            description: "Проверенное описание",
            attributes: { Напряжение: "12 В", Пустое: "" },
            availability: "on_request",
            price: "125.00",
          },
        }}
      />,
    );

    expect(screen.getByText("FIAMM")).toBeTruthy();
    expect(screen.getByText("SKU-01")).toBeTruthy();
    expect(screen.getByText("12FGL120")).toBeTruthy();
    expect(screen.getByText("12 В")).toBeTruthy();
    expect(screen.queryByText("Пустое")).toBeNull();
    expect(screen.getByText("Поставка по запросу")).toBeTruthy();
    expect(screen.getByText("125.00 BYN")).toBeTruthy();
  });
});
