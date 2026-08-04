<?php

namespace App\Domain\Launch;

use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Models\Site;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SiteUrl;

/**
 * Read-only deployment preflight. It does not certify external services or
 * mutate indexability; it makes every missing configuration explicit before
 * an operator attempts a country launch.
 */
final class SiteLaunchPreflight
{
    public function __construct(private readonly SiteSeoReleaseAuditor $seoAuditor) {}

    /** @return array<string, mixed> */
    public function inspect(Site $site): array
    {
        $issues = [];
        if (! $site->is_active) {
            $this->issue($issues, 'SITE_INACTIVE', 'The site profile is inactive.');
        }
        if (! SiteUrl::query()->where('site_id', $site->id)->where('is_indexable', true)->exists()) {
            $this->issue($issues, 'INDEXABLE_URL_MISSING', 'No indexable URL is configured for this site.');
        }

        $this->assertVerifiedCommercialProfile($site, $issues);

        $seo = $this->seoAuditor->audit($site);
        foreach ($seo['issues'] as $issue) {
            $this->issue($issues, 'SEO_'.$issue['code'], $issue['message'], $issue['path'] ?? null);
        }

        return [
            'site' => ['key' => $site->key, 'domain' => $site->domain, 'countryCode' => $site->country_code],
            'passed' => $issues === [],
            'summary' => ['blockingIssues' => count($issues), 'seoAuditPassed' => $seo['passed']],
            'issues' => $issues,
            'externalEvidenceStillRequired' => [
                'successful local-inbox test lead handled by an operator',
                'staging DNS/TLS and external crawl',
                'separate Analytics, Search Console and Yandex Webmaster verification',
                'approved legacy redirect cutover and 14-day post-launch observation',
            ],
        ];
    }

    /** @param list<array<string, string|null>> $issues */
    private function issue(array &$issues, string $code, string $message, ?string $path = null): void
    {
        $issues[] = ['code' => $code, 'message' => $message, 'path' => $path];
    }

    /** @param list<array<string, string|null>> $issues */
    private function assertVerifiedCommercialProfile(Site $site, array &$issues): void
    {
        $locale = $site->default_locale;
        $factKeys = SiteCommercialFact::query()
            ->where('site_id', $site->id)
            ->where('locale', $locale)
            ->published()
            ->whereNotNull('verified_at')
            ->whereNotNull('verified_by')
            ->pluck('key')
            ->all();
        $contactTypes = SiteContact::query()
            ->where('site_id', $site->id)
            ->where('locale', $locale)
            ->published()
            ->whereNotNull('verified_at')
            ->whereNotNull('verified_by')
            ->pluck('type')
            ->all();

        $missingFacts = array_values(array_diff(SiteCommercialFact::KEYS, $factKeys));
        $requiredContacts = ['legal_entity', 'address', 'phone', 'email', 'working_hours'];
        $missingContacts = array_values(array_diff($requiredContacts, $contactTypes));

        if ($missingFacts !== [] || $missingContacts !== []) {
            $details = [];
            if ($missingFacts !== []) {
                $details[] = 'facts: '.implode(', ', $missingFacts);
            }
            if ($missingContacts !== []) {
                $details[] = 'contacts: '.implode(', ', $missingContacts);
            }
            $this->issue(
                $issues,
                'COMMERCIAL_PROFILE_INCOMPLETE',
                'The country commercial profile needs published, verified local records ('.implode('; ', $details).').',
            );
        }
    }
}
