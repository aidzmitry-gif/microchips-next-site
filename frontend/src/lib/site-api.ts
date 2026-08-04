import { headers } from "next/headers";

export type SiteProfile = {
  key: string;
  domain: string;
  countryCode: string;
  currencyCode: string;
  defaultLocale: string;
  name: string;
  availablePagePaths?: string[];
  availablePages?: Record<string, string>;
  commercialProfile?: {
    legalName: string;
    legalAddress: string;
    phones: string[];
    email: string;
    workingHours: string | null;
    pickupAddress: string | null;
    deliveryTerms: string;
    paymentTerms: string;
    warrantyTerms: string;
  } | null;
  locales: Array<{ locale: string; language: string; isDefault: boolean }>;
};

type SeoPayload = {
  locale: string;
  title: string;
  description: string | null;
  canonicalPath: string;
  isIndexable: boolean;
  schema?: unknown | null;
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
    external_id?: string | null;
    name: string;
    sku: string | null;
    mpn: string | null;
    manufacturer: string | null;
    description: string | null;
    attributes: Record<string, string> | null;
    availability: string;
    price: string | null;
    price_observed_at?: string | null;
    currency: string;
    image_path?: string | null;
    variant_group?: ProductVariantGroup | null;
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

export type CatalogProduct = {
  slug: string;
  path?: string | null;
  name: string;
  sku: string | null;
  mpn: string | null;
  manufacturer?: string | null;
  summary_attributes?: Partial<Record<CatalogFilterKey, string>>;
  availability: string;
  price: string | null;
  price_observed_at?: string | null;
  currency: string;
  image_path?: string | null;
};

export type CatalogPayload = {
  data: CatalogProduct[];
  meta: {
    current_page: number;
    last_page: number;
    total: number;
    sort?: CatalogSort | "default";
    price_sort_enabled?: boolean;
    facets?: CatalogFacets;
    applied_filters?: Record<CatalogFilterKey, string | null>;
  };
  available: boolean;
};

export type ProductVariantOption = {
  external_id: string;
  variant_key: string;
  label: string;
  sku: string | null;
  attributes: Record<string, string>;
  availability: string;
  price: string | null;
  price_observed_at?: string | null;
  currency: string;
  image_path?: string | null;
};

export type ProductVariantGroup = {
  family_key: string;
  label: string;
  canonical_label: string;
  canonical_attributes: Record<string, string>;
  options: ProductVariantOption[];
};

export type QuoteCartLine = {
  external_id: string | null;
  variant_key: string | null;
  name: string;
  sku: string | null;
  quantity: number;
  attributes: Record<string, string>;
};

export type CatalogSort = "name_asc" | "name_desc" | "price_asc" | "price_desc";
export type CatalogFilterKey =
  | "manufacturer"
  | "technology"
  | "nominal_voltage"
  | "capacity"
  | "power"
  | "input_voltage"
  | "output_voltage"
  | "input_current"
  | "output_current"
  | "phase"
  | "topology"
  | "device_type";
export type CatalogFilters = Partial<Record<CatalogFilterKey, string>>;
export type CatalogFacetOption = { value: string; label: string; count: number };
export type CatalogFacets = Partial<Record<CatalogFilterKey, CatalogFacetOption[]>>;

export type CatalogCategory = {
  slug: string;
  name: string;
  path: string | null;
  children: CatalogCategory[];
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

export class SiteApiUnavailableError extends Error {
  constructor(operation: string, status?: number) {
    super(status ? `Site API ${operation} failed with HTTP ${status}.` : `Site API ${operation} is unavailable.`);
    this.name = "SiteApiUnavailableError";
  }
}

export async function getCurrentHost(): Promise<string> {
  const requestHeaders = await headers();
  const forwardedHost = requestHeaders.get("x-forwarded-host")?.split(",")[0];
  const fallbackHost = process.env.DEFAULT_SITE_HOST ?? "microchips-by.test";
  const host = forwardedHost ?? requestHeaders.get("host") ?? fallbackHost;
  const normalizedHost = host.toLowerCase().replace(/^www\./, "").replace(/:\d+$/, "");

  // Local ports cannot express a market hostname. Route only local preview
  // hosts through the explicitly configured profile; public domains stay strict.
  return ["localhost", "127.0.0.1", "::1"].includes(normalizedHost)
    ? fallbackHost.toLowerCase().replace(/^www\./, "").replace(/:\d+$/, "")
    : normalizedHost;
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

export async function fetchCatalogProducts(
  siteKey: string,
  options: { page?: number; perPage?: number; query?: string; category?: string; locale?: string; sort?: CatalogSort; filters?: CatalogFilters } = {},
): Promise<CatalogPayload> {
  const params = new URLSearchParams({
    page: String(options.page ?? 1),
    per_page: String(options.perPage ?? 12),
  });

  if (options.query) {
    params.set("q", options.query);
  }
  if (options.category) {
    params.set("category", options.category);
  }
  if (options.locale) {
    params.set("locale", options.locale);
  }
  if (options.sort) {
    params.set("sort", options.sort);
  }
  for (const [filter, value] of Object.entries(options.filters ?? {})) {
    if (value) params.set(filter, value);
  }

  try {
    const response = await fetch(
      `${apiBaseUrl}/api/v1/sites/${encodeURIComponent(siteKey)}/catalog/products?${params.toString()}`,
      { next: { revalidate: 300, tags: [`site:${siteKey}`, `catalog:${siteKey}`] } },
    );

    if (!response.ok) {
      return emptyCatalog(false);
    }

    const payload = (await response.json()) as Omit<CatalogPayload, "available">;

    return { ...payload, available: true };
  } catch {
    return emptyCatalog(false);
  }
}

export async function fetchCatalogCategories(siteKey: string, locale?: string): Promise<CatalogCategory[]> {
  const params = new URLSearchParams();
  if (locale) params.set("locale", locale);

  try {
    const response = await fetch(
      `${apiBaseUrl}/api/v1/sites/${encodeURIComponent(siteKey)}/catalog/categories?${params.toString()}`,
      { next: { revalidate: 300, tags: [`site:${siteKey}`, `catalog:${siteKey}`] } },
    );

    if (!response.ok) return [];

    const payload = (await response.json()) as { data: CatalogCategory[] };
    return payload.data;
  } catch {
    return [];
  }
}

export async function fetchSitemap(host: string): Promise<Array<{ path: string; lastModified: string }>> {
  try {
    const response = await fetch(`${apiBaseUrl}/api/v1/sites/${encodeURIComponent(host)}/seo/sitemap`, {
      next: { revalidate: 300, tags: [`site:${host}`] },
    });

    if (!response.ok) throw new SiteApiUnavailableError("sitemap", response.status);

    const body = (await response.json()) as { urls: Array<{ path: string; lastModified: string }> };
    return body.urls;
  } catch (error) {
    if (error instanceof SiteApiUnavailableError) throw error;

    throw new SiteApiUnavailableError("sitemap");
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

function emptyCatalog(available: boolean): CatalogPayload {
  return {
    data: [],
    meta: { current_page: 1, last_page: 1, total: 0 },
    available,
  };
}
