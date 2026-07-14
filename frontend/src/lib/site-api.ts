import { headers } from "next/headers";

export type SiteProfile = {
  key: string;
  domain: string;
  countryCode: string;
  currencyCode: string;
  defaultLocale: string;
  name: string;
  locales: Array<{ locale: string; language: string; isDefault: boolean }>;
};

type SeoPayload = {
  title: string;
  description: string | null;
  canonicalPath: string;
  isIndexable: boolean;
  hreflang: Record<string, string>;
};

export type SitePagePayload = {
  kind: "page";
  site: SiteProfile;
  path: string;
  page: { title: string; h1: string; content: string | null; locale: string };
  seo: SeoPayload;
};

export type ProductPayload = {
  kind: "product";
  site: SiteProfile;
  path: string;
  product: {
    name: string;
    sku: string | null;
    mpn: string | null;
    manufacturer: string | null;
    description: string | null;
    attributes: Record<string, string> | null;
    availability: string;
    price: string | null;
    currency: string;
  };
  seo: SeoPayload;
};

export type CategoryPayload = {
  kind: "category";
  site: SiteProfile;
  path: string;
  category: { name: string; slug: string };
  seo: SeoPayload;
};

export type RedirectPayload = {
  kind: "redirect";
  site: SiteProfile;
  redirect: { to: string; status: 301 | 302 | 307 | 308 };
};

export type NotFoundPayload = { kind: "not_found"; site: SiteProfile };
export type UnavailablePayload = { kind: "unavailable" };

export type ResolvedPayload =
  | SitePagePayload
  | ProductPayload
  | CategoryPayload
  | RedirectPayload
  | NotFoundPayload
  | UnavailablePayload;

const apiBaseUrl = (process.env.LARAVEL_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export async function getCurrentHost(): Promise<string> {
  const requestHeaders = await headers();
  const forwardedHost = requestHeaders.get("x-forwarded-host")?.split(",")[0];
  const host = forwardedHost ?? requestHeaders.get("host") ?? process.env.DEFAULT_SITE_HOST ?? "microchips-by.test";

  return host.toLowerCase().replace(/^www\./, "").replace(/:\d+$/, "");
}

export async function resolveSitePath(host: string, path: string): Promise<ResolvedPayload> {
  try {
    const response = await fetch(
      `${apiBaseUrl}/api/v1/sites/${encodeURIComponent(host)}/resolve?path=${encodeURIComponent(path)}`,
      { next: { revalidate: 300, tags: [`site:${host}`, `path:${host}:${path}`] } },
    );

    if (response.status === 404) {
      return { kind: "not_found", site: emptySite(host) };
    }

    if (!response.ok) {
      return { kind: "unavailable" };
    }

    return (await response.json()) as ResolvedPayload;
  } catch {
    return { kind: "unavailable" };
  }
}

export async function fetchSitemap(host: string): Promise<Array<{ path: string; lastModified: string }>> {
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/sites/${encodeURIComponent(host)}/seo/sitemap`, {
      next: { revalidate: 300, tags: [`site:${host}`] },
    });

    if (!response.ok) return [];

    const body = (await response.json()) as { urls: Array<{ path: string; lastModified: string }> };
    return body.urls;
  } catch {
    return [];
  }
}

function emptySite(domain: string): SiteProfile {
  return {
    key: "unknown",
    domain,
    countryCode: "",
    currencyCode: "",
    defaultLocale: "ru",
    name: "Microchips",
    locales: [],
  };
}
