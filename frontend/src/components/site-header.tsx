import { CategoryTree } from "@/components/category-tree";
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
  const navigation = [
    { path: "/solutions", label: "Решения" },
    { path: "/delivery", label: "Доставка и оплата" },
    { path: "/warranty-and-documents", label: "Гарантия и документы" },
    { path: "/services", label: "Услуги" },
  ].filter(({ path }) => availablePages.has(path));
  const companyPages = [
    { path: "/about", label: "О компании" },
    { path: "/contacts", label: "Контакты и реквизиты" },
  ].filter(({ path }) => availablePages.has(path));
  const hasContacts = availablePages.has("/contacts");
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
            <CategoryTree categories={categories} currentPath={currentPath} />
          </div>
        </details>
        {navigation.map(({ path, label }) => <Link key={path} href={path}>{label}</Link>)}
        {companyPages.length > 0 && (
          <details className="desktop-nav__company">
            <summary>О компании</summary>
            <div>{companyPages.map(({ path, label }) => <Link key={path} href={path}>{label}</Link>)}</div>
          </details>
        )}
        {hasContacts && <Link href="/contacts">Контакты</Link>}
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
          {hasContacts && <Link href="/contacts">Контакты</Link>}
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
