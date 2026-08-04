<?php

namespace App\Domain\Seo;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use RuntimeException;

/** Canonical hash inputs shared by release-manifest generation and consumption. */
final class ProductReleaseState
{
    /** @return array<string, mixed> */
    public function product(Product $product): array
    {
        return $product->only(['id', 'external_id', 'manufacturer', 'mpn', 'sku', 'name', 'short_description', 'technical_attributes', 'status']);
    }

    /** @return array<string, mixed> */
    public function siteProduct(SiteProduct $product): array
    {
        return $product->only(['id', 'site_id', 'product_id', 'slug', 'is_published', 'availability', 'price', 'seo', 'sort_order']);
    }

    /** @return array<string, mixed> */
    public function url(SiteUrl $url): array
    {
        return $url->only(['id', 'site_id', 'path', 'locale', 'target_type', 'target_id', 'is_indexable']);
    }

    /** @return array<string, mixed> */
    public function seo(SiteSeo $seo): array
    {
        return $seo->only(['id', 'site_id', 'locale', 'resource_type', 'resource_id', 'canonical_path', 'title', 'description', 'is_indexable', 'schema']);
    }

    /** @return array<string, mixed> */
    public function commercialProfile(Site $site): array
    {
        return [
            'contacts' => SiteContact::query()->where('site_id', $site->id)->where('locale', $site->default_locale)
                ->published()->whereNotNull('verified_at')->whereNotNull('verified_by')->orderBy('id')
                ->get(['id', 'locale', 'type', 'label', 'value', 'is_primary', 'verified_at', 'verified_by', 'verification_note'])->toArray(),
            'facts' => SiteCommercialFact::query()->where('site_id', $site->id)->where('locale', $site->default_locale)
                ->published()->whereNotNull('verified_at')->whereNotNull('verified_by')->orderBy('id')
                ->get(['id', 'locale', 'key', 'value', 'verified_at', 'verified_by', 'verification_note'])->toArray(),
        ];
    }

    /**
     * Frontend robots.ts emits `Disallow: /` unless the resolved root SEO is
     * indexable, so a product release must pin the real public home page.
     *
     * @return array<string, mixed>
     */
    public function root(Site $site): array
    {
        $root = SiteUrl::query()
            ->where('site_id', $site->id)
            ->where('path', '/')
            ->where('locale', $site->default_locale)
            ->where('target_type', 'page')
            ->where('is_indexable', true)
            ->first();
        $page = $root === null ? null : SitePage::query()
            ->where('site_id', $site->id)
            ->published()
            ->find($root->target_id);
        $seo = $root === null ? null : SiteSeo::query()
            ->where('site_id', $site->id)
            ->where('locale', $site->default_locale)
            ->where('resource_type', 'page')
            ->where('resource_id', $root->target_id)
            ->where('canonical_path', '/')
            ->where('is_indexable', true)
            ->first();
        if ($root === null || $page === null || $seo === null) {
            throw new RuntimeException('Product release is blocked until the published root URL and SEO record are indexable; robots.txt otherwise disallows the whole site.');
        }
        $visibleText = mb_strtolower(implode(' ', [$page->title, $page->h1, $page->content, $seo->title, $seo->description]));
        if (preg_match('/(?:\bdemo\b|\bplaceholder\b|прототип|черновик|миграц|перенос)/ui', $visibleText) === 1) {
            throw new RuntimeException('Product release is blocked while the indexable root still contains demo, draft, prototype, or migration placeholder text.');
        }

        return [
            'url' => $this->url($root),
            'page' => $page->only(['id', 'site_id', 'locale', 'slug', 'title', 'h1', 'content', 'is_published']),
            'seo' => $this->seo($seo),
        ];
    }

    /** @param array<string, mixed> $state */
    public function hash(array $state): string
    {
        return hash('sha256', json_encode($this->canonicalize($state), JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    }

    private function canonicalize(mixed $value): mixed
    {
        if (! is_array($value)) {
            return $value;
        }
        if (! array_is_list($value)) {
            ksort($value);
        }
        foreach ($value as $key => $child) {
            $value[$key] = $this->canonicalize($child);
        }

        return $value;
    }
}
