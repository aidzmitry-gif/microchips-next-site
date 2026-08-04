import Link from "next/link";
import Image from "next/image";
import type { LegacyPreviewCatalog, LegacyPreviewCategory, LegacyPreviewProduct } from "@/lib/legacy-preview-api";

export function LegacyPreviewCatalogView({
  catalog,
  categories,
  currentCategory,
  query,
  status,
  sort,
}: {
  catalog: LegacyPreviewCatalog;
  categories: LegacyPreviewCategory[];
  currentCategory?: string;
  query: string;
  status?: string;
  sort?: string;
}) {
  return (
    <main className="legacy-preview">
      <LegacyPreviewHeader />
      <section className="legacy-preview__summary" aria-labelledby="legacy-preview-title">
        <div>
          <p className="catalog-eyebrow">Снимок Bitrix · run #{catalog.meta.snapshot_run_id}</p>
          <h1 id="legacy-preview-title">Предпросмотр перенесённого каталога</h1>
          <p>Это рабочая копия для сверки структуры и карточек. Данные не опубликованы и не используются поисковыми системами.</p>
        </div>
        <dl>
          <div><dt>В снимке</dt><dd>{catalog.meta.snapshot_total}</dd></div>
          <div><dt>В текущем профиле</dt><dd>{catalog.meta.visible_scope_total}</dd></div>
          <div><dt>Исключено</dt><dd>{catalog.meta.excluded_total}</dd></div>
          <div><dt>В выдаче</dt><dd>{catalog.meta.total}</dd></div>
        </dl>
      </section>

      <section className="legacy-preview__layout">
        <aside className="legacy-preview__tree">
          <details open>
            <summary>Дерево старого каталога</summary>
            <LegacyCategoryTree categories={categories} currentCategory={currentCategory} />
          </details>
        </aside>

        <div className="legacy-preview__results">
          <form className="legacy-preview__filters" method="get">
            <label>
              <span>Поиск</span>
              <input name="q" type="search" defaultValue={query} placeholder="Название, ID Bitrix, код или артикул 1С" />
            </label>
            <label>
              <span>Статус переноса</span>
              <select name="status" defaultValue={status ?? ""}>
                <option value="">Все рабочие статусы</option>
                {Object.entries(statusLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label>
              <span>Сортировка</span>
              <select name="sort" defaultValue={sort ?? "legacy_id"}>
                <option value="legacy_id">По ID Bitrix</option>
                <option value="name_asc">Название А—Я</option>
                <option value="name_desc">Название Я—А</option>
              </select>
            </label>
            <button type="submit">Применить</button>
            {(query || status || sort) && <Link href={currentCategory ? `/legacy-preview/catalog/${currentCategory}` : "/legacy-preview/catalog"}>Сбросить</Link>}
          </form>

          {catalog.data.length === 0 ? (
            <div className="catalog-empty"><h2>Ничего не найдено</h2><p>Измените запрос или вернитесь к корню дерева.</p></div>
          ) : (
            <div className="legacy-preview__grid">
              {catalog.data.map((product) => <LegacyProductCard key={product.legacy_id} product={product} />)}
            </div>
          )}

          <LegacyPagination catalog={catalog} currentCategory={currentCategory} query={query} status={status} sort={sort} />
        </div>
      </section>
    </main>
  );
}

export function LegacyPreviewHeader() {
  return (
    <header className="legacy-preview__header">
      <Link href="/legacy-preview/catalog" className="legacy-preview__brand">Microchips · рабочая копия</Link>
      <span>NOINDEX · только локальная среда</span>
    </header>
  );
}

function LegacyProductCard({ product }: { product: LegacyPreviewProduct }) {
  return (
    <article className="legacy-preview-card">
      <Link className="legacy-preview-card__media" href={product.preview_path} aria-label={`Открыть ${product.name}`}>
        {product.has_staging_image
          ? <Image src={`/api/legacy-preview/media/${product.legacy_id}`} alt="" width={800} height={800} unoptimized />
          : <span>Изображение отсутствует в архиве</span>}
      </Link>
      <div className="legacy-preview-card__body">
        <div className="legacy-preview-card__badges">
          <span>Bitrix #{product.legacy_id}</span>
          <span data-status={product.transfer_status}>{statusLabels[product.transfer_status] ?? product.transfer_status}</span>
        </div>
        <h2><Link href={product.preview_path}>{product.name}</Link></h2>
        <p className="legacy-preview-card__section">{product.primary_section_path || "Раздел не определён"}</p>
        {product.description && <p className="legacy-preview-card__description">{product.description}</p>}
        <dl>
          <div><dt>Код 1С</dt><dd>{product.one_c.external_id ?? "не сопоставлен"}</dd></div>
          <div><dt>Артикул 1С</dt><dd>{product.one_c.article ?? "не подтверждён"}</dd></div>
        </dl>
      </div>
      <Link className="catalog-button catalog-button--light" href={product.preview_path}>Проверить карточку</Link>
    </article>
  );
}

function LegacyCategoryTree({ categories, currentCategory }: { categories: LegacyPreviewCategory[]; currentCategory?: string }) {
  return (
    <nav className="legacy-preview-tree" aria-label="Разделы старого каталога">
      <Link href="/legacy-preview/catalog" aria-current={!currentCategory ? "page" : undefined}>Все позиции</Link>
      <ul>{categories.map((category) => <LegacyCategoryBranch key={`${category.external_id}-${category.source_path}`} category={category} currentCategory={currentCategory} />)}</ul>
    </nav>
  );
}

function LegacyCategoryBranch({ category, currentCategory }: { category: LegacyPreviewCategory; currentCategory?: string }) {
  const active = currentCategory === category.source_path;
  if (category.children.length === 0) {
    return <li><Link href={category.path} aria-current={active ? "page" : undefined}>{category.name}<span>{category.count}</span></Link></li>;
  }

  const open = active || Boolean(currentCategory?.startsWith(`${category.source_path}/`));
  return (
    <li>
      <details open={open}>
        <summary><span>{category.name}</span><span>{category.count}</span></summary>
        <Link href={category.path} aria-current={active ? "page" : undefined}>Все в разделе</Link>
        <ul>{category.children.map((child) => <LegacyCategoryBranch key={`${child.external_id}-${child.source_path}`} category={child} currentCategory={currentCategory} />)}</ul>
      </details>
    </li>
  );
}

function LegacyPagination({ catalog, currentCategory, query, status, sort }: {
  catalog: LegacyPreviewCatalog;
  currentCategory?: string;
  query: string;
  status?: string;
  sort?: string;
}) {
  if (catalog.meta.last_page <= 1) return null;
  const start = Math.max(1, Math.min(catalog.meta.current_page - 2, catalog.meta.last_page - 4));
  const end = Math.min(catalog.meta.last_page, start + 4);
  const pages = Array.from({ length: end - start + 1 }, (_, index) => start + index);
  const base = currentCategory ? `/legacy-preview/catalog/${currentCategory}` : "/legacy-preview/catalog";
  const href = (page: number) => {
    const params = new URLSearchParams();
    if (query) params.set("q", query);
    if (status) params.set("status", status);
    if (sort) params.set("sort", sort);
    if (page > 1) params.set("page", String(page));
    return params.size ? `${base}?${params}` : base;
  };

  return (
    <nav className="catalog-pagination" aria-label="Страницы предпросмотра">
      {catalog.meta.current_page > 1 && <Link href={href(catalog.meta.current_page - 1)}>Назад</Link>}
      {pages.map((page) => <Link key={page} href={href(page)} aria-current={page === catalog.meta.current_page ? "page" : undefined}>{page}</Link>)}
      {catalog.meta.current_page < catalog.meta.last_page && <Link href={href(catalog.meta.current_page + 1)}>Далее</Link>}
    </nav>
  );
}

export const statusLabels: Record<string, string> = {
  strict_mapped_evidence: "строго сопоставлен с 1С",
  candidate_mapped_evidence: "кандидат связи с 1С",
  candidate_duplicate_group: "кандидат в группу дублей",
  hold_missing_1c_identity: "нет идентичности 1С",
  hold_missing_rb_site_product: "нет карточки РБ",
};
