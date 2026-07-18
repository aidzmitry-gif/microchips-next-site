import { afterEach, describe, expect, it, vi } from "vitest";

const { fetchSitemapMock, getCurrentHostMock } = vi.hoisted(() => ({
  fetchSitemapMock: vi.fn(),
  getCurrentHostMock: vi.fn(),
}));

vi.mock("@/lib/site-api", () => ({
  fetchSitemap: fetchSitemapMock,
  getCurrentHost: getCurrentHostMock,
}));

vi.mock("next/headers", () => ({
  headers: vi.fn(async () => new Headers()),
}));

describe("sitemap route", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("maps host + sitemap entries into absolute MetadataRoute.Sitemap urls", async () => {
    getCurrentHostMock.mockResolvedValue("microchips.by");
    fetchSitemapMock.mockResolvedValue([
      { path: "/", lastModified: "2026-07-01T00:00:00.000Z" },
      { path: "/catalog/batteries", lastModified: "2026-07-10T12:30:00.000Z" },
    ]);

    const sitemap = (await import("./sitemap")).default;
    const result = await sitemap();

    expect(getCurrentHostMock).toHaveBeenCalledTimes(1);
    expect(fetchSitemapMock).toHaveBeenCalledWith("microchips.by");
    expect(result).toEqual([
      {
        url: "https://microchips.by/",
        lastModified: new Date("2026-07-01T00:00:00.000Z"),
      },
      {
        url: "https://microchips.by/catalog/batteries",
        lastModified: new Date("2026-07-10T12:30:00.000Z"),
      },
    ]);
  });

  it("falls back to an empty sitemap when fetchSitemap returns no urls", async () => {
    getCurrentHostMock.mockResolvedValue("microchips-by.test");
    fetchSitemapMock.mockResolvedValue([]);

    const sitemap = (await import("./sitemap")).default;
    const result = await sitemap();

    expect(result).toEqual([]);
  });
});
