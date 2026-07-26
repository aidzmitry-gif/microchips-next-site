<?php

namespace App\Domain\Sites;

use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SitePage;
use App\Models\SiteProduct;
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

        if ($redirect !== null) {
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

    /** @return array<string, mixed> */
    private function pagePayload(Site $site, SiteUrl $url): array
    {
        $page = SitePage::published()
            ->where('site_id', $site->id)
            ->find($url->target_id);

        if ($page === null) {
            return ['kind' => 'not_found', 'site' => $this->sitePayload($site)];
        }

        return [
            'kind' => 'page',
            'site' => $this->sitePayload($site),
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
            ->with('product')
            ->published()
            ->where('site_id', $site->id)
            ->find($url->target_id);

        if ($siteProduct === null || $siteProduct->product === null) {
            return ['kind' => 'not_found', 'site' => $this->sitePayload($site)];
        }

        return [
            'kind' => 'product',
            'site' => $this->sitePayload($site),
            'path' => $url->path,
            'product' => [
                'name' => $siteProduct->product->name,
                'sku' => $siteProduct->product->sku,
                'mpn' => $siteProduct->product->mpn,
                'manufacturer' => $siteProduct->product->manufacturer,
                'description' => $siteProduct->product->short_description,
                'attributes' => $this->publicAttributes($siteProduct->product->technical_attributes),
                'availability' => $siteProduct->availability,
                'price' => $siteProduct->price,
                'currency' => $site->currency_code,
            ],
            'seo' => $this->seoPayload(
                $site,
                $url->locale ?? $site->default_locale,
                'product',
                $siteProduct->id,
                $url,
                $siteProduct->product->name,
                $siteProduct->price !== null && $siteProduct->availability === 'in_stock',
            ),
        ];
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
            'site' => $this->sitePayload($site),
            'path' => $url->path,
            'category' => [
                'name' => $category->name ?? $category->category->name,
                'slug' => $category->slug,
            ],
            'seo' => $this->seoPayload($site, $url->locale ?? $site->default_locale, 'category', $category->id, $url, $category->name ?? $category->category->name),
        ];
    }

    /** @return array<string, mixed> */
    private function sitePayload(Site $site): array
    {
        return [
            'key' => $site->key,
            'domain' => $site->domain,
            'countryCode' => $site->country_code,
            'currencyCode' => $site->currency_code,
            'defaultLocale' => $site->default_locale,
            'name' => $site->name,
            'locales' => $site->locales->map(fn ($locale) => [
                'locale' => $locale->locale,
                'language' => $locale->language,
                'isDefault' => $locale->is_default,
            ])->values(),
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
    ): array {
        $seo = SiteSeo::query()
            ->where('site_id', $site->id)
            ->where('locale', $locale)
            ->where('resource_type', $type)
            ->where('resource_id', $id)
            ->first();

        return [
            'locale' => $locale,
            'title' => $seo?->title ?? $fallbackTitle,
            'description' => $seo?->description,
            'canonicalPath' => $seo?->canonical_path ?? $url->path,
            'isIndexable' => $url->is_indexable && ($seo?->is_indexable ?? true),
            'schema' => $this->safeSchema($seo?->schema, $allowOfferSchema),
            'hreflang' => $this->isIndexableHreflangUrl($url, $locale) && ($seo?->is_indexable ?? true)
                ? $this->hreflangPayload($url, $locale, $site)
                : [],
        ];
    }

    private function safeSchema(mixed $schema, bool $allowOfferSchema): mixed
    {
        if (! is_array($schema) || $allowOfferSchema) {
            return $schema;
        }

        if (array_is_list($schema)) {
            return array_values(array_filter(array_map(
                fn (mixed $node) => $this->safeSchema($node, false),
                $schema,
            ), static fn (mixed $node): bool => $node !== null));
        }

        $type = $schema['@type'] ?? $schema['type'] ?? null;
        $types = is_array($type) ? $type : [$type];
        if (in_array('Offer', $types, true)) {
            return null;
        }

        unset($schema['offers']);
        foreach ($schema as $key => $value) {
            if (is_array($value)) {
                $schema[$key] = $this->safeSchema($value, false);
            }
        }

        return $schema;
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
            'page' => SitePage::query()->where('site_id', $site->id)->published()->whereKey($url->target_id)->exists(),
            'product' => SiteProduct::query()->where('site_id', $site->id)->published()->whereKey($url->target_id)->exists(),
            'category' => SiteCategory::query()->where('site_id', $site->id)->published()->whereKey($url->target_id)->exists(),
            default => false,
        };
    }
}
