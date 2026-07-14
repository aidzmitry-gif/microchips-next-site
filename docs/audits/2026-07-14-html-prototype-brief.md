# HTML prototype brief: Belarus B2B vertical

## Purpose

Create a static visual acceptance artifact before implementing public Next.js components. The prototype is not a copied Aspro theme and not an indexable website.

## First scope

`/catalog/akkumulyatory/promyshlennye/` plus one industrial battery product page and a quote-request state.

The scope proves the important B2B flow: visitor understands compatibility and conditions, selects or requests a product, and sends a traceable quote lead. It deliberately excludes checkout, personal account and unverified stock/payment claims.

## Required desktop blocks

1. Header: logo, visible country/language switcher, confirmed phone placeholder, search and quote CTA.
2. Breadcrumbs, category H1, short expert introduction and local delivery/payment summary.
3. Filter panel based only on confirmed source attributes: capacity, technology, use case, form factor and brand. Filter URLs are not indexable by default.
4. Product grid with technical comparison facts, availability state and `Запросить КП`; no invented price or stock.
5. Product page: technical specification, compatible use case, documents/media placeholders, FAQ and B2B quote form.
6. Trust/legal block: real Belarus company data placeholders, delivery, payment, warranty/service and contacts.
7. SEO content/FAQ block that is visibly separate from commercial content and can be approved by an editor.

## Required states

- price and availability on request;
- empty filter result;
- product without a confirmed image/document;
- form validation and successful submission;
- mobile header and filter drawer.

## Acceptance criteria

- Russian UI text; English code names.
- No references to non-existent city offices, stock, prices, certificates or legal entities.
- The prototype shows an obvious country/language switcher but does not auto-redirect by IP.
- The visual is data-dense, desktop-first, B2B and calm; it must not replicate the legacy Aspro theme.
- Product card and request form map directly to the existing `site_products` and `POST /api/v1/leads/quote` contracts.
