<?php

namespace Tests\Feature;

use App\Domain\Seo\LegacyUrlMigrationDecisionAuditor;
use Tests\TestCase;

class LegacyUrlMigrationDecisionAuditorTest extends TestCase
{
    public function test_an_approved_single_hop_migration_manifest_passes(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/ups-battery-42', 'keep', 'approved', null, 200, '/catalog/ups-battery-42', true),
            $this->row('/catalog/old-battery', 'redirect', 'approved', '/catalog/new-battery', 301, null, true),
            $this->row('/catalog/discontinued', 'remove', 'approved', null, 410, null, true),
        ]);

        $this->assertTrue($report['passed']);
        $this->assertSame(0, $report['summary']['blockingIssues']);
        $this->assertSame(3, $report['summary']['priorityRows']);
    }

    public function test_priority_unreviewed_or_blocked_decisions_block_release(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/unreviewed', 'keep', 'needs_review', null, 200, null, true),
            $this->row('/catalog/blocked', 'remove', 'blocked', null, 410, null, true),
            $this->row('/catalog/non-priority', 'keep', 'needs_review', null, 200, null, false),
        ]);

        $this->assertFalse($report['passed']);
        $this->assertSame(2, $report['summary']['blockingIssues']);
        $this->assertSame(1, $report['summary']['warnings']);
        $this->assertSame(
            ['LEGACY_PRIORITY_DECISION_NOT_APPROVED', 'LEGACY_PRIORITY_DECISION_NOT_APPROVED', 'LEGACY_NON_PRIORITY_DECISION_NOT_APPROVED'],
            $this->issueCodes($report),
        );
    }

    public function test_redirect_chains_homepage_and_cross_site_targets_block_release(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/old', 'redirect', 'approved', '/catalog/middle', 301, null, true),
            $this->row('/catalog/middle', 'redirect', 'approved', '/catalog/new', 308, null, true),
            $this->row('/catalog/fallback', 'redirect', 'approved', '/', 301, null, true),
            $this->row('/catalog/foreign', 'redirect', 'approved', 'https://microchips.ru/catalog/new', 301, null, true),
        ]);

        $this->assertFalse($report['passed']);
        $this->assertContains('LEGACY_REDIRECT_CHAIN', $this->issueCodes($report));
        $this->assertContains('LEGACY_REDIRECT_TO_HOME', $this->issueCodes($report));
        $this->assertContains('LEGACY_DESTINATION_CROSS_SITE', $this->issueCodes($report));
    }

    public function test_remove_with_200_and_cross_country_canonical_block_release(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/discontinued', 'remove', 'approved', null, 200, null, true),
            $this->row('/catalog/new-battery', 'fix', 'approved', '/catalog/new-battery', 200, 'https://microchips.ru/catalog/new-battery', true),
        ]);

        $this->assertFalse($report['passed']);
        $this->assertContains('LEGACY_REMOVE_RETURNS_200', $this->issueCodes($report));
        $this->assertContains('LEGACY_CANONICAL_CROSS_COUNTRY', $this->issueCodes($report));
    }

    /** @return array<string, mixed> */
    private function row(
        string $legacyUrl,
        string $decision,
        string $reviewStatus,
        ?string $destinationUrl,
        ?int $expectedStatus,
        ?string $canonicalUrl,
        bool $priority,
    ): array {
        return [
            'legacy_url' => $legacyUrl,
            'decision' => $decision,
            'review_status' => $reviewStatus,
            'destination_url' => $destinationUrl,
            'expected_status' => $expectedStatus,
            'canonical_url' => $canonicalUrl,
            'priority' => $priority,
        ];
    }

    /** @param array{issues: list<array{code: string}>} $report
     * @return list<string>
     */
    private function issueCodes(array $report): array
    {
        return array_map(fn (array $issue) => $issue['code'], $report['issues']);
    }
}
