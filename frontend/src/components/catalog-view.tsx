import type { CatalogCategory, CatalogPayload, CatalogProduct, CategoryPayload } from "@/lib/site-api";
import { CategoryTree } from "@/components/category-tree";
import { availabilityLabel, priceLabel } from "@/lib/catalog-presenters";
import { QuoteForm } from "@/components/quote-form";
import Link from "next/link";

type CatalogViewProps = {
  category: CategoryPayload;
  catalog: CatalogPayload;
  categories?: CatalogCategory[];
  query?: string;
};

export function CatalogView({ category, catalog, categories = [], query = "" }: CatalogViewProps) {
  const { site } = category;

  return (
    <>
      <nav className="catalog-breadcrumbs" aria-label="Хлебные крошки">
        <Link href="/">Главная</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{category.category.name}</span>
      </nav>

      <section className="catalog-hero">
        <div>
          <p className="catalog-eyebrow">Каталог для {marketName(site.countryCode)}</p>
          <h1>{category.category.name}</h1>
          <p className="catalog-hero__lead">
            Подбираем промышленные аккумуляторы и решения резервного питания под техническое задание.
            Коммерческие условия подтверждаем для каждого запроса отдельно.
          </p>
        </div>
        <div className="catalog-hero__facts" aria-label="Условия работы">
          <span>Подбор по параметрам</span>
          <span>Счёт и КП для организации</span>
          <span>Документы — после проверки</span>
        </div>
      </section>

      <section className="catalog-layout">
        <aside className="catalog-layout__tree">
          <CategoryTree categories={categories} currentPath={category.path} />
        </aside>
        <div className="catalog-section" aria-labelledby="catalog-results-title">
          <div className="catalog-toolbar">
          <div>
            <p className="catalog-eyebrow">Опубликованный ассортимент</p>
            <h2 id="catalog-results-title">{resultsTitle(catalog.meta.total, query)}</h2>
            <p>
              В каталоге показываются только позиции, прошедшие проверку для этого регионального сайта.
            </p>
          </div>
          <form className="catalog-search" role="search" method="get" action={category.path}>
            <label htmlFor="catalog-search">Поиск по каталогу</label>
            <div>
              <input
                id="catalog-search"
                name="q"
                type="search"
                defaultValue={query}
                placeholder="Название, SKU или MPN"
              />
              <button type="submit">Найти</button>
            </div>
          </form>
          </div>

          {!catalog.available ? (
            <CatalogUnavailable />
          ) : catalog.data.length === 0 ? (
            <CatalogEmpty hasQuery={Boolean(query)} />
          ) : (
            <>
              <div className="catalog-grid">
                {catalog.data.map((product) => (
                  <ProductCard key={product.slug} product={product} />
                ))}
              </div>
              <CatalogPagination
                currentPage={catalog.meta.current_page}
                lastPage={catalog.meta.last_page}
                path={category.path}
                query={query}
              />
            </>
          )}
        </div>
      </section>

      <section className="catalog-quote" id="quote-request" aria-labelledby="quote-title">
        <div>
          <p className="catalog-eyebrow">Инженерный запрос</p>
          <h2 id="quote-title">Не нашли нужную позицию?</h2>
          <p>
            Отправьте требования к напряжению, ёмкости, габаритам и режиму эксплуатации. Менеджер проверит
            номенклатуру и подготовит предложение без подмены неподтверждённых характеристик.
          </p>
        </div>
        <QuoteForm site={site} subject={`Раздел каталога: ${category.category.name}`} />
      </section>
    </>
  );
}

export function ProductCard({ product }: { product: CatalogProduct }) {
  const productPath = product.path || null;
  const identifiers = [
    product.sku ? ["SKU", product.sku] : null,
    product.mpn ? ["MPN", product.mpn] : null,
  ].filter((item): item is string[] => item !== null);

  return (
    <article className="catalog-card">
      {productPath ? (
        <a className="catalog-card__media" href={productPath} aria-label={`Открыть ${product.name}`}>
          <BatteryIcon />
          <span>Изображение не опубликовано</span>
        </a>
      ) : (
        <div className="catalog-card__media">
          <BatteryIcon />
          <span>Изображение не опубликовано</span>
        </div>
      )}
      <div className="catalog-card__body">
        <p className="catalog-card__scope">Позиция регионального каталога</p>
        <h3>
          {productPath ? <a href={productPath}>{product.name}</a> : product.name}
        </h3>
        {identifiers.length > 0 ? (
          <dl className="catalog-card__identifiers">
            {identifiers.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="catalog-card__verification">Идентификатор требует подтверждения</p>
        )}
      </div>
      <div className="catalog-card__commercial">
        <p className="catalog-card__availability">{availabilityLabel(product.availability)}</p>
        <p className="catalog-card__price">
          {priceLabel(product.price, product.currency)}
        </p>
        <a className="catalog-button" href={productPath ?? "#quote-request"}>
          {productPath ? "Открыть карточку" : "Запросить позицию"}
        </a>
      </div>
    </article>
  );
}

function CatalogEmpty({ hasQuery }: { hasQuery: boolean }) {
  return (
    <div className="catalog-empty">
      <BatteryIcon />
      <h3>{hasQuery ? "По вашему запросу ничего не найдено" : "Публикация позиций ещё не завершена"}</h3>
      <p>
        {hasQuery
          ? "Проверьте написание или отправьте техническое задание — мы сверим ассортимент вручную."
          : "Каталог пополняется только после проверки дублей и идентификаторов в 1С и исходном сайте."}
      </p>
      <a className="catalog-button" href="#quote-request">
        Запросить КП
      </a>
    </div>
  );
}

function CatalogUnavailable() {
  return (
    <div className="catalog-empty catalog-empty--warning">
      <h3>Каталог временно недоступен</h3>
      <p>Мы не подменяем данные демонстрационными товарами. Попробуйте обновить страницу позднее или отправьте запрос.</p>
      <a className="catalog-button" href="#quote-request">Запросить КП</a>
    </div>
  );
}

function CatalogPagination({
  currentPage,
  lastPage,
  path,
  query,
}: {
  currentPage: number;
  lastPage: number;
  path: string;
  query: string;
}) {
  if (lastPage <= 1) return null;

  const pages = paginationPages(currentPage, lastPage);

  return (
    <nav className="catalog-pagination" aria-label="Страницы каталога">
      {currentPage > 1 && <a href={pageHref(path, currentPage - 1, query)}>Назад</a>}
      {pages.map((page) => (
        <a
          key={page}
          href={pageHref(path, page, query)}
          aria-current={page === currentPage ? "page" : undefined}
        >
          {page}
        </a>
      ))}
      {currentPage < lastPage && <a href={pageHref(path, currentPage + 1, query)}>Далее</a>}
    </nav>
  );
}

function pageHref(path: string, page: number, query: string) {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (page > 1) params.set("page", String(page));
  const suffix = params.toString();

  return suffix ? `${path}?${suffix}` : path;
}

function paginationPages(currentPage: number, lastPage: number) {
  const start = Math.max(1, Math.min(currentPage - 2, lastPage - 4));
  const end = Math.min(lastPage, start + 4);
  return Array.from({ length: end - start + 1 }, (_, index) => start + index);
}

function resultsTitle(total: number, query: string) {
  if (query) return `Результаты поиска: ${total}`;
  if (total === 0) return "Каталог готовится к публикации";
  return `Товаров в каталоге: ${total}`;
}

function marketName(countryCode: string) {
  const names: Record<string, string> = { BY: "Беларуси", RU: "России", UZ: "Узбекистана" };
  return names[countryCode] ?? "вашего региона";
}

function BatteryIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <path d="M18 8h12v5h5a5 5 0 0 1 5 5v20a5 5 0 0 1-5 5H13a5 5 0 0 1-5-5V18a5 5 0 0 1 5-5h5V8Zm-5 10v20h22V18H13Zm9 4h4v5h5v4h-5v5h-4v-5h-5v-4h5v-5Z" fill="currentColor" />
    </svg>
  );
}
