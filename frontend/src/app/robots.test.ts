import { afterEach, describe, expect, it, vi } from "vitest";

const { getCurrentHostMock, resolveSitePathMock } = vi.hoisted(() => ({
  getCurrentHostMock: vi.fn(),
  resolveSitePathMock: vi.fn(),
}));

vi.mock("@/lib/site-api", () => ({
  getCurrentHost: getCurrentHostMock,
  resolveSitePath: resolveSitePathMock,
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
    resolveSitePathMock.mockResolvedValue({ kind: "page", seo: { isIndexable: true } });

    const robots = (await import("./robots")).default;
    const result = await robots();

    expect(getCurrentHostMock).toHaveBeenCalledTimes(1);
    expect(resolveSitePathMock).toHaveBeenCalledWith("microchips.by", "/");
    expect(result).toEqual({
      rules: { userAgent: "*", allow: "/", disallow: ["/api/", "/search", "/filter"] },
      sitemap: "https://microchips.by/sitemap.xml",
    });
  });

  it("blocks an unknown or unprepared fallback host and omits its sitemap", async () => {
    getCurrentHostMock.mockResolvedValue("microchips-by.test");
    resolveSitePathMock.mockResolvedValue({ kind: "not_found", site: {} });

    const robots = (await import("./robots")).default;
    const result = await robots();

    expect(result).toEqual({ rules: { userAgent: "*", disallow: "/" } });
  });

  it("blocks a known site whose root page is not indexable", async () => {
    getCurrentHostMock.mockResolvedValue("preview.microchips.by");
    resolveSitePathMock.mockResolvedValue({ kind: "page", seo: { isIndexable: false } });

    const robots = (await import("./robots")).default;
    await expect(robots()).resolves.toEqual({ rules: { userAgent: "*", disallow: "/" } });
  });
});
