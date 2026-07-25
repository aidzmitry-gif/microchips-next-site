import type { Metadata } from "next";
import { notFound, redirect } from "next/navigation";
import { CatalogView } from "@/components/catalog-view";
import { ProductView } from "@/components/product-view";
import { StructuredData } from "@/components/structured-data";
import { SiteHeader } from "@/components/site-header";
import {
  fetchCatalogProducts,
  fetchCatalogCategories,
  getCurrentHost,
  resolveSitePath,
  SiteApiUnavailableError,
  type CatalogPayload,
  type CatalogCategory,
  type ResolvedPayload,
} from "@/lib/site-api";

type PageProps = {
  params: Promise<{ path?: string[] }>;
  searchParams?: Promise<Record<string, string | string[] | undefined>>;
};

export const dynamic = "force-dynamic";

export async function generateMetadata({ params, searchParams }: PageProps): Promise<Metadata> {
  const path = toPath((await params).path);
  const resolved = await resolveForCurrentHost(path);
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
  const resolved = await resolveForCurrentHost(path);

  if (resolved.kind === "redirect") {
    redirect(resolved.redirect.to);
  }

  if (resolved.kind === "not_found") {
    notFound();
  }

  if (resolved.kind === "unavailable") {
    throw new SiteApiUnavailableError("page resolver");
  }

  const { site } = resolved;
  const catalogOptions = await normalizedCatalogOptions(searchParams);
  const [categories, catalog] = await Promise.all([
    fetchCatalogCategories(site.key, site.defaultLocale),
    resolved.kind === "category" ? fetchCatalogProducts(site.key, {
      page: catalogOptions.page,
      perPage: 12,
      query: catalogOptions.query,
      category: resolved.category.slug,
    }) : Promise.resolve(null),
  ]);

  return (
    <div className="site-shell">
      <SiteHeader site={site} currentPath={path} categories={categories} currentLocale={resolved.seo.locale} localeAlternates={resolved.seo.hreflang} />
      <StructuredData value={resolved.seo.schema} />
      <main className="site-main">
        <Content resolved={resolved} catalog={catalog} categories={categories} query={catalogOptions.query} />
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
}: {
  resolved: Exclude<ResolvedPayload, { kind: "redirect" | "not_found" | "unavailable" }>;
  catalog: CatalogPayload | null;
  categories: CatalogCategory[];
  query: string;
}) {
  if (resolved.kind === "product") {
    return <ProductView payload={resolved} />;
  }

  if (resolved.kind === "category") {
    return <CatalogView category={resolved} catalog={catalog ?? emptyCatalog()} categories={categories} query={query} />;
  }

  return (
    <article className="content-page">
      <p className="catalog-eyebrow">{resolved.site.name}</p>
      <h1>{resolved.page.h1}</h1>
      {resolved.page.content && <p className="content-page__lead">{resolved.page.content}</p>}
    </article>
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

function toPath(segments?: string[]): string {
  return segments?.length ? `/${segments.join("/")}` : "/";
}

async function normalizedCatalogOptions(searchParams?: PageProps["searchParams"]) {
  const values = searchParams ? await searchParams : {};
  const rawPage = Array.isArray(values.page) ? values.page[0] : values.page;
  const rawQuery = Array.isArray(values.q) ? values.q[0] : values.q;
  const page = Number.parseInt(rawPage ?? "1", 10);

  return {
    page: Number.isFinite(page) && page > 0 ? page : 1,
    query: (rawQuery ?? "").trim().slice(0, 100),
  };
}

function emptyCatalog(): CatalogPayload {
  return { data: [], meta: { current_page: 1, last_page: 1, total: 0 }, available: false };
}
