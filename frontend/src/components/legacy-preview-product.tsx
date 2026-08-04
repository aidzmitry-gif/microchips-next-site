import Link from "next/link";
import Image from "next/image";
import type { LegacyPreviewProduct } from "@/lib/legacy-preview-api";
import { LegacyPreviewHeader, statusLabels } from "@/components/legacy-preview-catalog";

export function LegacyPreviewProductView({ product }: { product: LegacyPreviewProduct }) {
  return (
    <main className="legacy-preview">
      <LegacyPreviewHeader />
      <nav className="catalog-breadcrumbs" aria-label="Хлебные крошки">
        <Link href="/legacy-preview/catalog">Предпросмотр каталога</Link><span>/</span><span>Bitrix #{product.legacy_id}</span>
      </nav>
      <article className="legacy-preview-product">
        <div className="legacy-preview-product__main">
          <p className="catalog-eyebrow">Исходная карточка Bitrix #{product.legacy_id}</p>
          <h1>{product.name}</h1>
          <p className="legacy-preview-product__warning">Исходный текст показан только для аудита. Характеристики, цена, наличие и коммерческие условия не считаются подтверждёнными.</p>
          <div className="legacy-preview-product__media">
            {product.has_staging_image
              ? <Image src={`/api/legacy-preview/media/${product.legacy_id}`} alt={`Архивное изображение: ${product.name}`} width={1000} height={1000} unoptimized />
              : <span>В архиве нет изображения для этой позиции</span>}
          </div>
          <section>
            <h2>Исходное описание</h2>
            <p className="legacy-preview-product__description">{product.description || "Описание отсутствует."}</p>
          </section>
        </div>
        <aside className="legacy-preview-product__aside">
          <span className="legacy-preview-product__status">{statusLabels[product.transfer_status] ?? product.transfer_status}</span>
          <dl>
            <div><dt>ID Bitrix</dt><dd>{product.legacy_id}</dd></div>
            <div><dt>Код 1С</dt><dd>{product.one_c.external_id ?? "не сопоставлен"}</dd></div>
            <div><dt>Артикул 1С</dt><dd>{product.one_c.article ?? "не подтверждён"}</dd></div>
            <div><dt>Основной раздел</dt><dd>{product.primary_section_path ?? "не определён"}</dd></div>
          </dl>
          {product.matched_section_paths.length > 0 && <div><h2>Привязки разделов</h2><ul>{product.matched_section_paths.map((path) => <li key={path}>{path}</li>)}</ul></div>}
          <p>{product.source_notice}</p>
        </aside>
      </article>
    </main>
  );
}
