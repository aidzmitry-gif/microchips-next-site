<?php

namespace App\Domain\Seo;

use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\SiteUrlAlternate;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Support\Collection;

/**
 * Read-only release gate for the public, site-scoped SEO surface.
 *
 * This intentionally validates only records already present in the new platform.
 * It never crawls a live domain and never changes a site, redirect, or SEO record.
 */
final class SiteSeoReleaseAuditor
{
    private const VISIBLE_PRICE_MAX_AGE_DAYS = 30;

    /**
     * @return array{
     *     site: array{key: string, domain: string, countryCode: string},
     *     generatedAt: string,
     *     passed: bool,
     *     summary: array{checkedUrls: int, sitemapUrls: int, checkedRedirects: int, checkedHreflangAlternates: int, blockingIssues: int},
     *     issues: list<array{severity: string, code: string, message: string, path: ?string, context: array<string, mixed>}>
     * }
     */
    public function audit(Site $site): array
    {
        $context = $this->context($site);
        $issues = [];

        foreach ($context['urls'] as $url) {
            if (! $url->is_indexable) {
                continue;
            }

            $seo = $this->seoForUrl($url, $context);

            $this->validateSeoRecord($issues, $url, $seo);
            $this->validateCanonical($issues, $site, $url, $seo);
            $this->validateIndexability($issues, $url, $seo, $context);
            $this->validateVisibleProductPriceFreshness($issues, $site, $url);
            $this->validateOfferSchema($issues, $site, $url, $seo);
        }

        foreach ($context['duplicateIndexableResources'] as $duplicate) {
            $this->issue(
                $issues,
                'SEO_INDEXABLE_RESOURCE_DUPLICATE_PATH',
                'One resource and locale cannot have more than one indexable URL; use a redirect for an alias.',
                $duplicate['paths'][0],
                [
                    'targetType' => $duplicate['target_type'],
                    'targetId' => $duplicate['target_id'],
                    'locale' => $duplicate['locale'],
                    'paths' => $duplicate['paths'],
                ],
            );
        }

        $this->validateRegionalCommercialProfile($issues, $site, $context);
        $this->validatePublishedLeafCategoriesHaveProducts($issues, $site);

        $this->validateRedirects($issues, $context);
        $alternateCount = $this->validateHreflang($issues, $context);
        $sitemapUrls = $this->sitemapUrlsFromContext($context);

        return [
            'site' => [
                'key' => $site->key,
                'domain' => $site->domain,
                'countryCode' => $site->country_code,
            ],
            'generatedAt' => now()->toAtomString(),
            'passed' => $issues === [],
            'summary' => [
                'checkedUrls' => $context['checkedUrlCount'],
                'sitemapUrls' => $sitemapUrls->count(),
                'checkedRedirects' => $context['redirects']->count(),
                'checkedHreflangAlternates' => $alternateCount,
                'blockingIssues' => count($issues),
            ],
            'issues' => $issues,
        ];
    }

    /** @return Collection<int, SiteUrl> */
    public function sitemapUrls(Site $site): Collection
    {
        return $this->sitemapUrlsFromContext($this->context($site));
    }

    /**
     * A numeric price can be shown on a noindex migration preview, but it may
     * not be released into the index without fresh, matching provenance. This
     * is intentionally independent of Offer eligibility: a fresh price does
     * not claim availability or create an Offer.
     *
     * @param  list<array{severity: string, code: string, message: string, path: ?string, context: array<string, mixed>}>  $issues
     */
    private function validateVisibleProductPriceFreshness(array &$issues, Site $site, SiteUrl $url): void
    {
        if ($url->target_type !== 'product' || $url->target_id === null) {
            return;
        }

        $product = SiteProduct::query()
            ->where('site_id', $site->id)
            ->find($url->target_id);
        if ($product === null || $product->price === null) {
            return;
        }

        $evidence = SiteProductPriceEvidence::query()
            ->where('site_id', $site->id)
            ->where('site_product_id', $product->id)
            ->where('is_current', true)
            ->where('calculated_price', $product->price)
            ->where('currency', $site->currency_code)
            ->latest('observed_at')
            ->first();

        if ($evidence === null || $evidence->observed_at === null) {
            $this->issue(
                $issues,
                'SEO_VISIBLE_PRICE_EVIDENCE_MISSING',
                'An indexable product with a visible local price requires current provenance evidence matching its price and currency.',
                $url->path,
                ['targetId' => $url->target_id],
            );

            return;
        }

        $freshAfter = now()->subDays(self::VISIBLE_PRICE_MAX_AGE_DAYS);
        if ($evidence->observed_at->lt($freshAfter)) {
            $this->issue(
                $issues,
                'SEO_VISIBLE_PRICE_EVIDENCE_STALE',
                'An indexable product price must have matching provenance evidence observed within the last 30 days.',
                $url->path,
                [
                    'targetId' => $url->target_id,
                    'observedAt' => $evidence->observed_at->toAtomString(),
                    'freshAfter' => $freshAfter->toAtomString(),
                ],
            );
        }
    }

    /**
     * @return array{
     *     site: Site,
     *     checkedUrlCount: int,
     *     urls: Collection<int, SiteUrl>,
     *     urlsByPath: Collection<string, SiteUrl>,
     *     redirects: Collection<int, SiteRedirect>,
     *     redirectsBySource: Collection<string, SiteRedirect>,
     *     seoByResource: Collection<string, SiteSeo>,
     *     publishedTargetIds: array<string, array<int, bool>>,
     *     duplicateIndexableResources: array<string, array{target_type: string, target_id: ?int, locale: string, paths: list<string>}>
     * }
     */
    private function context(Site $site): array
    {
        $site->loadMissing('locales');

        $checkedUrlCount = SiteUrl::query()
            ->where('site_id', $site->id)
            ->count();
        $redirects = SiteRedirect::query()
            ->select(['id', 'site_id', 'source_path', 'target_path', 'status_code', 'purpose'])
            ->where('site_id', $site->id)
            ->where('is_active', true)
            ->orderBy('source_path')
            ->get();
        $redirectTargetPaths = $redirects->pluck('target_path')->unique()->values()->all();

        // Noindex URLs do not participate in the release surface unless an
        // active redirect resolves to them. Keeping every hydrated URL and SEO
        // model made the audit grow with the entire migration inventory rather
        // than the public surface (and exhausted PHP's default 128 MB limit).
        $urls = SiteUrl::query()
            ->select(['id', 'site_id', 'path', 'locale', 'target_type', 'target_id', 'is_indexable', 'updated_at'])
            ->where('site_id', $site->id)
            ->where(function (Builder $query) use ($redirectTargetPaths): void {
                $query->where('is_indexable', true);
                if ($redirectTargetPaths !== []) {
                    $query->orWhereIn('path', $redirectTargetPaths);
                }
            })
            ->orderBy('path')
            ->get();

        return [
            'site' => $site,
            'checkedUrlCount' => $checkedUrlCount,
            'urls' => $urls,
            'urlsByPath' => $urls->keyBy('path'),
            'redirects' => $redirects,
            'redirectsBySource' => $redirects->keyBy('source_path'),
            'seoByResource' => $this->seoByResource($site, $urls),
            'publishedTargetIds' => $this->publishedTargetIds($site, $urls),
            'duplicateIndexableResources' => $this->duplicateIndexableResources($site, $urls),
        ];
    }

    /**
     * Only indexable URL resources need SEO records in the release context.
     * Redirect-only noindex targets are validated as published resources, while
     * hreflang records perform their own target SEO lookup.
     *
     * @param  Collection<int, SiteUrl>  $urls
     * @return Collection<string, SiteSeo>
     */
    private function seoByResource(Site $site, Collection $urls): Collection
    {
        $groups = $urls
            ->filter(fn (SiteUrl $url): bool => $url->is_indexable)
            ->groupBy(fn (SiteUrl $url): string => $url->target_type.'|'.$this->localeFor($url, $site));

        if ($groups->isEmpty()) {
            return collect();
        }

        return SiteSeo::query()
            ->select(['id', 'site_id', 'locale', 'resource_type', 'resource_id', 'canonical_path', 'is_indexable', 'schema'])
            ->where('site_id', $site->id)
            ->where(function (Builder $query) use ($groups, $site): void {
                foreach ($groups as $group) {
                    /** @var Collection<int, SiteUrl> $group */
                    /** @var SiteUrl $first */
                    $first = $group->first();
                    $resourceIds = $group->pluck('target_id')->filter()->unique()->values()->all();
                    $hasNullResource = $group->contains(fn (SiteUrl $url): bool => $url->target_id === null);

                    $query->orWhere(function (Builder $resourceQuery) use ($first, $site, $resourceIds, $hasNullResource): void {
                        $resourceQuery
                            ->where('resource_type', $first->target_type)
                            ->where('locale', $this->localeFor($first, $site))
                            ->where(function (Builder $idQuery) use ($resourceIds, $hasNullResource): void {
                                if ($resourceIds !== []) {
                                    $idQuery->whereIn('resource_id', $resourceIds);
                                }
                                if ($hasNullResource) {
                                    $resourceIds === []
                                        ? $idQuery->whereNull('resource_id')
                                        : $idQuery->orWhereNull('resource_id');
                                }
                            });
                    });
                }
            })
            ->get()
            ->keyBy(fn (SiteSeo $seo) => $this->seoKey($seo->resource_type, $seo->resource_id, $seo->locale));
    }

    /** @param Collection<int, SiteUrl> $urls
     * @return array<string, array{target_type: string, target_id: ?int, locale: string, paths: list<string>}>
     */
    private function duplicateIndexableResources(Site $site, Collection $urls): array
    {
        return $urls
            ->filter(fn (SiteUrl $url): bool => $url->is_indexable)
            ->groupBy(fn (SiteUrl $url): string => $this->resourceLocaleKey($url, $site))
            ->filter(fn (Collection $group): bool => $group->count() > 1)
            ->mapWithKeys(function (Collection $group, string $key) use ($site): array {
                /** @var SiteUrl $first */
                $first = $group->first();

                return [$key => [
                    'target_type' => $first->target_type,
                    'target_id' => $first->target_id,
                    'locale' => $this->localeFor($first, $site),
                    'paths' => $group->pluck('path')->sort()->values()->all(),
                ]];
            })
            ->all();
    }

    /** @param Collection<int, SiteUrl> $urls
     * @return array<string, array<int, bool>>
     */
    private function publishedTargetIds(Site $site, Collection $urls): array
    {
        $idsFor = fn (string $type) => $urls
            ->where('target_type', $type)
            ->pluck('target_id')
            ->filter()
            ->unique()
            ->values()
            ->all();

        $publishedIds = [
            'page' => SitePage::query()
                ->where('site_id', $site->id)
                ->published()
                ->whereIn('id', $idsFor('page'))
                ->pluck('id')
                ->all(),
            'product' => SiteProduct::query()
                ->where('site_id', $site->id)
                ->published()
                ->whereIn('id', $idsFor('product'))
                ->pluck('id')
                ->all(),
            'category' => SiteCategory::query()
                ->where('site_id', $site->id)
                ->published()
                ->whereIn('id', $idsFor('category'))
                ->pluck('id')
                ->all(),
        ];

        return collect($publishedIds)
            ->map(fn (array $ids) => array_fill_keys($ids, true))
            ->all();
    }

    /**
     * @param  array<string, mixed>  $context
     */
    private function seoForUrl(SiteUrl $url, array $context): ?SiteSeo
    {
        return $context['seoByResource']->get(
            $this->seoKey($url->target_type, $url->target_id, $this->localeFor($url, $context['site'])),
        );
    }

    /**
     * A public URL must have an explicit site-scoped SEO record. Falling back
     * to the URL path hides missing title/robots/schema ownership and lets a
     * partial import enter the sitemap. Draft/noindex URLs remain allowed to
     * omit an SEO record because they are not a public SEO surface.
     *
     * @param  list<array{severity: string, code: string, message: string, path: ?string, context: array<string, mixed>}>  $issues
     */
    private function validateSeoRecord(array &$issues, SiteUrl $url, ?SiteSeo $seo): void
    {
        if ($seo !== null) {
            return;
        }

        $this->issue(
            $issues,
            'SEO_INDEXABLE_URL_SEO_RECORD_MISSING',
            'An indexable URL must have an explicit site-scoped SEO record before it can enter the sitemap.',
            $url->path,
            [
                'targetType' => $url->target_type,
                'targetId' => $url->target_id,
                'locale' => $url->locale,
            ],
        );
    }

    /**
     * @param  list<array{severity: string, code: string, message: string, path: ?string, context: array<string, mixed>}>  $issues
     */
    private function validateCanonical(array &$issues, Site $site, SiteUrl $url, ?SiteSeo $seo): void
    {
        $canonical = trim((string) ($seo?->canonical_path ?? $url->path));
        $canonicalHost = parse_url($canonical, PHP_URL_HOST);

        if (is_string($canonicalHost) && $canonicalHost !== '') {
            $code = strcasecmp($canonicalHost, $site->domain) === 0
                ? 'SEO_CANONICAL_EXTERNAL_FORMAT'
                : 'SEO_CANONICAL_CROSS_COUNTRY';

            $this->issue(
                $issues,
                $code,
                'Canonical must be a local path generated on the current site domain.',
                $url->path,
                ['canonical' => $canonical, 'siteDomain' => $site->domain],
            );

            return;
        }

        if (! $this->isSafeLocalPath($canonical)) {
            $this->issue(
                $issues,
                'SEO_CANONICAL_NOT_LOCAL_PATH',
                'Canonical contains a query, fragment, authority, or invalid local path.',
                $url->path,
                ['canonical' => $canonical],
            );

            return;
        }

        if ($canonical !== $url->path) {
            $this->issue(
                $issues,
                'SEO_CANONICAL_NOT_SELF',
                'An indexable URL must use its own normalized path as canonical.',
                $url->path,
                ['canonical' => $canonical],
            );
        }
    }

    /**
     * @param  list<array{severity: string, code: string, message: string, path: ?string, context: array<string, mixed>}>  $issues
     * @param  array<string, mixed>  $context
     */
    private function validateIndexability(array &$issues, SiteUrl $url, ?SiteSeo $seo, array $context): void
    {
        $locale = $this->localeFor($url, $context['site']);
        if (! $this->siteHasEnabledLocale($context['site'], $locale)) {
            $this->issue(
                $issues,
                'SEO_INDEXABLE_URL_LOCALE_DISABLED',
                'An indexable URL must use an enabled locale on its own site.',
                $url->path,
                ['locale' => $locale],
            );
        }

        if (! $this->isSitemapSafePath($url->path)) {
            $this->issue(
                $issues,
                'SEO_SITEMAP_UNSAFE_PATH',
                'An indexable URL contains a query, filter route, or utility route and must not enter a sitemap.',
                $url->path,
            );
        }

        if ($seo !== null && ! $seo->is_indexable) {
            $this->issue(
                $issues,
                'SEO_INDEXABILITY_CONFLICT',
                'The URL is indexable, but its site-scoped SEO record is marked noindex.',
                $url->path,
            );
        }

        if (! $this->targetIsPublished($url, $context)) {
            $this->issue(
                $issues,
                'SEO_INDEXABLE_TARGET_NOT_PUBLISHED',
                'An indexable URL does not resolve to a published resource for this site.',
                $url->path,
                ['targetType' => $url->target_type, 'targetId' => $url->target_id],
            );
        }

        if ($url->target_type === 'page' && $url->target_id !== null) {
            $pageLocale = SitePage::query()->where('site_id', $context['site']->id)->whereKey($url->target_id)->value('locale');
            if ($pageLocale !== null && $pageLocale !== $locale) {
                $this->issue(
                    $issues,
                    'SEO_PAGE_URL_LOCALE_MISMATCH',
                    'A localized page URL must resolve to a page with the same locale.',
                    $url->path,
                    ['urlLocale' => $locale, 'pageLocale' => $pageLocale, 'targetId' => $url->target_id],
                );
            }
        }

        if ($context['redirectsBySource']->has($url->path)) {
            $this->issue(
                $issues,
                'SEO_INDEXABLE_REDIRECT_SOURCE',
                'A redirect source cannot be included as an indexable URL or sitemap entry.',
                $url->path,
            );
        }
    }

    /**
     * @param  list<array{severity: string, code: string, message: string, path: ?string, context: array<string, mixed>}>  $issues
     */
    private function validateOfferSchema(array &$issues, Site $site, SiteUrl $url, ?SiteSeo $seo): void
    {
        if ($seo === null || ! $this->containsOfferSchema($seo->schema)) {
            return;
        }

        if ($url->target_type !== 'product' || $url->target_id === null) {
            $this->issue(
                $issues,
                'SEO_OFFER_SCHEMA_NON_PRODUCT',
                'Offer schema is allowed only on a published commercial product URL.',
                $url->path,
            );

            return;
        }

        $product = SiteProduct::query()
            ->where('site_id', $site->id)
            ->published()
            ->find($url->target_id);

        if ($product === null || $product->price === null || $product->availability !== 'in_stock') {
            $this->issue(
                $issues,
                'SEO_OFFER_SCHEMA_UNCONFIRMED_COMMERCIAL_DATA',
                'Offer schema requires a published in-stock product with confirmed local price.',
                $url->path,
                ['targetId' => $url->target_id],
            );

            return;
        }

        $hasCurrentEvidence = SiteProductPriceEvidence::query()
            ->where('site_id', $site->id)
            ->where('site_product_id', $product->id)
            ->where('is_current', true)
            ->where('calculated_price', $product->price)
            ->where('currency', $site->currency_code)
            ->exists();
        if (! $hasCurrentEvidence) {
            $this->issue(
                $issues,
                'SEO_OFFER_SCHEMA_PRICE_EVIDENCE_MISSING',
                'Offer schema requires current provenance evidence matching the visible local price and currency.',
                $url->path,
                ['targetId' => $url->target_id],
            );

            return;
        }

        foreach ($this->offerSchemas($seo->schema) as $offer) {
            if (! $this->offerMatchesCommercialData($offer, (string) $product->price, $site->currency_code)) {
                $this->issue(
                    $issues,
                    'SEO_OFFER_SCHEMA_COMMERCIAL_DATA_MISMATCH',
                    'Offer price, currency and availability must match the visible, evidence-backed local commercial data.',
                    $url->path,
                    ['targetId' => $url->target_id],
                );

                break;
            }
        }
    }

    /** @return list<array<string, mixed>> */
    private function offerSchemas(mixed $schema): array
    {
        if (! is_array($schema)) {
            return [];
        }

        $offers = [];
        $type = $schema['@type'] ?? $schema['type'] ?? null;
        if (! array_is_list($schema) && in_array('Offer', is_array($type) ? $type : [$type], true)) {
            $offers[] = $schema;
        }
        foreach ($schema as $value) {
            $offers = [...$offers, ...$this->offerSchemas($value)];
        }

        return $offers;
    }

    /** @param array<string, mixed> $offer */
    private function offerMatchesCommercialData(array $offer, string $price, string $currency): bool
    {
        if (! is_numeric($offer['price'] ?? null)) {
            return false;
        }

        $schemaCurrency = mb_strtoupper(trim((string) ($offer['priceCurrency'] ?? '')));
        $availability = trim((string) ($offer['availability'] ?? ''));

        return round((float) $offer['price'], 2, PHP_ROUND_HALF_UP) === round((float) $price, 2, PHP_ROUND_HALF_UP)
            && $schemaCurrency === mb_strtoupper($currency)
            && in_array($availability, ['InStock', 'http://schema.org/InStock', 'https://schema.org/InStock'], true);
    }

    /**
     * Indexable commercial pages must not be released until factual local
     * business data is independently verified. Site columns are deliberately
     * not accepted as evidence because they have no approval provenance.
     *
     * @param  list<array{severity: string, code: string, message: string, path: ?string, context: array<string, mixed>}>  $issues
     * @param  array<string, mixed>  $context
     */
    private function validateRegionalCommercialProfile(array &$issues, Site $site, array $context): void
    {
        $indexableUrls = $this->sitemapUrlsFromContext($context);
        if ($indexableUrls->isEmpty()) {
            return;
        }

        foreach ($indexableUrls->groupBy(fn (SiteUrl $url) => $this->localeFor($url, $site)) as $locale => $localeUrls) {
            $contacts = SiteContact::query()
                ->published()
                ->where('site_id', $site->id)
                ->where('locale', $locale)
                ->whereNotNull('verified_at')
                ->whereNotNull('verified_by')
                ->whereNotNull('verification_note')
                ->get()
                ->groupBy('type');
            $facts = SiteCommercialFact::query()
                ->published()
                ->where('site_id', $site->id)
                ->where('locale', $locale)
                ->whereNotNull('verified_at')
                ->whereNotNull('verified_by')
                ->whereNotNull('verification_note')
                ->get()
                ->keyBy('key');

            $missingLegal = collect(['legal_name', 'legal_address'])->filter(fn (string $key) => ! $facts->has($key))->values()->all();
            if ($missingLegal !== [] || ! $contacts->has('legal_entity') || ! $contacts->has('address')) {
                $this->issue($issues, 'SEO_SITE_LEGAL_PROFILE_INCOMPLETE', 'Indexable pages require verified local legal entity and address facts.', null, ['locale' => $locale, 'missingFacts' => $missingLegal]);
            }
            $missingContacts = collect(['phone', 'email'])->filter(fn (string $type) => ! $contacts->has($type))->values()->all();
            if ($missingContacts !== []) {
                $this->issue($issues, 'SEO_SITE_CONTACT_PROFILE_INCOMPLETE', 'Indexable pages require verified local phone and email contacts.', null, ['locale' => $locale, 'missingTypes' => $missingContacts]);
            }
            $requiresTerms = $localeUrls->contains(fn (SiteUrl $url) => in_array($url->path, ['/delivery', '/payment'], true)
                || in_array($url->target_type, ['product', 'category'], true));
            $missingTerms = collect(['delivery_terms', 'payment_terms'])->filter(fn (string $key) => ! $facts->has($key))->values()->all();
            if ($requiresTerms && $missingTerms !== []) {
                $this->issue($issues, 'SEO_SITE_COMMERCIAL_TERMS_INCOMPLETE', 'Indexable commercial pages require verified local delivery and payment terms.', null, ['locale' => $locale, 'missingFacts' => $missingTerms]);
            }

            $requiresWarrantyTerms = $localeUrls->contains(
                fn (SiteUrl $url) => in_array($url->path, ['/warranty', '/warranty-and-documents'], true),
            );
            if ($requiresWarrantyTerms && ! $facts->has('warranty_terms')) {
                $this->issue($issues, 'SEO_SITE_WARRANTY_TERMS_INCOMPLETE', 'An indexable warranty page requires verified local warranty and returns terms.', null, ['locale' => $locale, 'missingFacts' => ['warranty_terms']]);
            }
        }
    }

    /**
     * A published leaf category without a published product is an empty
     * landing page. Parent categories are deliberately exempt when they have
     * published children, because their buyer value is the navigation tree.
     *
     * @param  list<array{severity: string, code: string, message: string, path: ?string, context: array<string, mixed>}>  $issues
     */
    private function validatePublishedLeafCategoriesHaveProducts(array &$issues, Site $site): void
    {
        $categories = SiteCategory::query()
            ->with('category')
            ->where('site_id', $site->id)
            ->published()
            ->get();
        $publishedCanonicalIds = $categories->pluck('category_id')->filter()->all();

        foreach ($categories as $category) {
            $hasPublishedChild = $category->category !== null
                && $categories->contains(fn (SiteCategory $candidate): bool => $candidate->category?->parent_id === $category->category_id);
            if ($hasPublishedChild || $category->products()->where('site_products.is_published', true)->exists()) {
                continue;
            }

            $this->issue(
                $issues,
                'SEO_PUBLISHED_CATEGORY_EMPTY',
                'A published leaf category must contain at least one published product.',
                null,
                ['siteCategoryId' => $category->id, 'externalId' => $category->external_id, 'publishedCanonicalIds' => $publishedCanonicalIds],
            );
        }
    }

    private function containsOfferSchema(mixed $schema): bool
    {
        if (! is_array($schema)) {
            return false;
        }

        $type = $schema['@type'] ?? $schema['type'] ?? null;
        if (in_array('Offer', is_array($type) ? $type : [$type], true)) {
            return true;
        }

        foreach ($schema as $value) {
            if ($this->containsOfferSchema($value)) {
                return true;
            }
        }

        return false;
    }

    /**
     * @param  list<array{severity: string, code: string, message: string, path: ?string, context: array<string, mixed>}>  $issues
     * @param  array<string, mixed>  $context
     */
    private function validateRedirects(array &$issues, array $context): void
    {
        foreach ($context['redirects'] as $redirect) {
            if (! in_array($redirect->purpose, [SiteRedirect::PURPOSE_SEO, SiteRedirect::PURPOSE_PREVIEW], true)) {
                $this->issue(
                    $issues,
                    'SEO_REDIRECT_PURPOSE_INVALID',
                    'Redirect purpose must be seo or preview.',
                    $redirect->source_path,
                    ['redirectId' => $redirect->id, 'purpose' => $redirect->purpose],
                );
            }

            if (! $this->isSafeLocalPath($redirect->source_path)) {
                $this->issue(
                    $issues,
                    'SEO_REDIRECT_UNSAFE_SOURCE',
                    'Redirect source must be a normalized local path without a query or fragment.',
                    $redirect->source_path,
                    ['redirectId' => $redirect->id],
                );
            }

            if (! $this->isSafeLocalPath($redirect->target_path)) {
                $this->issue(
                    $issues,
                    'SEO_REDIRECT_UNSAFE_TARGET',
                    'Redirect target must be a normalized local path on the same site.',
                    $redirect->source_path,
                    ['redirectId' => $redirect->id, 'target' => $redirect->target_path],
                );

                continue;
            }

            if (! in_array($redirect->status_code, [301, 308], true)) {
                $this->issue(
                    $issues,
                    'SEO_REDIRECT_NOT_PERMANENT',
                    'Release redirects must use a permanent 301 or 308 status.',
                    $redirect->source_path,
                    ['redirectId' => $redirect->id, 'statusCode' => $redirect->status_code],
                );
            }

            if ($redirect->source_path === $redirect->target_path) {
                $this->issue(
                    $issues,
                    'SEO_REDIRECT_SELF_REFERENCE',
                    'Redirect source and target cannot be the same path.',
                    $redirect->source_path,
                    ['redirectId' => $redirect->id],
                );
            }

            if ($redirect->target_path === '/') {
                $this->issue(
                    $issues,
                    'SEO_REDIRECT_TO_HOME',
                    'Redirects to the home page are release blockers unless a migration decision explicitly changes this rule.',
                    $redirect->source_path,
                    ['redirectId' => $redirect->id],
                );
            }

            if ($context['redirectsBySource']->has($redirect->target_path)) {
                $this->issue(
                    $issues,
                    'SEO_REDIRECT_CHAIN',
                    'Redirect target is another active redirect source.',
                    $redirect->source_path,
                    ['redirectId' => $redirect->id, 'target' => $redirect->target_path],
                );
            }

            $target = $context['urlsByPath']->get($redirect->target_path);
            $requiresIndexableTarget = $redirect->purpose !== SiteRedirect::PURPOSE_PREVIEW;
            if ($target === null
                || ! $this->targetIsPublished($target, $context)
                || ($requiresIndexableTarget && ! $target->is_indexable)) {
                $this->issue(
                    $issues,
                    'SEO_REDIRECT_TARGET_NOT_RESOLVABLE',
                    $requiresIndexableTarget
                        ? 'SEO redirect target must resolve to an indexable published URL on the same site.'
                        : 'Preview redirect target must resolve to a published URL on the same site.',
                    $redirect->source_path,
                    ['redirectId' => $redirect->id, 'target' => $redirect->target_path],
                );
            }
        }
    }

    /**
     * @param  list<array{severity: string, code: string, message: string, path: ?string, context: array<string, mixed>}>  $issues
     * @param  array<string, mixed>  $context
     */
    private function validateHreflang(array &$issues, array $context): int
    {
        $alternates = SiteUrlAlternate::query()
            ->with([
                'sourceUrl.site.locales',
                'alternateUrl.site.locales',
            ])
            ->whereHas('sourceUrl', fn (Builder $query) => $query->where('site_id', $context['site']->id))
            ->get();
        $alternateIds = $alternates->pluck('alternate_url_id')->unique()->values()->all();
        $reverseKeys = SiteUrlAlternate::query()
            ->whereIn('source_url_id', $alternateIds)
            ->get()
            ->mapWithKeys(fn (SiteUrlAlternate $alternate) => [
                $this->alternateKey($alternate->source_url_id, $alternate->alternate_url_id, $alternate->locale) => true,
            ]);

        foreach ($alternates->groupBy(fn (SiteUrlAlternate $alternate) => $alternate->source_url_id.'|'.$alternate->locale) as $duplicates) {
            if ($duplicates->count() > 1) {
                $source = $duplicates->first()->sourceUrl;
                $this->issue(
                    $issues,
                    'SEO_HREFLANG_DUPLICATE_LOCALE',
                    'A source URL cannot emit more than one alternate for the same hreflang locale.',
                    $source?->path,
                    ['locale' => $duplicates->first()->locale],
                );
            }
        }

        foreach ($alternates as $alternate) {
            $source = $alternate->sourceUrl;
            $target = $alternate->alternateUrl;

            if ($source === null || $target === null || $source->site === null || $target->site === null) {
                $this->issue(
                    $issues,
                    'SEO_HREFLANG_MISSING_URL',
                    'Hreflang must reference existing site-scoped URLs.',
                    null,
                    ['alternateId' => $alternate->id],
                );

                continue;
            }

            $sourceLocale = $this->localeFor($source, $source->site);
            $targetLocale = $this->localeFor($target, $target->site);

            if (! $source->is_indexable || ! $this->isSitemapSafePath($source->path)) {
                $this->issue(
                    $issues,
                    'SEO_HREFLANG_SOURCE_NOT_INDEXABLE',
                    'Hreflang source must be an indexable, canonical sitemap-safe URL.',
                    $source->path,
                    ['alternateId' => $alternate->id],
                );
            }

            if (! $target->is_indexable || ! $this->isSitemapSafePath($target->path)) {
                $this->issue(
                    $issues,
                    'SEO_HREFLANG_ALTERNATE_NOT_INDEXABLE',
                    'Hreflang alternate must be an indexable, canonical sitemap-safe URL.',
                    $source->path,
                    ['alternateId' => $alternate->id, 'alternatePath' => $target->path],
                );
            }

            if (! $this->hreflangUrlHasPublishedSelfCanonicalTarget($source)) {
                $this->issue(
                    $issues,
                    'SEO_HREFLANG_SOURCE_TARGET_NOT_PUBLISHED_OR_CANONICAL',
                    'Hreflang source must resolve to a published self-canonical resource.',
                    $source->path,
                    ['alternateId' => $alternate->id],
                );
            }

            if (! $this->hreflangUrlHasPublishedSelfCanonicalTarget($target)) {
                $this->issue(
                    $issues,
                    'SEO_HREFLANG_ALTERNATE_TARGET_NOT_PUBLISHED_OR_CANONICAL',
                    'Hreflang alternate must resolve to a published self-canonical resource.',
                    $source->path,
                    ['alternateId' => $alternate->id, 'alternatePath' => $target->path],
                );
            }

            if (! $this->siteHasEnabledLocale($source->site, $sourceLocale)) {
                $this->issue(
                    $issues,
                    'SEO_HREFLANG_SOURCE_LOCALE_DISABLED',
                    'Hreflang source locale is not enabled for its site.',
                    $source->path,
                    ['locale' => $sourceLocale],
                );
            }

            if (! $this->siteHasEnabledLocale($target->site, $targetLocale)) {
                $this->issue(
                    $issues,
                    'SEO_HREFLANG_ALTERNATE_LOCALE_DISABLED',
                    'Hreflang alternate locale is not enabled for the alternate site.',
                    $source->path,
                    ['alternateLocale' => $targetLocale],
                );
            }

            if ($alternate->locale !== $targetLocale) {
                $this->issue(
                    $issues,
                    'SEO_HREFLANG_LOCALE_MISMATCH',
                    'The alternate locale must equal the locale of its target URL.',
                    $source->path,
                    ['declaredLocale' => $alternate->locale, 'targetLocale' => $targetLocale],
                );
            }

            if (! $reverseKeys->has($this->alternateKey($target->id, $source->id, $sourceLocale))) {
                $this->issue(
                    $issues,
                    'SEO_HREFLANG_NOT_RECIPROCAL',
                    'Every hreflang alternate must have a reciprocal alternate back to the source URL.',
                    $source->path,
                    ['alternatePath' => $target->path, 'expectedLocale' => $sourceLocale],
                );
            }
        }

        return $alternates->count();
    }

    private function hreflangUrlHasPublishedSelfCanonicalTarget(SiteUrl $url): bool
    {
        $seo = SiteSeo::query()
            ->where('site_id', $url->site_id)
            ->where('locale', $this->localeFor($url, $url->site))
            ->where('resource_type', $url->target_type)
            ->where('resource_id', $url->target_id)
            ->first();
        if ($seo === null || ! $seo->is_indexable || ! $this->isSelfCanonical($url, $seo)) {
            return false;
        }

        return match ($url->target_type) {
            'page' => SitePage::query()->where('site_id', $url->site_id)->published()->whereKey($url->target_id)->exists(),
            'product' => SiteProduct::query()->where('site_id', $url->site_id)->published()->whereKey($url->target_id)->exists(),
            'category' => SiteCategory::query()->where('site_id', $url->site_id)->published()->whereKey($url->target_id)->exists(),
            default => false,
        };
    }

    /**
     * @param  array<string, mixed>  $context
     * @return Collection<int, SiteUrl>
     */
    private function sitemapUrlsFromContext(array $context): Collection
    {
        return $context['urls']
            ->filter(fn (SiteUrl $url) => $url->is_indexable)
            ->filter(fn (SiteUrl $url) => ! array_key_exists($this->resourceLocaleKey($url, $context['site']), $context['duplicateIndexableResources']))
            ->filter(fn (SiteUrl $url) => $this->siteHasEnabledLocale($context['site'], $this->localeFor($url, $context['site'])))
            ->filter(fn (SiteUrl $url) => $this->isSitemapSafePath($url->path))
            ->filter(fn (SiteUrl $url) => ! $context['redirectsBySource']->has($url->path))
            ->filter(fn (SiteUrl $url) => $this->targetIsPublished($url, $context))
            ->filter(function (SiteUrl $url) use ($context): bool {
                $seo = $this->seoForUrl($url, $context);

                return $seo !== null && $seo->is_indexable && $this->isSelfCanonical($url, $seo);
            })
            ->sortBy('path')
            ->values();
    }

    /** @param array<string, mixed> $context */
    private function targetIsPublished(SiteUrl $url, array $context): bool
    {
        $publishedIds = $context['publishedTargetIds'][$url->target_type] ?? [];

        return ($publishedIds[$url->target_id ?? 0] ?? false) === true;
    }

    private function isSelfCanonical(SiteUrl $url, ?SiteSeo $seo): bool
    {
        $canonical = trim((string) ($seo?->canonical_path ?? $url->path));

        return $this->isSafeLocalPath($canonical) && $canonical === $url->path;
    }

    private function isSitemapSafePath(string $path): bool
    {
        if (! $this->isSafeLocalPath($path)) {
            return false;
        }

        return preg_match('#/(?:filter|search|sort|basket|cart|compare|personal)(?:/|$)#i', $path) !== 1;
    }

    private function isSafeLocalPath(string $path): bool
    {
        if ($path === '' || ! str_starts_with($path, '/') || str_starts_with($path, '//') || str_contains($path, '\\')) {
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

        $normalized = $this->normalizePath($path);

        return $normalized === $path;
    }

    private function normalizePath(string $path): string
    {
        $path = '/'.ltrim((string) (parse_url($path, PHP_URL_PATH) ?: '/'), '/');
        $path = preg_replace('#/+#', '/', $path) ?? '/';

        return $path === '/' ? $path : rtrim($path, '/');
    }

    private function localeFor(SiteUrl $url, Site $site): string
    {
        return $url->locale ?: $site->default_locale;
    }

    private function resourceLocaleKey(SiteUrl $url, Site $site): string
    {
        return implode('|', [$url->target_type, $url->target_id ?? 'none', $this->localeFor($url, $site)]);
    }

    private function siteHasEnabledLocale(Site $site, string $locale): bool
    {
        return $site->locales->contains(
            fn ($siteLocale) => $siteLocale->locale === $locale && $siteLocale->is_enabled,
        );
    }

    private function seoKey(string $type, ?int $id, string $locale): string
    {
        return implode('|', [$type, $id ?? 'none', $locale]);
    }

    private function alternateKey(int $sourceId, int $targetId, string $locale): string
    {
        return implode('|', [$sourceId, $targetId, $locale]);
    }

    /**
     * @param  list<array{severity: string, code: string, message: string, path: ?string, context: array<string, mixed>}>  $issues
     * @param  array<string, mixed>  $context
     */
    private function issue(array &$issues, string $code, string $message, ?string $path, array $context = []): void
    {
        $issues[] = [
            'severity' => 'blocker',
            'code' => $code,
            'message' => $message,
            'path' => $path,
            'context' => $context,
        ];
    }
}
