"use client";

import Link from "next/link";
import { useState } from "react";
import { availabilityLabel, priceEvidenceLabel, priceLabel } from "@/lib/catalog-presenters";
import { QuoteForm } from "@/components/quote-form";
import { CommercialProfile } from "@/components/commercial-profile";
import type { ProductPayload, QuoteCartLine } from "@/lib/site-api";

export function ProductView({ payload }: { payload: ProductPayload }) {
  const { product } = payload;
  const [selectedVariantKey, setSelectedVariantKey] = useState("");
  const selectedVariant = product.variant_group?.options.find((option) => option.variant_key === selectedVariantKey) ?? null;
  const commercialProduct = selectedVariant ?? product;
  const observedPriceLabel = priceEvidenceLabel(commercialProduct.price, commercialProduct.price_observed_at);
  const selectedImagePath = selectedVariant?.image_path ?? product.image_path;
  const quoteCart: QuoteCartLine[] = [{
    external_id: selectedVariant?.external_id ?? product.external_id ?? null,
    variant_key: selectedVariant?.variant_key ?? null,
    name: selectedVariant ? `${product.name} — ${selectedVariant.label}` : product.name,
    sku: selectedVariant?.sku ?? product.sku,
    quantity: 1,
    attributes: selectedVariant?.attributes ?? product.variant_group?.canonical_attributes ?? {},
  }];
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

          <div className="product-page__media" role={selectedImagePath ? undefined : "img"} aria-label={selectedImagePath ? undefined : "Изображение товара не опубликовано"}>
            {selectedImagePath ? <img src={proxyMediaPath(selectedImagePath)} alt={selectedVariant ? `${product.name} — ${selectedVariant.label}` : product.name} /> : <><ProductPlaceholderIcon /><span>Изображение пока не опубликовано</span></>}
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
          {product.variant_group ? (
            <fieldset className="product-variant-selector">
              <legend>{product.variant_group.label}</legend>
              <label>
                <input
                  type="radio"
                  name="product-variant"
                  value=""
                  checked={selectedVariantKey === ""}
                  onChange={() => setSelectedVariantKey("")}
                />
                <span>{product.variant_group.canonical_label}</span>
              </label>
              {product.variant_group.options.map((option) => (
                <label key={option.variant_key}>
                  <input
                    type="radio"
                    name="product-variant"
                    value={option.variant_key}
                    checked={selectedVariantKey === option.variant_key}
                    onChange={() => setSelectedVariantKey(option.variant_key)}
                  />
                  <span>{option.label}</span>
                </label>
              ))}
            </fieldset>
          ) : null}
          {selectedVariant ? (
            <VariantFacts label={selectedVariant.label} attributes={selectedVariant.attributes} />
          ) : product.variant_group ? (
            <VariantFacts label={product.variant_group.canonical_label} attributes={product.variant_group.canonical_attributes} />
          ) : null}
          <p className="catalog-card__availability">{availabilityLabel(commercialProduct.availability)}</p>
          <p className="product-page__price">{priceLabel(commercialProduct.price, commercialProduct.currency)}</p>
          {observedPriceLabel && <p className="product-page__price-evidence">{observedPriceLabel}</p>}
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
        <QuoteForm
          site={payload.site}
          subject={selectedVariant ? `Товар: ${product.name}\nВариант: ${selectedVariant.label}` : `Товар: ${product.name}`}
          cart={quoteCart}
        />
      </section>

      <CommercialProfile site={payload.site} />
    </article>
  );
}

function VariantFacts({ label, attributes }: { label: string; attributes: Record<string, string> }) {
  const facts = Object.entries(attributes).filter(([, value]) => Boolean(value.trim()));
  if (facts.length === 0) return null;

  return (
    <dl className="product-variant-facts" aria-label={`Параметры варианта ${label}`}>
      {facts.map(([label, value]) => (
        <div key={label}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function proxyMediaPath(path: string): string {
  const match = path.match(/^\/api\/v1\/media\/(\d+)$/);
  return match ? `/api/media/${match[1]}` : "";
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
