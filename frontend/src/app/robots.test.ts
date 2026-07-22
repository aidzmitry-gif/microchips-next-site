import { afterEach, describe, expect, it, vi } from "vitest";

const { getCurrentHostMock } = vi.hoisted(() => ({
  getCurrentHostMock: vi.fn(),
}));

vi.mock("@/lib/site-api", () => ({
  getCurrentHost: getCurrentHostMock,
}));

vi.mock("next/headers", () => ({
  headers: vi.fn(async () => new Headers()),
}));

describe("robots route", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("builds rules and an absolute sitemap url from the resolved host", async () => {
    getCurrentHostMock.mockResolvedValue("microchips.by");

    const robots = (await import("./robots")).default;
    const result = await robots();

    expect(getCurrentHostMock).toHaveBeenCalledTimes(1);
    expect(result).toEqual({
      rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/search", "/filter"] },
      sitemap: "https://microchips.by/sitemap.xml",
    });
  });

  it("falls back to the default host when getCurrentHost resolves the fallback", async () => {
    getCurrentHostMock.mockResolvedValue("microchips-by.test");

    const robots = (await import("./robots")).default;
    const result = await robots();

    expect(result.sitemap).toBe("https://microchips-by.test/sitemap.xml");
  });
});
