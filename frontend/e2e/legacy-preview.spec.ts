import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.setExtraHTTPHeaders({ "x-forwarded-host": "microchips-by.test" });
});

test("legacy preview is noindex, non-commercial and has no desktop overflow", async ({ page }) => {
  const response = await page.goto("/legacy-preview/catalog");

  expect(response?.status()).toBe(200);
  expect(response?.headers()["x-robots-tag"]).toContain("noindex");
  await expect(page.getByRole("heading", { level: 1, name: "Предпросмотр перенесённого каталога" })).toBeVisible();
  await expect(page.getByText("1569")).toBeVisible();
  await expect(page.getByRole("heading", { level: 2, name: "Аккумулятор EnerSys Cyclon X Cell (AGM, 5 Ah, 2V)" })).toBeVisible();
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex.*nofollow/);
  await expect(page.getByText(/В наличии|BYN|Цена по запросу/)).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  expect((await page.locator('script[type="application/ld+json"]').allTextContents()).join(" ")).not.toContain("Offer");
});

test("legacy product card is usable at mobile width without horizontal overflow", async ({ page, isMobile }) => {
  test.skip(!isMobile, "mobile layout is verified in the mobile project");
  await page.goto("/legacy-preview/product/742");

  await expect(page.getByRole("heading", { level: 1, name: "Аккумулятор EnerSys Cyclon X Cell (AGM, 5 Ah, 2V)" })).toBeVisible();
  await expect(page.getByText("кандидат в группу дублей")).toBeVisible();
  await expect(page.getByText("КА-00005195")).toBeVisible();
  await expect(page.getByRole("img", { name: /Архивное изображение/ })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
  expect(await page.locator(".legacy-preview-product").evaluate((node) => getComputedStyle(node).gridTemplateColumns)).not.toMatch(/\s/);
});
