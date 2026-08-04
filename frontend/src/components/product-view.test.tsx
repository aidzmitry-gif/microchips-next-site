import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    external_id: "TEST-001",
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
    locale: "ru-BY",
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
            price_observed_at: "2026-06-23T00:00:00+03:00",
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
    expect(screen.getByText("Цена по данным на 23.06.2026 · уточняйте")).toBeTruthy();
  });

  it("renders regional commercial details only when the API supplies a complete verified profile", () => {
    render(
      <ProductView
        payload={{
          ...basePayload,
          site: {
            ...basePayload.site,
            commercialProfile: {
              legalName: "ООО «Аккумуляторные решения»",
              legalAddress: "Минск, пом. 407",
              phones: ["+375 (33) 347-75-10"],
              email: "order@microchips.by",
              workingHours: "пн–пт 9:00–17:00",
              pickupAddress: "Минск, офис 408",
              deliveryTerms: "Доставка по согласованию.",
              paymentTerms: "Оплата по счёту.",
              warrantyTerms: "Гарантия по документации производителя.",
            },
          },
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Реквизиты и порядок работы" })).toBeTruthy();
    expect(screen.getByText("Минск, офис 408")).toBeTruthy();
    expect(screen.getByText("Гарантия по документации производителя.")).toBeTruthy();
  });

  it("selects a verified variant without changing the canonical product heading", async () => {
    const user = userEvent.setup();
    render(
      <ProductView
        payload={{
          ...basePayload,
          product: {
            ...basePayload.product,
            name: "CSB GP1272",
            price: null,
            variant_group: {
              family_key: "csb-gp1272",
              label: "Тип вывода",
              canonical_label: "F1 / Faston 187",
              canonical_attributes: { "Тип вывода": "F1 / Faston 187" },
              options: [{
                external_id: "КА-00001276",
                variant_key: "f2",
                label: "F2 / Faston 250",
                sku: "GP1272-F2",
                attributes: { "Тип вывода": "F2 / Faston 250" },
                availability: "on_request",
                price: "88.00",
                currency: "BYN",
                image_path: "/api/v1/media/42",
              }],
            },
          },
        }}
      />,
    );

    await user.click(screen.getByRole("radio", { name: "F2 / Faston 250" }));

    expect(screen.getByRole("heading", { level: 1, name: "CSB GP1272" })).toBeTruthy();
    expect(screen.getByText("88.00 BYN")).toBeTruthy();
    expect(screen.getByLabelText("Параметры варианта F2 / Faston 250")).toBeTruthy();
    expect(screen.getByRole("img", { name: "CSB GP1272 — F2 / Faston 250" }).getAttribute("src")).toBe("/api/media/42");
    expect(window.location.pathname).toBe("/");
  });
});
