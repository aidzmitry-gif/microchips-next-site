<?php

namespace App\Domain\Seo;

use App\Events\SiteContentChanged;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use DomainException;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

/**
 * The only application service for changing an existing public URL from
 * noindex to indexable. Draft editing and publication remain independent.
 */
final class SiteIndexabilityPublisher
{
    public function __construct(private readonly SiteSeoReleaseAuditor $auditor) {}

    public function promote(SiteUrl $url): void
    {
        $this->promoteMany([$url]);
    }

    /**
     * Atomically promote a site-scoped cohort and run the complete release
     * audit once against the resulting public surface. This is deliberately
     * the same gate used by the single-URL command; the cohort workflow adds
     * manifest pins but does not maintain a second copy of SEO rules.
     *
     * @param  iterable<SiteUrl>  $urls
     * @return array<string, mixed>
     */
    public function promoteMany(iterable $urls): array
    {
        $ids = collect($urls)
            ->map(static fn (SiteUrl $url): int => (int) $url->id)
            ->unique()
            ->values();
        if ($ids->isEmpty()) {
            throw new DomainException('At least one site URL is required for indexability promotion.');
        }

        return DB::transaction(function () use ($ids): array {
            /** @var Collection<int, SiteUrl> $lockedUrls */
            $lockedUrls = SiteUrl::query()
                ->whereIn('id', $ids->all())
                ->orderBy('id')
                ->lockForUpdate()
                ->get();
            if ($lockedUrls->count() !== $ids->count()) {
                throw new DomainException('One or more site URLs disappeared before indexability promotion.');
            }

            $siteIds = $lockedUrls->pluck('site_id')->unique();
            if ($siteIds->count() !== 1) {
                throw new DomainException('An indexability cohort must belong to exactly one site.');
            }
            $site = $lockedUrls->first()->site()->firstOrFail();
            $paths = [];
            foreach ($lockedUrls as $lockedUrl) {
                $lockedUrl->forceFill(['is_indexable' => true])->saveQuietly();
                $updated = SiteSeo::query()
                    ->where('site_id', $site->id)
                    ->where('locale', $lockedUrl->locale ?: $site->default_locale)
                    ->where('resource_type', $lockedUrl->target_type)
                    ->where('resource_id', $lockedUrl->target_id)
                    ->update(['is_indexable' => true]);
                if ($updated > 1) {
                    throw new DomainException("URL {$lockedUrl->path} matched more than one SEO record.");
                }
                $paths[] = $lockedUrl->path;
            }

            $report = $this->auditor->audit($site);
            if (! $report['passed']) {
                $codes = implode(', ', array_unique(array_column($report['issues'], 'code')));
                throw new DomainException("The URL cohort cannot become indexable until the site release audit passes: {$codes}");
            }

            SiteContentChanged::dispatch($site, array_values(array_unique([...$paths, '/sitemap.xml'])));

            return $report;
        });
    }
}
