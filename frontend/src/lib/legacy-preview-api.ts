import { headers } from "next/headers";

export type LegacyPreviewProduct = {
  legacy_id: number;
  name: string;
  preview_path: string;
  legacy_url_candidate: string | null;
  primary_section_path: string | null;
  matched_section_paths: string[];
  description: string;
  one_c: { external_id: string | null; name: string | null; article: string | null };
  transfer_status: string;
  has_staging_image: boolean;
  image_path: string | null;
  source_notice: string;
};

export type LegacyPreviewCategory = {
  external_id: string | null;
  name: string;
  source_path: string;
  path: string;
  count: number;
  children: LegacyPreviewCategory[];
};

export type LegacyPreviewCatalog = {
  data: LegacyPreviewProduct[];
  meta: {
    snapshot_run_id: number;
    current_page: number;
    last_page: number;
    per_page: number;
    total: number;
    snapshot_total: number;
    visible_scope_total: number;
    excluded_total: number;
    status_counts: Record<string, number>;
    filters: { q: string | null; category: string | null; status: string | null; sort: string };
  };
};

const apiBaseUrl = (process.env.LARAVEL_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const siteKey = process.env.LEGACY_PREVIEW_SITE_KEY ?? "microchips-by";

export async function isLegacyPreviewRequestAllowed(): Promise<boolean> {
  const requestHeaders = await headers();
  return isLocalOrTestHost(requestHeaders.get("x-forwarded-host")?.split(",")[0] ?? requestHeaders.get("host"));
}

export function isLocalOrTestHost(rawHost: string | null | undefined): boolean {
  const host = (rawHost ?? "").trim().toLowerCase().replace(/^www\./, "").replace(/:\d+$/, "");
  return host === "localhost" || host === "127.0.0.1" || host === "::1" || host.endsWith(".test");
}

export async function fetchLegacyPreviewCatalog(options: {
  page?: number;
  query?: string;
  category?: string;
  status?: string;
  sort?: string;
  perPage?: number;
} = {}): Promise<LegacyPreviewCatalog> {
  const params = new URLSearchParams({
    page: String(options.page ?? 1),
    per_page: String(options.perPage ?? 24),
  });
  if (options.query) params.set("q", options.query);
  if (options.category) params.set("category", options.category);
  if (options.status) params.set("status", options.status);
  if (options.sort) params.set("sort", options.sort);

  return fetchPreviewJson<LegacyPreviewCatalog>(
    `/api/v1/sites/${encodeURIComponent(siteKey)}/legacy-preview/products?${params.toString()}`,
  );
}

export async function fetchLegacyPreviewCategories(): Promise<LegacyPreviewCategory[]> {
  const payload = await fetchPreviewJson<{ data: LegacyPreviewCategory[] }>(
    `/api/v1/sites/${encodeURIComponent(siteKey)}/legacy-preview/categories`,
  );
  return payload.data;
}

export async function fetchLegacyPreviewProduct(legacyId: number): Promise<LegacyPreviewProduct | null> {
  const response = await fetch(
    `${apiBaseUrl}/api/v1/sites/${encodeURIComponent(siteKey)}/legacy-preview/products/${legacyId}`,
    { cache: "no-store" },
  );
  if (response.status === 404) return null;
  if (!response.ok) throw new Error(`Legacy preview product failed with HTTP ${response.status}.`);
  const payload = (await response.json()) as { data: LegacyPreviewProduct };
  return payload.data;
}

export function legacyPreviewSiteKey(): string {
  return siteKey;
}

async function fetchPreviewJson<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`Legacy preview API failed with HTTP ${response.status}.`);
  return (await response.json()) as T;
}
