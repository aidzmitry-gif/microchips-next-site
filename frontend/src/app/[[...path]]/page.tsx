import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { CatalogView } from "@/components/catalog-view";
import { SiteHeader } from "@/components/site-header";
import {
  fetchCatalogProducts,
  getCurrentHost,
  resolveSitePath,
  type CatalogPayload,
  type ResolvedPayload,
} from "@/lib/site-api";

type PageProps = {
  params: Promise<{ path?: string[] }>;
  searchParams?: Promise<{ page?: string | string[]; q?: string | string[] }>;
};

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const path = toPath((await params).path);
  const resolved = await resolveForCurrentHost(path);

  if (!("seo" in resolved)) {
    return { title: "Microchips" };
  }

  return {
    title: resolved.seo.title,
    description: resolved.seo.description ?? undefined,
    robots: resolved.seo.isIndexable ? { index: true, follow: true } : { index: false, follow: false },
    alternates: {
      canonical: new URL(resolved.seo.canonicalPath, `https://${resolved.site.domain}`).toString(),
      languages: resolved.seo.hreflang,
    },
  };
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
    return <Unavailable />;
  }

  const { site } = resolved;
  const catalogOptions = await normalizedCatalogOptions(searchParams);
  const catalog = resolved.kind === "category"
    ? await fetchCatalogProducts(site.key, { page: catalogOptions.page, perPage: 12, query: catalogOptions.query })
    : null;

  return (
    <div className="site-shell">
      <SiteHeader site={site} currentPath={path} />
      <main className="site-main">
        <Content resolved={resolved} catalog={catalog} query={catalogOptions.query} />
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
  query,
}: {
  resolved: Exclude<ResolvedPayload, { kind: "redirect" | "not_found" | "unavailable" }>;
  catalog: CatalogPayload | null;
  query: string;
}) {
  if (resolved.kind === "product") {
    return (
      <article className="product-page">
        <nav className="catalog-breadcrumbs" aria-label="Хлебные крошки">
          <Link href="/">Главная</Link><span aria-hidden="true">/</span><Link href="/catalog">Каталог</Link>
          <span aria-hidden="true">/</span><span aria-current="page">{resolved.product.name}</span>
        </nav>
        <div className="product-page__layout">
          <div>
            <p className="catalog-eyebrow">Карточка товара</p>
            <h1>{resolved.product.name}</h1>
            {resolved.product.description && <p className="product-page__lead">{resolved.product.description}</p>}
            {resolved.product.attributes && (
              <dl className="product-specs">
                {Object.entries(resolved.product.attributes).map(([name, value]) => (
                  <div key={name}>
                    <dt>{name}</dt><dd>{value}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
          <aside className="product-page__aside">
            <p className="catalog-card__availability">
              {resolved.product.availability === "on_request" ? "Поставка по запросу" : "Условия поставки подтверждаются"}
            </p>
            <p className="product-page__price">
              {resolved.product.price ? `${resolved.product.price} ${resolved.product.currency}` : "Цена по запросу"}
            </p>
            <a className="catalog-button" href="#quote-request">Запросить КП</a>
          </aside>
        </div>
      </article>
    );
  }

  if (resolved.kind === "category") {
    return <CatalogView category={resolved} catalog={catalog ?? emptyCatalog()} query={query} />;
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
