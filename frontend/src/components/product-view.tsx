import Link from "next/link";
import { availabilityLabel, priceLabel } from "@/lib/catalog-presenters";
import { QuoteForm } from "@/components/quote-form";
import type { ProductPayload } from "@/lib/site-api";

export function ProductView({ payload }: { payload: ProductPayload }) {
  const { product } = payload;
  const attributes = Object.entries(product.attributes ?? {}).filter(
    (entry): entry is [string, string] => typeof entry[0] === "string" && typeof entry[1] === "string" && Boolean(entry[0].trim()) && Boolean(entry[1].trim()),
  );

  return (
    <article className="product-page">
      <nav className="catalog-breadcrumbs" aria-label="Хлебные крошки">
        <Link href="/">Главная</Link>
        <span aria-hidden="true">/</span>
        <Link href="/catalog">Каталог</Link>
        <span aria-hidden="true">/</span>
        <span aria-current="page">{product.name}</span>
      </nav>

      <div className="product-page__layout">
        <div className="product-page__content">
          <p className="catalog-eyebrow">Карточка товара</p>
          <h1>{product.name}</h1>

          <div className="product-page__media" role="img" aria-label="Изображение товара не опубликовано">
            <ProductPlaceholderIcon />
            <span>Изображение пока не опубликовано</span>
          </div>

          {product.description ? (
            <p className="product-page__lead">{product.description}</p>
          ) : (
            <p className="product-page__notice">Описание пока не опубликовано. Уточните параметры у менеджера.</p>
          )}

          <section className="product-details" aria-labelledby="product-identifiers-title">
            <h2 id="product-identifiers-title">Идентификация</h2>
            <dl className="product-specs">
              <ProductFact label="Производитель" value={product.manufacturer} />
              <ProductFact label="SKU" value={product.sku} />
              <ProductFact label="MPN" value={product.mpn} />
            </dl>
          </section>

          <section className="product-details" aria-labelledby="product-specs-title">
            <h2 id="product-specs-title">Характеристики</h2>
            {attributes.length ? (
              <dl className="product-specs">
                {attributes.map(([name, value]) => (
                  <ProductFact key={name} label={name} value={value} />
                ))}
              </dl>
            ) : (
              <p className="product-page__notice">Характеристики пока не опубликованы.</p>
            )}
          </section>
        </div>

        <aside className="product-page__aside" aria-label="Коммерческие условия">
          <p className="catalog-card__availability">{availabilityLabel(product.availability)}</p>
          <p className="product-page__price">{priceLabel(product.price, product.currency)}</p>
          <p className="product-page__commercial-note">
            Итоговые условия, срок поставки и комплект документов подтверждаются в коммерческом предложении.
          </p>
          <a className="catalog-button" href="#quote-request">Запросить КП</a>
        </aside>
      </div>

      <section className="catalog-quote product-page__quote" id="quote-request" aria-labelledby="product-quote-title">
        <div>
          <p className="catalog-eyebrow">Запрос по товару</p>
          <h2 id="product-quote-title">Уточнить цену и условия поставки</h2>
          <p>
            Укажите название товара и необходимые параметры. Менеджер сверит опубликованные данные и подготовит ответ.
          </p>
        </div>
        <QuoteForm site={payload.site} subject={`Товар: ${product.name}`} />
      </section>
    </article>
  );
}

function ProductFact({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd className={value ? undefined : "product-specs__missing"}>
        {value || "Не указано в опубликованных данных"}
      </dd>
    </div>
  );
}

function ProductPlaceholderIcon() {
  return (
    <svg viewBox="0 0 48 48" aria-hidden="true">
      <path d="M18 8h12v5h5a5 5 0 0 1 5 5v20a5 5 0 0 1-5 5H13a5 5 0 0 1-5-5V18a5 5 0 0 1 5-5h5V8Zm-5 10v20h22V18H13Zm9 4h4v5h5v4h-5v5h-4v-5h-5v-4h5v-5Z" fill="currentColor" />
    </svg>
  );
}
