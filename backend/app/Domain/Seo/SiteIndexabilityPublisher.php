<?php

namespace App\Domain\Seo;

use App\Models\SiteSeo;
use App\Models\SiteUrl;
use DomainException;
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
        DB::transaction(function () use ($url): void {
            /** @var SiteUrl $lockedUrl */
            $lockedUrl = SiteUrl::query()->lockForUpdate()->findOrFail($url->id);
            $site = $lockedUrl->site()->firstOrFail();

            $lockedUrl->forceFill(['is_indexable' => true])->save();
            SiteSeo::query()
                ->where('site_id', $site->id)
                ->where('locale', $lockedUrl->locale ?: $site->default_locale)
                ->where('resource_type', $lockedUrl->target_type)
                ->where('resource_id', $lockedUrl->target_id)
                ->update(['is_indexable' => true]);

            $report = $this->auditor->audit($site);
            if (! $report['passed']) {
                $codes = implode(', ', array_unique(array_column($report['issues'], 'code')));
                throw new DomainException("The URL cannot become indexable until the site release audit passes: {$codes}");
            }
        });
    }
}
