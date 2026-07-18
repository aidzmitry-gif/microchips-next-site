import { describe, expect, it, vi, beforeEach } from "vitest";

const resolveSitePathMock = vi.fn();
const getCurrentHostMock = vi.fn();
const redirectMock = vi.fn();
const notFoundMock = vi.fn();

vi.mock("@/lib/site-api", () => ({
  resolveSitePath: (...args: unknown[]) => resolveSitePathMock(...args),
  getCurrentHost: (...args: unknown[]) => getCurrentHostMock(...args),
}));

vi.mock("next/navigation", () => ({
  redirect: (...args: unknown[]) => redirectMock(...args),
  notFound: (...args: unknown[]) => notFoundMock(...args),
}));

// Import after mocks are registered so the module under test picks them up.
const { generateMetadata, default: SitePage } = await import("./page");

const site = {
  key: "rb",
  domain: "microchips.by",
  countryCode: "BY",
  currencyCode: "BYN",
  defaultLocale: "ru",
  name: "Microchips",
  locales: [{ locale: "ru", language: "ru", isDefault: true }],
};

function makeParams(path?: string[]) {
  return { params: Promise.resolve({ path }) };
}

beforeEach(() => {
  resolveSitePathMock.mockReset();
  getCurrentHostMock.mockReset();
  redirectMock.mockReset();
  notFoundMock.mockReset();
  getCurrentHostMock.mockResolvedValue("microchips.by");
});

describe("generateMetadata", () => {
  it("builds full metadata for a page kind with indexable seo", async () => {
    resolveSitePathMock.mockResolvedValue({
      kind: "page",
      site,
      path: "/about",
      page: { title: "About", h1: "About us", content: "Text", locale: "ru" },
      seo: {
        title: "About | Microchips",
        description: "About description",
        canonicalPath: "/about",
        isIndexable: true,
        hreflang: { ru: "/about", en: "/en/about" },
      },
    });

    const metadata = await generateMetadata(makeParams(["about"]));

    expect(metadata.title).toBe("About | Microchips");
    expect(metadata.description).toBe("About description");
    expect(metadata.robots).toEqual({ index: true, follow: true });
    expect(metadata.alternates?.canonical).toBe("https://microchips.by/about");
    expect(metadata.alternates?.languages).toEqual({ ru: "/about", en: "/en/about" });

    expect(resolveSitePathMock).toHaveBeenCalledWith("microchips.by", "/about");
  });

  it("builds metadata for a product kind with non-indexable seo", async () => {
    resolveSitePathMock.mockResolvedValue({
      kind: "product",
      site,
      path: "/product/battery-1",
      product: {
        name: "Battery 1",
        sku: null,
        mpn: null,
        manufacturer: null,
        description: null,
        attributes: null,
        availability: "in_stock",
        price: null,
        currency: "BYN",
      },
      seo: {
        title: "Battery 1",
        description: null,
        canonicalPath: "/product/battery-1",
        isIndexable: false,
        hreflang: {},
      },
    });

    const metadata = await generateMetadata(makeParams(["product", "battery-1"]));

    expect(metadata.title).toBe("Battery 1");
    expect(metadata.description).toBeUndefined();
    expect(metadata.robots).toEqual({ index: false, follow: false });
    expect(metadata.alternates?.canonical).toBe("https://microchips.by/product/battery-1");
  });

  it("builds metadata for a category kind", async () => {
    resolveSitePathMock.mockResolvedValue({
      kind: "category",
      site,
      path: "/category/ups",
      category: { name: "UPS", slug: "ups" },
      seo: {
        title: "UPS category",
        description: "Category description",
        canonicalPath: "/category/ups",
        isIndexable: true,
        hreflang: { ru: "/category/ups" },
      },
    });

    const metadata = await generateMetadata(makeParams(["category", "ups"]));

    expect(metadata.title).toBe("UPS category");
    expect(metadata.robots).toEqual({ index: true, follow: true });
  });

  it("falls back to a bare title for not_found (no seo field)", async () => {
    resolveSitePathMock.mockResolvedValue({ kind: "not_found", site });

    const metadata = await generateMetadata(makeParams(["missing"]));

    expect(metadata).toEqual({ title: "Microchips" });
  });

  it("falls back to a bare title for unavailable (no seo field)", async () => {
    resolveSitePathMock.mockResolvedValue({ kind: "unavailable" });

    const metadata = await generateMetadata(makeParams(undefined));

    expect(metadata).toEqual({ title: "Microchips" });
    expect(resolveSitePathMock).toHaveBeenCalledWith("microchips.by", "/");
  });

  it("falls back to a bare title for redirect (no seo field)", async () => {
    resolveSitePathMock.mockResolvedValue({
      kind: "redirect",
      site,
      redirect: { to: "/new-path", status: 301 },
    });

    const metadata = await generateMetadata(makeParams(["old-path"]));

    expect(metadata).toEqual({ title: "Microchips" });
  });

  it("resolves root path when no segments are given", async () => {
    resolveSitePathMock.mockResolvedValue({ kind: "unavailable" });

    await generateMetadata(makeParams(undefined));

    expect(resolveSitePathMock).toHaveBeenCalledWith("microchips.by", "/");
  });

  it("joins multiple path segments with slashes", async () => {
    resolveSitePathMock.mockResolvedValue({ kind: "unavailable" });

    await generateMetadata(makeParams(["a", "b", "c"]));

    expect(resolveSitePathMock).toHaveBeenCalledWith("microchips.by", "/a/b/c");
  });
});

describe("SitePage redirect/not_found branches", () => {
  it("calls redirect() with the target path for a redirect kind and does not render page content", async () => {
    resolveSitePathMock.mockResolvedValue({
      kind: "redirect",
      site,
      redirect: { to: "/new-path", status: 301 },
    });
    // redirect() throws in real Next.js to halt rendering; emulate that so
    // we can assert nothing after the call happens.
    redirectMock.mockImplementation(() => {
      throw new Error("NEXT_REDIRECT");
    });

    await expect(SitePage(makeParams(["old-path"]))).rejects.toThrow("NEXT_REDIRECT");

    expect(redirectMock).toHaveBeenCalledWith("/new-path");
    expect(notFoundMock).not.toHaveBeenCalled();
  });

  it("calls notFound() for a not_found kind", async () => {
    resolveSitePathMock.mockResolvedValue({ kind: "not_found", site });
    notFoundMock.mockImplementation(() => {
      throw new Error("NEXT_NOT_FOUND");
    });

    await expect(SitePage(makeParams(["missing"]))).rejects.toThrow("NEXT_NOT_FOUND");

    expect(notFoundMock).toHaveBeenCalledTimes(1);
    expect(redirectMock).not.toHaveBeenCalled();
  });

  it("renders the Unavailable branch without redirect/notFound for an unavailable kind", async () => {
    resolveSitePathMock.mockResolvedValue({ kind: "unavailable" });

    const result = await SitePage(makeParams(undefined));

    expect(redirectMock).not.toHaveBeenCalled();
    expect(notFoundMock).not.toHaveBeenCalled();
    // The component returns a React element tree for the Unavailable view.
    expect(result).toBeTruthy();
    expect(typeof result).toBe("object");
  });
});
