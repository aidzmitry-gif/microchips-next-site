import type { Metadata } from "next";
import { notFound, permanentRedirect, redirect } from "next/navigation";
import { CatalogView } from "@/components/catalog-view";
import { ProductView } from "@/components/product-view";
import { StructuredData } from "@/components/structured-data";
import { SiteHeader } from "@/components/site-header";
import { CommercialProfile } from "@/components/commercial-profile";
import { RbHomeView } from "@/components/rb-home-view";
import { OrganizationStructuredData } from "@/components/organization-structured-data";
import { ServicePageView } from "@/components/service-page-view";
import { getServicePageDefinition } from "@/data/service-pages";
import {
  fetchCatalogProducts,
  fetchCatalogCategories,
  getCurrentHost,
  resolveSitePath,
  SiteApiUnavailableError,
  type CatalogPayload,
  type CatalogCategory,
  type CatalogFilters,
  type CatalogSort,
  type ResolvedPayload,
} from "@/lib/site-api";

type PageProps = {
  params: Promise<{ path?: string[] }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export const dynamic = "force-dynamic";

export async function generateMetadata({ params, searchParams }: PageProps): Promise<Metadata> {
  const path = toPath((await params).path);
  const resolved = await resolveViewForCurrentHost(path);
  const hasCatalogQuery = hasIndexableQuery(await searchParams);

  if (!("seo" in resolved)) {
    return { title: "Microchips", robots: { index: false, follow: false } };
  }

  return {
    title: resolved.seo.title,
    description: resolved.seo.description ?? undefined,
    robots: !resolved.seo.isIndexable
      ? { index: false, follow: false }
      : hasCatalogQuery
        ? { index: false, follow: true }
        : { index: true, follow: true },
    alternates: {
      canonical: new URL(resolved.seo.canonicalPath, `https://${resolved.site.domain}`).toString(),
      languages: resolved.seo.hreflang,
    },
  };
}

function hasIndexableQuery(searchParams: Awaited<PageProps["searchParams"]>): boolean {
  if (!searchParams) return false;

  return Object.values(searchParams).some((value) => Array.isArray(value) ? value.some(Boolean) : Boolean(value));
}

export default async function SitePage({ params, searchParams }: PageProps) {
  const path = toPath((await params).path);
  const resolved = await resolveViewForCurrentHost(path);

  if (resolved.kind === "redirect") {
    if ([301, 308].includes(resolved.redirect.status)) {
      permanentRedirect(resolved.redirect.to);
    }

    redirect(resolved.redirect.to);
  }

  if (resolved.kind === "not_found") {
    notFound();
  }

  if (resolved.kind === "unavailable") {
    throw new SiteApiUnavailableError("page resolver");
  }

  const { site } = resolved;
  const catalogLocale = resolved.seo.locale ?? site.defaultLocale;
  const catalogOptions = await normalizedCatalogOptions(searchParams);
  const [categories, catalog] = await Promise.all([
    fetchCatalogCategories(site.key, catalogLocale),
    resolved.kind === "category" ? fetchCatalogProducts(site.key, {
      page: catalogOptions.page,
      perPage: 12,
      query: catalogOptions.query,
      category: resolved.category.slug || undefined,
      locale: catalogLocale,
      sort: catalogOptions.sort,
      filters: catalogOptions.filters,
    }) : Promise.resolve(null),
  ]);

  return (
    <div className="site-shell">
      <SiteHeader site={site} currentPath={path} categories={categories} currentLocale={resolved.seo.locale} localeAlternates={resolved.seo.hreflang} />
      <StructuredData value={resolved.seo.schema} />
      <OrganizationStructuredData site={site} />
      <main className="site-main">
        <Content resolved={resolved} catalog={catalog} categories={categories} query={catalogOptions.query} sort={catalogOptions.sort} filters={catalogOptions.filters} />
      </main>
      <footer className="site-footer">
        <div>
          <strong>{site.name}</strong>
          <span>Регион определяется доменом, без IP-переадресации.</span>
        </div>
        <span>{site.countryCode} · {site.defaultLocale} · {site.currencyCode}</span>
      </footer>
    </div>
  );
}

function Content({
  resolved,
  catalog,
  categories,
  query,
  sort,
  filters,
}: {
  resolved: Exclude<ResolvedPayload, { kind: "redirect" | "not_found" | "unavailable" }>;
  catalog: CatalogPayload | null;
  categories: CatalogCategory[];
  query: string;
  sort?: CatalogSort;
  filters: CatalogFilters;
}) {
  if (resolved.kind === "product") {
    return <ProductView payload={resolved} />;
  }

  if (resolved.kind === "category") {
    return <CatalogView category={resolved} catalog={catalog ?? emptyCatalog()} categories={categories} query={query} sort={sort} filters={filters} />;
  }

  if (resolved.path === "/" && resolved.site.countryCode === "BY") {
    return <RbHomeView page={resolved} categories={categories} />;
  }

  const servicePage = getServicePageDefinition(resolved.path);
  if (servicePage) {
    return <ServicePageView page={resolved} definition={servicePage} />;
  }

  return (
    <>
      <article className="content-page">
        <p className="catalog-eyebrow">{resolved.site.name}</p>
        <h1>{resolved.page.h1}</h1>
        {resolved.page.content && <p className="content-page__lead">{resolved.page.content}</p>}
      </article>
      <CommercialProfile site={resolved.site} />
    </>
  );
}

function Unavailable() {
  return (
    <main className="unavailable">
      <div>
        <p className="catalog-eyebrow">Microchips platform</p>
        <h1>Витрина ожидает подключения каталога</h1>
        <p>Laravel API сейчас недоступен. Публичные страницы не должны индексироваться до прохождения регионального SEO-чеклиста.</p>
      </div>
    </main>
  );
}

async function resolveForCurrentHost(path: string) {
  return resolveSitePath(await getCurrentHost(), path);
}

/**
 * `/catalog` is an interface root, not a taxonomy category. It must still be
 * a real useful page as soon as a first noindex catalogue wave is available;
 * otherwise breadcrumbs and the main navigation point visitors at a 404.
 * It deliberately inherits no indexability from this virtual root: only an
 * audited category URL can later be promoted in the SEO release flow.
 */
async function resolveViewForCurrentHost(path: string): Promise<ResolvedPayload> {
  const resolved = await resolveForCurrentHost(path);
  if (path !== "/catalog" || resolved.kind !== "not_found") return resolved;

  const home = await resolveForCurrentHost("/");
  if (home.kind === "not_found" || home.kind === "unavailable" || home.kind === "redirect") return resolved;

  return {
    kind: "category",
    site: home.site,
    path: "/catalog",
    category: { name: "Каталог", slug: "" },
    seo: {
      locale: home.site.defaultLocale,
      title: "Каталог | " + home.site.name,
      description: "Проверенные позиции регионального каталога.",
      canonicalPath: "/catalog",
      isIndexable: false,
      schema: null,
      hreflang: {},
    },
  };
}

function toPath(segments?: string[]): string {
  return segments?.length ? `/${segments.join("/")}` : "/";
}

async function normalizedCatalogOptions(searchParams?: PageProps["searchParams"]) {
  const values = searchParams ? await searchParams : {};
  const rawPage = Array.isArray(values.page) ? values.page[0] : values.page;
  const rawQuery = Array.isArray(values.q) ? values.q[0] : values.q;
  const rawSort = Array.isArray(values.sort) ? values.sort[0] : values.sort;
  const page = Number.parseInt(rawPage ?? "1", 10);

  return {
    page: Number.isFinite(page) && page > 0 ? page : 1,
    query: (rawQuery ?? "").trim().slice(0, 100),
    sort: ["name_asc", "name_desc", "price_asc", "price_desc"].includes(rawSort ?? "")
      ? rawSort as CatalogSort
      : undefined,
    filters: catalogFilters(values),
  };
}

function catalogFilters(values: Record<string, string | string[] | undefined>): CatalogFilters {
  const filters: CatalogFilters = {};
  for (const key of [
    "manufacturer",
    "technology",
    "nominal_voltage",
    "capacity",
    "power",
    "input_voltage",
    "output_voltage",
    "input_current",
    "output_current",
    "phase",
    "topology",
    "device_type",
  ] as const) {
    const raw = Array.isArray(values[key]) ? values[key][0] : values[key];
    const value = (raw ?? "").trim().slice(0, 255);
    if (value) filters[key] = value;
  }

  return filters;
}

function emptyCatalog(): CatalogPayload {
  return { data: [], meta: { current_page: 1, last_page: 1, total: 0 }, available: false };
}
