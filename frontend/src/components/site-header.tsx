import { CategoryTree } from "@/components/category-tree";
import { CatalogMegaMenu } from "@/components/catalog-mega-menu";
import type { CatalogCategory, SiteProfile } from "@/lib/site-api";
import Link from "next/link";

export function SiteHeader({
  site,
  currentPath,
  categories = [],
  currentLocale,
  localeAlternates = {},
}: {
  site: SiteProfile;
  currentPath: string;
  categories?: CatalogCategory[];
  currentLocale?: string;
  localeAlternates?: Record<string, string>;
}) {
  const localeLinks = Object.entries(localeAlternates).filter(([locale, href]) => locale !== currentLocale && isSafeAbsoluteUrl(href));
  const availablePages = new Set(site.availablePagePaths ?? []);
  const pagePath = (slug: string, legacyPath: string) => site.availablePages?.[slug] ?? (availablePages.has(legacyPath) ? legacyPath : null);
  const navigation = [
    { slug: "solutions", path: pagePath("solutions", "/solutions"), label: "Решения" },
    { slug: "delivery", path: pagePath("delivery", "/delivery"), label: "Доставка и оплата" },
    { slug: "warranty-and-documents", path: pagePath("warranty-and-documents", "/warranty-and-documents"), label: "Гарантия и документы" },
    { slug: "services", path: pagePath("services", "/services"), label: "Услуги" },
  ].filter((page): page is { slug: string; path: string; label: string } => page.path !== null);
  const companyPages = [
    { slug: "about", path: pagePath("about", "/about"), label: "О компании" },
    { slug: "contacts", path: pagePath("contacts", "/contacts"), label: "Контакты и реквизиты" },
  ].filter((page): page is { slug: string; path: string; label: string } => page.path !== null);
  const contactsPath = pagePath("contacts", "/contacts");
  return (
    <header className="site-header">
      {localeLinks.length > 0 && (
        <details className="site-header__locale-switcher">
          <summary>{currentLocale ?? site.defaultLocale}</summary>
          <div>
            {localeLinks.map(([locale, href]) => (
              <a key={locale} href={href} lang={locale.split("-")[0]}>{locale}</a>
            ))}
          </div>
        </details>
      )}
      <div className="site-header__bar">
        <p>Промышленные аккумуляторы и системы резервного питания</p>
        <p>{marketLabel(site.countryCode)} · {site.currencyCode}</p>
      </div>
      <div className="site-header__main">
        <Link className="site-brand" href="/" aria-label={`${site.name} — главная`}>
          <span className="site-brand__mark" aria-hidden="true">AR</span>
          <span>{site.name}</span>
        </Link>
        <a className="catalog-button site-header__cta" href="#quote-request">Запросить КП</a>
      </div>
      <nav className="desktop-nav" aria-label="Основная навигация">
        <details className="desktop-nav__catalog">
          <summary>Каталог</summary>
          <div className="desktop-nav__mega">
            <CatalogMegaMenu categories={categories} currentPath={currentPath} />
          </div>
        </details>
        {navigation.map(({ path, label }) => <Link key={path} href={path}>{label}</Link>)}
        {companyPages.length > 0 && (
          <details className="desktop-nav__company">
            <summary>О компании</summary>
            <div>{companyPages.map(({ path, label }) => <Link key={path} href={path}>{label}</Link>)}</div>
          </details>
        )}
        {contactsPath && <Link href={contactsPath}>Контакты</Link>}
      </nav>

      <details className="mobile-nav">
        <summary>Меню</summary>
        <div className="mobile-nav__panel">
          <details>
            <summary>Каталог</summary>
            <CategoryTree categories={categories} currentPath={currentPath} mobile />
          </details>
          {navigation.map(({ path, label }) => <Link key={path} href={path}>{label}</Link>)}
          {companyPages.length > 0 && (
            <details>
              <summary>О компании</summary>
              <div className="mobile-nav__nested">{companyPages.map(({ path, label }) => <Link key={path} href={path}>{label}</Link>)}</div>
            </details>
          )}
          {contactsPath && <Link href={contactsPath}>Контакты</Link>}
          <a className="catalog-button" href="#quote-request">Запросить КП</a>
        </div>
      </details>
    </header>
  );
}

function marketLabel(countryCode: string) {
  const labels: Record<string, string> = { BY: "Беларусь", RU: "Россия", UZ: "Узбекистан" };
  return labels[countryCode] ?? countryCode;
}
function isSafeAbsoluteUrl(href: string): boolean {
  try {
    const url = new URL(href);

    return url.protocol === "https:";
  } catch {
    return false;
  }
}
