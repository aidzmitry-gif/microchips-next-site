import type { CatalogCategory, CatalogFacetOption, CatalogFilters, CatalogPayload, CatalogProduct, CatalogSort, CategoryPayload } from "@/lib/site-api";
import { CatalogCategoryPanel } from "@/components/catalog-category-panel";
import { availabilityLabel, priceEvidenceLabel, priceLabel } from "@/lib/catalog-presenters";
import { QuoteForm } from "@/components/quote-form";
import { CommercialProfile } from "@/components/commercial-profile";
import Link from "next/link";

type CatalogViewProps = {
  category: CategoryPayload;
  catalog: CatalogPayload;
  categories?: CatalogCategory[];
  query?: string;
  sort?: CatalogSort;
  filters?: CatalogFilters;
};

export function CatalogView({ category, catalog, categories = [], query = "", sort, filters = {} }: CatalogViewProps) {
  const { site } = category;
  const facets = catalog.meta.facets;
  const hasControls = Boolean(query || sort || Object.keys(filters).length);

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
            {category.seo.description ??
              "Подбираем промышленное оборудование под техническое задание. Коммерческие условия подтверждаем для каждого запроса отдельно."}
          </p>
        </div>
        <div className="catalog-hero__facts" aria-label="Условия работы">
          <span>Подбор по параметрам</span>
          <span>Счёт и КП для организации</span>
          <span>Документы — после проверки</span>
        </div>
      </section>

      <section className="catalog-layout">
        <CatalogCategoryPanel categories={categories} currentPath={category.path} />
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
            <div className="catalog-search__query">
              <input
                id="catalog-search"
                name="q"
                type="search"
                defaultValue={query}
                placeholder="Название, SKU или MPN"
              />
              <button type="submit">Найти</button>
            </div>
            <label htmlFor="catalog-sort">Сортировка</label>
            <select id="catalog-sort" name="sort" defaultValue={sort ?? ""}>
              <option value="">{query ? "Сначала точные совпадения" : "По умолчанию"}</option>
              <option value="name_asc">Название: А—Я</option>
              <option value="name_desc">Название: Я—А</option>
              {catalog.meta.price_sort_enabled && <option value="price_asc">Цена: сначала ниже</option>}
              {catalog.meta.price_sort_enabled && <option value="price_desc">Цена: сначала выше</option>}
            </select>
            {facets && (
              <fieldset className="catalog-filters">
                <legend className="sr-only">Фильтры каталога</legend>
                <FacetSelect id="manufacturer" label="Производитель" options={facets.manufacturer} selected={filters.manufacturer} />
                <FacetSelect id="technology" label="Технология" options={facets.technology} selected={filters.technology} />
                <FacetSelect id="nominal_voltage" label="Напряжение" options={facets.nominal_voltage} selected={filters.nominal_voltage} />
                <FacetSelect id="capacity" label="Ёмкость" options={facets.capacity} selected={filters.capacity} />
                <FacetSelect id="power" label="Мощность" options={facets.power} selected={filters.power} />
                <FacetSelect id="input_voltage" label="Входное напряжение" options={facets.input_voltage} selected={filters.input_voltage} />
                <FacetSelect id="output_voltage" label="Выходное напряжение" options={facets.output_voltage} selected={filters.output_voltage} />
                <FacetSelect id="input_current" label="Входной ток" options={facets.input_current} selected={filters.input_current} />
                <FacetSelect id="output_current" label="Выходной ток" options={facets.output_current} selected={filters.output_current} />
                <FacetSelect id="phase" label="Фазность" options={facets.phase} selected={filters.phase} />
                <FacetSelect id="topology" label="Топология" options={facets.topology} selected={filters.topology} />
                <FacetSelect id="device_type" label="Тип устройства" options={facets.device_type} selected={filters.device_type} />
              </fieldset>
            )}
            <div className="catalog-filter-actions">
              <button type="submit">Применить</button>
              {hasControls && <a href={category.path}>Сбросить</a>}
            </div>
          </form>
          </div>

          {!catalog.available ? (
            <CatalogUnavailable />
          ) : catalog.data.length === 0 ? (
            <CatalogEmpty hasQuery={Boolean(query || Object.keys(filters).length)} />
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
                sort={sort}
                filters={filters}
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

      <CommercialProfile site={site} />
    </>
  );
}

export function ProductCard({ product }: { product: CatalogProduct }) {
  const productPath = product.path || null;
  const observedPriceLabel = priceEvidenceLabel(product.price, product.price_observed_at);
  const identifiers = [
    product.sku ? ["SKU", product.sku] : null,
    product.mpn ? ["MPN", product.mpn] : null,
  ].filter((item): item is string[] => item !== null);
  const summary = Object.entries(product.summary_attributes ?? {}).map(([key, value]) => [summaryLabel(key), value]);

  return (
    <article className="catalog-card">
      {productPath ? (
        <a className="catalog-card__media" href={productPath} aria-label={`Открыть ${product.name}`}>
          {product.image_path ? <img src={proxyMediaPath(product.image_path)} alt="" /> : <><BatteryIcon /><span>Изображение не опубликовано</span></>}
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
        {product.manufacturer && <p className="catalog-card__manufacturer">{product.manufacturer}</p>}
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
        {summary.length > 0 && (
          <dl className="catalog-card__summary">
            {summary.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}
          </dl>
        )}
      </div>
      <div className="catalog-card__commercial">
        <p className="catalog-card__availability">{availabilityLabel(product.availability)}</p>
        <p className="catalog-card__price">
          {priceLabel(product.price, product.currency)}
        </p>
        {observedPriceLabel && <p className="catalog-card__price-evidence">{observedPriceLabel}</p>}
        <a className="catalog-button" href={productPath ?? "#quote-request"}>
          {productPath ? "Открыть карточку" : "Запросить позицию"}
        </a>
      </div>
    </article>
  );
}

function FacetSelect({ id, label, options, selected }: { id: string; label: string; options?: CatalogFacetOption[]; selected?: string }) {
  if (!options?.length) return null;

  return (
    <label htmlFor={`catalog-filter-${id}`}>
      <span>{label}</span>
      <select id={`catalog-filter-${id}`} name={id} defaultValue={selected ?? ""}>
        <option value="">Все</option>
        {options.map((option) => <option key={option.value} value={option.value}>{option.label} ({option.count})</option>)}
      </select>
    </label>
  );
}

function summaryLabel(key: string) {
  return ({
    technology: "Технология",
    nominal_voltage: "Напряжение",
    capacity: "Ёмкость",
    power: "Мощность",
    input_voltage: "Входное напряжение",
    output_voltage: "Выходное напряжение",
    input_current: "Входной ток",
    output_current: "Выходной ток",
    phase: "Фазность",
    topology: "Топология",
    device_type: "Тип устройства",
  } as Record<string, string>)[key] ?? key;
}

function proxyMediaPath(path: string): string {
  const match = path.match(/^\/api\/v1\/media\/(\d+)$/);
  return match ? `/api/media/${match[1]}` : "";
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
  sort,
  filters,
}: {
  currentPage: number;
  lastPage: number;
  path: string;
  query: string;
  sort?: CatalogSort;
  filters: CatalogFilters;
}) {
  if (lastPage <= 1) return null;

  const pages = paginationPages(currentPage, lastPage);

  return (
    <nav className="catalog-pagination" aria-label="Страницы каталога">
      {currentPage > 1 && <a href={pageHref(path, currentPage - 1, query, sort, filters)}>Назад</a>}
      {pages.map((page) => (
        <a
          key={page}
          href={pageHref(path, page, query, sort, filters)}
          aria-current={page === currentPage ? "page" : undefined}
        >
          {page}
        </a>
      ))}
      {currentPage < lastPage && <a href={pageHref(path, currentPage + 1, query, sort, filters)}>Далее</a>}
    </nav>
  );
}

function pageHref(path: string, page: number, query: string, sort: CatalogSort | undefined, filters: CatalogFilters) {
  const params = new URLSearchParams();
  if (query) params.set("q", query);
  if (sort) params.set("sort", sort);
  for (const [filter, value] of Object.entries(filters)) {
    if (value) params.set(filter, value);
  }
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
