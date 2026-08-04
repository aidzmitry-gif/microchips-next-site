import { expect, test } from "@playwright/test";

const categoryPath = "/catalog/akkumulyatory";
const productPath = "/catalog/akkumulyatory/sonnenschein-sb-12-130";
const longName = "Аккумулятор Sonnenschein Dryfit Solar Block SB 12/130 A для ИБП (GEL, 130Ah)";

test("RB catalog uses an SSR-safe commercial representation without price or Offer", async ({ page }) => {
  await page.goto(categoryPath);

  await expect(page).toHaveTitle("Тестовая карточка — Microchips");
  await expect(page.locator("h1")).toHaveText("Аккумуляторы");
  await expect(page.getByRole("link", { name: longName, exact: true })).toBeVisible();
  await expect(page.getByText("Цена по запросу")).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  const schema = await page.locator('script[type="application/ld+json"]').evaluateAll((elements) =>
    elements.map((element) => element.innerHTML).find((value) => value.includes('"@type":"Product"')) ?? "",
  );
  expect(schema).toContain('"@type":"Product"');
  expect(schema).not.toContain('"Offer"');
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).resolves.toBeTruthy();
});

test("mobile product page opens navigation, has no overflow, and sends a local inbox request", async ({ page, isMobile }) => {
  test.skip(!isMobile, "mobile behaviour is verified in the mobile project");
  await page.goto(productPath);

  await expect(page.getByRole("heading", { level: 1, name: longName })).toBeVisible();
  await expect(page.getByText("г. Минск, ул. Тимирязева, 65А, офис 408")).toBeVisible();
  await page.locator(".mobile-nav > summary").click();
  await expect(page.locator(".mobile-nav")).toHaveAttribute("open", "");
  await expect(page.locator(".mobile-nav").getByRole("link", { name: "Контакты" })).toBeVisible();
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).resolves.toBeTruthy();

  await page.getByLabel("Организация").fill("ООО Тест");
  await page.getByLabel("Контактное лицо").fill("Иван Петров");
  await page.getByLabel("Эл. почта").fill("test@example.by");
  const response = page.waitForResponse((candidate) => candidate.url().endsWith("/api/leads/quote") && candidate.request().method() === "POST");
  await page.getByRole("button", { name: "Отправить запрос" }).click();
  expect((await response).status()).toBe(201);
  await expect(page.getByRole("status")).toContainText("Запрос принят");
});
