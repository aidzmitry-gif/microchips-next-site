import { CategoryTree } from "@/components/category-tree";
import type { SiteProfile } from "@/lib/site-api";
import Link from "next/link";

export function SiteHeader({ site, currentPath }: { site: SiteProfile; currentPath: string }) {
  return (
    <header className="site-header">
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
            <CategoryTree currentPath={currentPath} />
          </div>
        </details>
        <Link href="/solutions">Решения</Link>
        <Link href="/delivery">Доставка и оплата</Link>
        <Link href="/warranty-and-documents">Гарантия и документы</Link>
        <Link href="/services">Услуги</Link>
        <details className="desktop-nav__company">
          <summary>О компании</summary>
          <div>
            <Link href="/about">О компании</Link>
            <Link href="/contacts">Контакты и реквизиты</Link>
          </div>
        </details>
        <Link href="/contacts">Контакты</Link>
      </nav>

      <details className="mobile-nav">
        <summary>Меню</summary>
        <div className="mobile-nav__panel">
          <details>
            <summary>Каталог</summary>
            <CategoryTree currentPath={currentPath} mobile />
          </details>
          <Link href="/solutions">Решения</Link>
          <Link href="/delivery">Доставка и оплата</Link>
          <Link href="/warranty-and-documents">Гарантия и документы</Link>
          <Link href="/services">Услуги</Link>
          <details>
            <summary>О компании</summary>
            <div className="mobile-nav__nested">
              <Link href="/about">О компании</Link>
              <Link href="/contacts">Контакты и реквизиты</Link>
            </div>
          </details>
          <Link href="/contacts">Контакты</Link>
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
