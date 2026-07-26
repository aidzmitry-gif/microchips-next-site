<?php

namespace App\Domain\Seo;

use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\SiteUrlAlternate;
use Illuminate\Support\Collection;

/**
 * Read-only release gate for the public, site-scoped SEO surface.
 *
 * This intentionally validates only records already present in the new platform.
 * It never crawls a live domain and never changes a site, redirect, or SEO record.
 */
final class SiteSeoReleaseAuditor
{
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

            $this->validateCanonical($issues, $site, $url, $seo);
            $this->validateIndexability($issues, $url, $seo, $context);
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
                'checkedUrls' => $context['urls']->count(),
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
     * @return array{
     *     site: Site,
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

        $urls = SiteUrl::query()
            ->where('site_id', $site->id)
            ->orderBy('path')
            ->get();
        $redirects = SiteRedirect::query()
            ->where('site_id', $site->id)
            ->where('is_active', true)
            ->orderBy('source_path')
            ->get();

        return [
            'site' => $site,
            'urls' => $urls,
            'urlsByPath' => $urls->keyBy('path'),
            'redirects' => $redirects,
            'redirectsBySource' => $redirects->keyBy('source_path'),
            'seoByResource' => SiteSeo::query()
                ->where('site_id', $site->id)
                ->get()
                ->keyBy(fn (SiteSeo $seo) => $this->seoKey($seo->resource_type, $seo->resource_id, $seo->locale)),
            'publishedTargetIds' => $this->publishedTargetIds($site, $urls),
            'duplicateIndexableResources' => $this->duplicateIndexableResources($site, $urls),
        ];
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
        }
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

        $locale = $site->default_locale;
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
        $requiresTerms = $indexableUrls->contains(fn (SiteUrl $url) => in_array($url->path, ['/delivery', '/payment'], true)
            || in_array($url->target_type, ['product', 'category'], true));
        $missingTerms = collect(['delivery_terms', 'payment_terms'])->filter(fn (string $key) => ! $facts->has($key))->values()->all();
        if ($requiresTerms && $missingTerms !== []) {
            $this->issue($issues, 'SEO_SITE_COMMERCIAL_TERMS_INCOMPLETE', 'Indexable commercial pages require verified local delivery and payment terms.', null, ['locale' => $locale, 'missingFacts' => $missingTerms]);
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
            if ($target === null || ! $target->is_indexable || ! $this->targetIsPublished($target, $context)) {
                $this->issue(
                    $issues,
                    'SEO_REDIRECT_TARGET_NOT_RESOLVABLE',
                    'Redirect target must resolve to an indexable published URL on the same site.',
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
        $sourceIds = $context['urls']->pluck('id')->all();
        if ($sourceIds === []) {
            return 0;
        }

        $alternates = SiteUrlAlternate::query()
            ->with([
                'sourceUrl.site.locales',
                'alternateUrl.site.locales',
            ])
            ->whereIn('source_url_id', $sourceIds)
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
        if (($seo?->is_indexable ?? true) === false || ! $this->isSelfCanonical($url, $seo)) {
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

                return ($seo?->is_indexable ?? true) && $this->isSelfCanonical($url, $seo);
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
