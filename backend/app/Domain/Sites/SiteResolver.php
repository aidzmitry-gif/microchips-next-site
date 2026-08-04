<?php

namespace App\Domain\Sites;

use App\Models\ProductFamily;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteContact;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\SiteUrlAlternate;

class SiteResolver
{
    public function resolve(string $host): ?Site
    {
        $domain = $this->normalizeHost($host);

        return Site::query()
            ->with(['locales' => fn ($query) => $query->where('is_enabled', true)])
            ->where('domain', $domain)
            ->where('is_active', true)
            ->first();
    }

    /** @return array<string, mixed> */
    public function resolvePath(Site $site, string $path): array
    {
        $path = $this->normalizePath($path);
        $redirect = $site->redirects()
            ->where('source_path', $path)
            ->where('is_active', true)
            ->first();

        if ($redirect !== null && $this->isSafeLocalPath($redirect->target_path)) {
            return [
                'kind' => 'redirect',
                'site' => $this->sitePayload($site),
                'redirect' => [
                    'to' => $redirect->target_path,
                    'status' => $redirect->status_code,
                ],
            ];
        }

        $url = SiteUrl::query()
            ->where('site_id', $site->id)
            ->where('path', $path)
            ->first();

        if ($url === null) {
            return ['kind' => 'not_found', 'site' => $this->sitePayload($site)];
        }

        return match ($url->target_type) {
            'page' => $this->pagePayload($site, $url),
            'product' => $this->productPayload($site, $url),
            'category' => $this->categoryPayload($site, $url),
            default => ['kind' => 'not_found', 'site' => $this->sitePayload($site)],
        };
    }

    public function normalizeHost(string $host): string
    {
        $host = strtolower(trim($host));
        $host = preg_replace('#^https?://#', '', $host) ?? $host;
        $host = explode('/', $host)[0];
        $host = explode(':', $host)[0];

        return str_starts_with($host, 'www.') ? substr($host, 4) : $host;
    }

    public function normalizePath(string $path): string
    {
        $path = '/'.ltrim(parse_url($path, PHP_URL_PATH) ?: '/', '/');
        $path = preg_replace('#/+#', '/', $path) ?? '/';

        return $path === '/' ? $path : rtrim($path, '/');
    }

    public function isSafeLocalPath(string $path): bool
    {
        if ($path === '' || ! str_starts_with($path, '/') || str_starts_with($path, '//') || str_contains($path, '\\')) {
            return false;
        }

        // Next and browsers can decode an encoded separator after this API
        // response leaves Laravel. Treat an encoded protocol-relative URL or
        // backslash path exactly like its literal form.
        $decoded = rawurldecode($path);
        if (! str_starts_with($decoded, '/') || str_starts_with($decoded, '//') || str_contains($decoded, '\\')
            || preg_match('/[\x00-\x1F\x7F]/', $decoded) === 1) {
            return false;
        }

        $parts = parse_url($path);
        if ($parts === false) {
            return false;
        }

        foreach (['scheme', 'host', 'port', 'user', 'pass', 'query', 'fragment'] as $forbidden) {
            if (array_key_exists($forbidden, $parts)) {
                return false;
            }
        }

        return $this->normalizePath($path) === $path;
    }

    /** @return array<string, mixed> */
    private function pagePayload(Site $site, SiteUrl $url): array
    {
        $page = SitePage::published()
            ->where('site_id', $site->id)
            ->find($url->target_id);

        if ($page === null) {
            return ['kind' => 'not_found', 'site' => $this->sitePayload($site)];
        }
        if ($page->locale !== ($url->locale ?? $site->default_locale)) {
            return ['kind' => 'not_found', 'site' => $this->sitePayload($site)];
        }

        return [
            'kind' => 'page',
            'site' => $this->sitePayload($site, $page->locale, true),
            'path' => $url->path,
            'page' => [
                'title' => $page->title,
                'h1' => $page->h1,
                'content' => $page->content,
                'locale' => $page->locale,
            ],
            'seo' => $this->seoPayload($site, $page->locale, 'page', $page->id, $url, $page->title),
        ];
    }

    /** @return array<string, mixed> */
    private function productPayload(Site $site, SiteUrl $url): array
    {
        $siteProduct = SiteProduct::query()
            ->with([
                'product.media' => fn ($query) => $query->previewReady()->orderBy('sort_order')->orderBy('id'),
                'currentPriceEvidence',
            ])
            ->published()
            ->where('site_id', $site->id)
            ->find($url->target_id);

        if ($siteProduct === null || $siteProduct->product === null) {
            return ['kind' => 'not_found', 'site' => $this->sitePayload($site)];
        }

        $variantGroup = $this->variantGroupPayload($site, $siteProduct);
        $hasCurrentPriceEvidence = $siteProduct->price !== null
            && SiteProductPriceEvidence::query()
                ->where('site_id', $site->id)
                ->where('site_product_id', $siteProduct->id)
                ->where('is_current', true)
                ->where('calculated_price', $siteProduct->price)
                ->where('currency', $site->currency_code)
                ->exists();

        return [
            'kind' => 'product',
            'site' => $this->sitePayload($site, $url->locale ?? $site->default_locale, true),
            'path' => $url->path,
            'product' => [
                'external_id' => $siteProduct->product->external_id,
                'name' => $siteProduct->product->name,
                'sku' => $siteProduct->product->sku,
                'mpn' => $siteProduct->product->mpn,
                'manufacturer' => $siteProduct->product->manufacturer,
                'description' => $siteProduct->product->short_description,
                'attributes' => $this->publicAttributes($siteProduct->product->technical_attributes),
                'availability' => $siteProduct->availability,
                'price' => $siteProduct->price,
                'price_observed_at' => $this->priceObservedAt($siteProduct, $site->currency_code),
                'currency' => $site->currency_code,
                'image_path' => $siteProduct->product->media->first()?->id === null ? null : '/api/v1/media/'.$siteProduct->product->media->first()->id,
                'variant_group' => $variantGroup,
            ],
            'seo' => $this->seoPayload(
                $site,
                $url->locale ?? $site->default_locale,
                'product',
                $siteProduct->id,
                $url,
                $siteProduct->product->name,
                $hasCurrentPriceEvidence && $siteProduct->availability === 'in_stock',
                $siteProduct->price,
                $site->currency_code,
            ),
        ];
    }

    /** @return array<string, mixed>|null */
    private function variantGroupPayload(Site $site, SiteProduct $canonicalSiteProduct): ?array
    {
        $family = ProductFamily::query()
            ->where('site_id', $site->id)
            ->where('canonical_product_id', $canonicalSiteProduct->product_id)
            ->where('status', ProductFamily::STATUS_VERIFIED)
            ->with([
                'variants' => fn ($query) => $query->active()->orderBy('id'),
                'variants.product.media' => fn ($query) => $query->previewReady()->orderBy('sort_order')->orderBy('id'),
                'variants.product.sites' => fn ($query) => $query
                    ->where('site_id', $site->id)
                    ->published()
                    ->with('currentPriceEvidence'),
            ])
            ->first();
        if ($family === null) {
            return null;
        }

        $options = $family->variants
            ->map(function ($variant) use ($site): ?array {
                $siteProduct = $variant->product?->sites->first();
                if ($siteProduct === null) {
                    return null;
                }
                // A family option is deliberately URL-less. If later data
                // drift gives it a standalone URL, fail closed in the public
                // payload instead of recreating a duplicate page.
                if (SiteUrl::query()
                    ->where('site_id', $site->id)
                    ->where('target_type', 'product')
                    ->where('target_id', $siteProduct->id)
                    ->exists()) {
                    return null;
                }

                return [
                    'external_id' => $variant->product->external_id,
                    'variant_key' => $variant->variant_key,
                    'label' => $variant->label,
                    'sku' => $variant->product->sku,
                    'attributes' => $this->publicAttributes($variant->attributes) ?? [],
                    'availability' => $siteProduct->availability,
                    'price' => $siteProduct->price,
                    'price_observed_at' => $this->priceObservedAt($siteProduct, $site->currency_code),
                    'currency' => $site->currency_code,
                    'image_path' => $variant->product->media->first()?->id === null
                        ? null
                        : '/api/v1/media/'.$variant->product->media->first()->id,
                ];
            })
            ->filter()
            ->values()
            ->all();

        if ($options === []) {
            return null;
        }

        return [
            'family_key' => $family->family_key,
            'label' => $family->selector_label,
            'canonical_label' => $family->canonical_label,
            'canonical_attributes' => $this->publicAttributes($family->canonical_attributes) ?? [],
            'options' => $options,
        ];
    }

    private function priceObservedAt(SiteProduct $siteProduct, string $currency): ?string
    {
        $evidence = $siteProduct->currentPriceEvidence;

        if ($siteProduct->price === null
            || $evidence === null
            || (string) $evidence->calculated_price !== (string) $siteProduct->price
            || $evidence->currency !== $currency) {
            return null;
        }

        return $evidence->observed_at?->toIso8601String();
    }

    /**
     * The frontend's declared contract for `product.attributes` is
     * `Record<string, string> | null` (frontend/src/lib/site-api.ts). Product::
     * $technical_attributes is an internal JSON blob that may also carry
     * sibling `*_provenance` audit keys (see SiteProductCategoryAssigner) --
     * nested objects recording WHERE a value like 'chemistry' came from, not
     * a display fact. Those must never leave this boundary: they are
     * internal audit metadata, not a storefront attribute, and shipping them
     * as-is both breaks the declared string-only contract and leaks internal
     * source labels to any API caller.
     *
     * Only `*_provenance` keys are dropped. Every other key is kept and
     * stringified -- a non-scalar value (a nested spec object, say) must
     * never silently vanish just because it isn't already a string: round-2
     * regression had `is_scalar($value)` filtering the VALUE, which quietly
     * dropped whole attributes with no trace in the payload, and turned a
     * `false` value into an indistinguishable empty string.
     *
     * A `null` value is dropped the same way a `*_provenance` key is: the key
     * is absent from the returned map entirely, not stringified to `''`.
     * Collapsing "no value" and "confirmed empty string" into the same `''`
     * is exactly the defect this docblock warns against for `false` above --
     * a reader of the payload could not tell "this attribute was never set"
     * from "this attribute is confirmed blank". Omitting the key keeps that
     * distinction visible (`array_key_exists` on the result answers it), and
     * matches how the frontend already treats a missing/blank attribute the
     * same way when rendering (frontend/src/components/product-view.tsx).
     *
     * @return array<string, string>|null
     */
    private function publicAttributes(?array $attributes): ?array
    {
        if ($attributes === null) {
            return null;
        }

        $public = [];
        foreach ($attributes as $key => $value) {
            if (is_string($key) && str_ends_with($key, '_provenance')) {
                continue;
            }

            if ($value === null) {
                continue;
            }

            $public[$key] = $this->stringifyAttributeValue($value);
        }

        // `chemistry` can be an earlier category-assignment fact (AGM/GEL),
        // while a source-backed editor has supplied the reader-facing
        // `Технология` attribute. Rendering both produces an English internal
        // key and a duplicate fact on the product page. Preserve chemistry
        // for products that have no richer source-backed label, but prefer
        // the explicit public attribute whenever it exists.
        if (array_key_exists('Технология', $public)) {
            unset($public['chemistry']);
        }

        return $public;
    }

    /**
     * Only ever called with a non-null $value (publicAttributes() drops null
     * before calling in). The default branch's json_encode() uses
     * JSON_THROW_ON_ERROR deliberately: a value this method cannot encode
     * must surface as a loud failure, not as a silently misleading `''` that
     * a storefront reader would read as "confirmed blank".
     */
    private function stringifyAttributeValue(mixed $value): string
    {
        return match (true) {
            is_string($value) => $value,
            is_bool($value) => $value ? 'true' : 'false',
            is_scalar($value) => (string) $value,
            default => json_encode($value, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR),
        };
    }

    /** @return array<string, mixed> */
    private function categoryPayload(Site $site, SiteUrl $url): array
    {
        $category = SiteCategory::query()
            ->with('category')
            ->where('site_id', $site->id)
            ->published()
            ->find($url->target_id);

        if ($category === null || $category->category === null) {
            return ['kind' => 'not_found', 'site' => $this->sitePayload($site)];
        }

        return [
            'kind' => 'category',
            'site' => $this->sitePayload($site, $url->locale ?? $site->default_locale, true),
            'path' => $url->path,
            'category' => [
                'name' => $category->name ?? $category->category->name,
                'slug' => $category->slug,
            ],
            'seo' => $this->seoPayload($site, $url->locale ?? $site->default_locale, 'category', $category->id, $url, $category->name ?? $category->category->name),
        ];
    }

    /** @return array<string, mixed> */
    private function sitePayload(Site $site, ?string $locale = null, bool $includeCommercialProfile = false): array
    {
        $locale ??= $site->default_locale;
        $availablePages = SiteUrl::query()
            ->join('site_pages', function ($join) use ($site): void {
                $join->on('site_urls.target_id', '=', 'site_pages.id')
                    ->where('site_urls.target_type', '=', 'page')
                    ->where('site_urls.site_id', '=', $site->id)
                    ->where('site_pages.site_id', '=', $site->id);
            })
            ->where(function ($query) use ($locale, $site): void {
                $query->where('site_urls.locale', $locale);
                if ($locale === $site->default_locale) {
                    $query->orWhereNull('site_urls.locale');
                }
            })
            ->where('site_pages.locale', $locale)
            ->where('site_pages.is_published', true)
            ->orderBy('site_urls.path')
            ->pluck('site_urls.path', 'site_pages.slug');

        return [
            'key' => $site->key,
            'domain' => $site->domain,
            'countryCode' => $site->country_code,
            'currencyCode' => $site->currency_code,
            'defaultLocale' => $site->default_locale,
            'name' => $site->name,
            // Navigation must be derived from the same published page/URL
            // boundary as resolution. A hard-coded frontend menu can otherwise
            // link visitors (and crawlers) to planned pages which are still
            // drafts, yielding a silent collection of 404s at launch.
            'availablePagePaths' => $availablePages->values()->all(),
            'availablePages' => $availablePages->all(),
            // Do not use legacy Site columns or drafts as a fallback. A
            // commercial block is either fully verified for this locale or
            // omitted from the public payload altogether. It is not exposed
            // on not_found/redirect payloads while the regional site is still
            // a draft.
            ...($includeCommercialProfile ? ['commercialProfile' => $this->commercialProfilePayload($site, $locale)] : []),
            'locales' => $site->locales->map(fn ($locale) => [
                'locale' => $locale->locale,
                'language' => $locale->language,
                'isDefault' => $locale->is_default,
            ])->values(),
        ];
    }

    /** @return array<string, mixed>|null */
    private function commercialProfilePayload(Site $site, string $locale): ?array
    {
        $facts = $site->commercialFacts()->published()->where('locale', $locale)->pluck('value', 'key');
        $requiredFacts = ['legal_name', 'legal_address', 'delivery_terms', 'payment_terms', 'warranty_terms'];
        foreach ($requiredFacts as $key) {
            if (! $facts->has($key) || blank($facts->get($key))) {
                return null;
            }
        }

        $contacts = $site->contacts()->published()->where('locale', $locale)->get();
        $phones = $contacts->where('type', 'phone')->pluck('value')->values()->all();
        $email = $contacts->firstWhere('type', 'email')?->value;
        if ($phones === [] || blank($email)) {
            return null;
        }

        return [
            'legalName' => $facts->get('legal_name'),
            'legalAddress' => $facts->get('legal_address'),
            'phones' => $phones,
            'email' => $email,
            'workingHours' => $contacts->firstWhere('type', 'working_hours')?->value,
            'pickupAddress' => $contacts->first(fn (SiteContact $contact): bool => $contact->type === 'address' && $contact->label === 'Самовывоз')?->value,
            'deliveryTerms' => $facts->get('delivery_terms'),
            'paymentTerms' => $facts->get('payment_terms'),
            'warrantyTerms' => $facts->get('warranty_terms'),
        ];
    }

    /** @return array<string, mixed> */
    private function seoPayload(
        Site $site,
        string $locale,
        string $type,
        int $id,
        SiteUrl $url,
        string $fallbackTitle,
        bool $allowOfferSchema = false,
        ?string $offerPrice = null,
        ?string $offerCurrency = null,
    ): array {
        $seo = SiteSeo::query()
            ->where('site_id', $site->id)
            ->where('locale', $locale)
            ->where('resource_type', $type)
            ->where('resource_id', $id)
            ->first();
        $localeEnabled = $site->locales->contains(
            fn ($siteLocale): bool => $siteLocale->locale === $locale && $siteLocale->is_enabled,
        );

        return [
            'locale' => $locale,
            'title' => $seo?->title ?? $fallbackTitle,
            'description' => $seo?->description,
            'canonicalPath' => $seo?->canonical_path ?? $url->path,
            'isIndexable' => $localeEnabled && $url->is_indexable && ($seo?->is_indexable ?? true),
            'schema' => $this->safeSchema($seo?->schema, $allowOfferSchema, $offerPrice, $offerCurrency),
            'hreflang' => $localeEnabled && $this->isIndexableHreflangUrl($url, $locale) && ($seo?->is_indexable ?? true)
                ? $this->hreflangPayload($url, $locale, $site)
                : [],
        ];
    }

    private function safeSchema(
        mixed $schema,
        bool $allowOfferSchema,
        ?string $offerPrice = null,
        ?string $offerCurrency = null,
    ): mixed {
        if (! is_array($schema)) {
            return $schema;
        }

        if (array_is_list($schema)) {
            return array_values(array_filter(array_map(
                fn (mixed $node) => $this->safeSchema($node, $allowOfferSchema, $offerPrice, $offerCurrency),
                $schema,
            ), static fn (mixed $node): bool => $node !== null));
        }

        $type = $schema['@type'] ?? $schema['type'] ?? null;
        $types = is_array($type) ? $type : [$type];
        if (in_array('Offer', $types, true)) {
            if (! $allowOfferSchema || ! $this->offerMatchesCommercialData($schema, $offerPrice, $offerCurrency)) {
                return null;
            }
        }

        foreach ($schema as $key => $value) {
            if (is_array($value)) {
                $safeValue = $this->safeSchema($value, $allowOfferSchema, $offerPrice, $offerCurrency);
                if ($safeValue === null || ($key === 'offers' && $safeValue === [])) {
                    unset($schema[$key]);
                } else {
                    $schema[$key] = $safeValue;
                }
            }
        }

        return $schema;
    }

    /** @param array<string, mixed> $offer */
    private function offerMatchesCommercialData(array $offer, ?string $price, ?string $currency): bool
    {
        if ($price === null || $currency === null || ! is_numeric($offer['price'] ?? null)) {
            return false;
        }

        $schemaCurrency = mb_strtoupper(trim((string) ($offer['priceCurrency'] ?? '')));
        $availability = trim((string) ($offer['availability'] ?? ''));

        return round((float) $offer['price'], 2, PHP_ROUND_HALF_UP) === round((float) $price, 2, PHP_ROUND_HALF_UP)
            && $schemaCurrency === mb_strtoupper($currency)
            && in_array($availability, ['InStock', 'http://schema.org/InStock', 'https://schema.org/InStock'], true);
    }

    /** @return array<string, string> */
    private function hreflangPayload(SiteUrl $url, string $locale, Site $site): array
    {
        $alternates = SiteUrlAlternate::query()
            ->with('alternateUrl.site.locales')
            ->where('source_url_id', $url->id)
            ->get()
            ->filter(fn (SiteUrlAlternate $alternate): bool => $alternate->alternateUrl !== null
                && $alternate->locale === $alternate->alternateUrl->locale
                && $this->isIndexableHreflangUrl($alternate->alternateUrl, $alternate->locale))
            ->mapWithKeys(fn (SiteUrlAlternate $alternate) => [
                $alternate->locale => "https://{$alternate->alternateUrl->site->domain}{$alternate->alternateUrl->path}",
            ])
            ->all();

        $alternates[$url->locale ?? $locale] = "https://{$site->domain}{$url->path}";

        return $alternates;
    }

    private function isIndexableHreflangUrl(SiteUrl $url, string $locale): bool
    {
        $site = $url->relationLoaded('site') ? $url->site : $url->site()->with('locales')->first();
        $urlLocale = $url->locale ?? $locale;
        if ($site === null || ! $site->is_active || ! $url->is_indexable
            || ! $site->locales->contains(fn ($siteLocale): bool => $siteLocale->locale === $urlLocale && $siteLocale->is_enabled)) {
            return false;
        }

        $seo = SiteSeo::query()
            ->where('site_id', $site->id)
            ->where('locale', $urlLocale)
            ->where('resource_type', $url->target_type)
            ->where('resource_id', $url->target_id)
            ->first();
        if ($seo !== null && (! $seo->is_indexable || $seo->canonical_path !== null && $seo->canonical_path !== $url->path)) {
            return false;
        }

        return match ($url->target_type) {
            'page' => SitePage::query()
                ->where('site_id', $site->id)
                ->published()
                ->where('locale', $urlLocale)
                ->whereKey($url->target_id)
                ->exists(),
            'product' => SiteProduct::query()->where('site_id', $site->id)->published()->whereKey($url->target_id)->exists(),
            'category' => SiteCategory::query()->where('site_id', $site->id)->published()->whereKey($url->target_id)->exists(),
            default => false,
        };
    }
}
