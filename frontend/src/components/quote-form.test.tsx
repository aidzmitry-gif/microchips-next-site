import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QuoteForm } from "./quote-form";

const site = {
  key: "microchips-by",
  domain: "microchips.by",
  countryCode: "BY",
  currencyCode: "BYN",
  defaultLocale: "ru-BY",
  name: "Аккумуляторные решения",
  locales: [],
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("QuoteForm", () => {
  it("requires at least one contact without sending a request", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<QuoteForm site={site} subject="Товар: FIAMM" />);

    await user.type(screen.getByLabelText("Организация"), "ООО Тест");
    await user.type(screen.getByLabelText("Контактное лицо"), "Иван Иванов");
    await user.click(screen.getByRole("button", { name: "Отправить запрос" }));

    expect(screen.getByRole("alert").textContent).toContain("Укажите телефон или электронную почту");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("posts the exact lead contract with page and product context", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(<QuoteForm site={site} subject="Товар: FIAMM" />);

    await user.type(screen.getByLabelText("Организация"), "ООО Тест");
    await user.type(screen.getByLabelText("Контактное лицо"), "Иван Иванов");
    await user.type(screen.getByLabelText("Эл. почта"), "ivan@example.test");
    await user.type(screen.getByLabelText("Комментарий"), "Нужно 10 штук");
    await user.click(screen.getByRole("button", { name: "Отправить запрос" }));

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(String(options.body));
    expect(url).toBe("/api/leads/quote");
    expect(body).toMatchObject({
      site_key: "microchips-by",
      locale: "ru-BY",
      company: "ООО Тест",
      contact_name: "Иван Иванов",
      email: "ivan@example.test",
      phone: null,
      message: "Товар: FIAMM\nНужно 10 штук",
    });
    expect(body.page_url).toBe("https://microchips.by/");
    expect(await screen.findByRole("status")).toBeTruthy();
  });
});
