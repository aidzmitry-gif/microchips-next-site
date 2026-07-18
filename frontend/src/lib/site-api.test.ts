import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { headersMock } = vi.hoisted(() => ({ headersMock: vi.fn() }));

vi.mock("next/headers", () => ({
  headers: headersMock,
}));

function makeHeaders(map: Record<string, string>) {
  return {
    get(name: string) {
      const key = Object.keys(map).find((k) => k.toLowerCase() === name.toLowerCase());
      return key ? map[key] : null;
    },
  };
}

describe("site-api", () => {
  const originalDefaultSiteHost = process.env.DEFAULT_SITE_HOST;
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.resetModules();
    headersMock.mockReset();
  });

  afterEach(() => {
    if (originalDefaultSiteHost === undefined) {
      delete process.env.DEFAULT_SITE_HOST;
    } else {
      process.env.DEFAULT_SITE_HOST = originalDefaultSiteHost;
    }
    global.fetch = originalFetch;
    vi.unstubAllEnvs();
  });

  describe("getCurrentHost", () => {
    it("prefers the first value from x-forwarded-host over a comma-separated list", async () => {
      headersMock.mockResolvedValue(
        makeHeaders({ "x-forwarded-host": "shop.example.com, proxy.internal", host: "ignored.example.com" }),
      );

      const { getCurrentHost } = await import("./site-api");
      await expect(getCurrentHost()).resolves.toBe("shop.example.com");
    });

    it("falls back to the host header when x-forwarded-host is absent", async () => {
      headersMock.mockResolvedValue(makeHeaders({ host: "direct.example.com" }));

      const { getCurrentHost } = await import("./site-api");
      await expect(getCurrentHost()).resolves.toBe("direct.example.com");
    });

    it("strips a leading www. and a trailing port, and lowercases the host", async () => {
      headersMock.mockResolvedValue(makeHeaders({ host: "WWW.Example.COM:8080" }));

      const { getCurrentHost } = await import("./site-api");
      await expect(getCurrentHost()).resolves.toBe("example.com");
    });

    it("falls back to DEFAULT_SITE_HOST when no headers are present", async () => {
      process.env.DEFAULT_SITE_HOST = "fallback.example.com";
      headersMock.mockResolvedValue(makeHeaders({}));

      const { getCurrentHost } = await import("./site-api");
      await expect(getCurrentHost()).resolves.toBe("fallback.example.com");
    });

    it("falls back to microchips-by.test when neither headers nor DEFAULT_SITE_HOST are set", async () => {
      delete process.env.DEFAULT_SITE_HOST;
      headersMock.mockResolvedValue(makeHeaders({}));

      const { getCurrentHost } = await import("./site-api");
      await expect(getCurrentHost()).resolves.toBe("microchips-by.test");
    });
  });

  describe("resolveSitePath", () => {
    it("returns a not_found payload with an empty site profile on a 404 response", async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 404 });

      const { resolveSitePath } = await import("./site-api");
      const result = await resolveSitePath("example.com", "/missing");

      expect(result).toEqual({
        kind: "not_found",
        site: {
          key: "unknown",
          domain: "example.com",
          countryCode: "",
          currencyCode: "",
          defaultLocale: "ru",
          name: "Microchips",
          locales: [],
        },
      });
    });

    it("returns an unavailable payload when the response is not ok and not a 404", async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false, status: 500 });

      const { resolveSitePath } = await import("./site-api");
      const result = await resolveSitePath("example.com", "/broken");

      expect(result).toEqual({ kind: "unavailable" });
    });

    it("returns the parsed JSON payload on a successful response", async () => {
      const payload = { kind: "page", site: {}, path: "/about", page: {}, seo: {} };
      global.fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => payload });

      const { resolveSitePath } = await import("./site-api");
      const result = await resolveSitePath("example.com", "/about");

      expect(result).toEqual(payload);
    });

    it("returns an unavailable payload when fetch throws", async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error("network down"));

      const { resolveSitePath } = await import("./site-api");
      const result = await resolveSitePath("example.com", "/about");

      expect(result).toEqual({ kind: "unavailable" });
    });

    it("encodes host and path into the request URL", async () => {
      const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => ({ kind: "not_found" }) });
      global.fetch = fetchMock;

      const { resolveSitePath } = await import("./site-api");
      await resolveSitePath("exämple.com", "/a b/c");

      const calledUrl = fetchMock.mock.calls[0][0] as string;
      expect(calledUrl).toContain(encodeURIComponent("exämple.com"));
      expect(calledUrl).toContain(encodeURIComponent("/a b/c"));
    });
  });

  describe("fetchSitemap", () => {
    it("returns the parsed urls array on a successful response", async () => {
      const urls = [{ path: "/", lastModified: "2026-01-01" }];
      global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ urls }) });

      const { fetchSitemap } = await import("./site-api");
      const result = await fetchSitemap("example.com");

      expect(result).toEqual(urls);
    });

    it("returns an empty array when the response is not ok", async () => {
      global.fetch = vi.fn().mockResolvedValue({ ok: false });

      const { fetchSitemap } = await import("./site-api");
      const result = await fetchSitemap("example.com");

      expect(result).toEqual([]);
    });

    it("returns an empty array when fetch throws", async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error("network down"));

      const { fetchSitemap } = await import("./site-api");
      const result = await fetchSitemap("example.com");

      expect(result).toEqual([]);
    });
  });
});
