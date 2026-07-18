<?php

namespace Tests\Feature;

use App\Domain\Seo\LegacyUrlMigrationDecisionAuditor;
use Tests\TestCase;

/**
 * Fills the remaining decision/status/path-safety branches in
 * LegacyUrlMigrationDecisionAuditor that LegacyUrlMigrationDecisionAuditorTest
 * and AuditorErrorBranchesTest do not exercise: invalid review status
 * severity split, non-foreign-host destination/canonical rejection reasons,
 * expected-status parsing edge cases, the fix/redirect destination
 * requirement, the keep/fix 200 rule, remove's canonical/status rules, the
 * non-array-row and non-sequential-index defensive branches, and site domain
 * normalization.
 */
class LegacyAuditorCoverageTest extends TestCase
{
    public function test_invalid_review_status_is_a_warning_for_non_priority_and_a_blocker_for_priority(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/a', 'keep', 'pending', null, null, null, false),
            $this->row('/catalog/b', 'keep', 'pending', null, null, null, true),
        ]);

        $issues = $this->issuesOfCode($report, 'LEGACY_REVIEW_STATUS_INVALID');
        $this->assertCount(2, $issues);
        $this->assertSame('warning', $issues[0]['severity']);
        $this->assertSame(1, $issues[0]['row']);
        $this->assertSame('blocker', $issues[1]['severity']);
        $this->assertSame(2, $issues[1]['row']);
        $this->assertFalse($report['passed']);
    }

    public function test_destination_url_starting_with_double_slash_is_rejected_as_authority(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/old', 'fix', 'approved', '//evil.example.com/catalog/new', null, null, true),
        ]);

        $issue = $this->issuesOfCode($report, 'LEGACY_DESTINATION_UNSAFE')[0] ?? null;
        $this->assertNotNull($issue);
        $this->assertSame('authority', $issue['context']['reason']);
    }

    public function test_destination_url_with_a_non_http_scheme_is_rejected_as_invalid_url(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/old', 'fix', 'approved', 'javascript:alert(1)', null, null, true),
        ]);

        $issue = $this->issuesOfCode($report, 'LEGACY_DESTINATION_UNSAFE')[0] ?? null;
        $this->assertNotNull($issue);
        $this->assertSame('invalid_url', $issue['context']['reason']);
    }

    public function test_destination_url_with_a_query_string_is_rejected_as_unsafe_url(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/old', 'fix', 'approved', 'https://microchips.by/catalog/new?utm=1', null, null, true),
        ]);

        $issue = $this->issuesOfCode($report, 'LEGACY_DESTINATION_UNSAFE')[0] ?? null;
        $this->assertNotNull($issue);
        $this->assertSame('unsafe_url', $issue['context']['reason']);
    }

    public function test_destination_path_with_an_internal_double_slash_is_rejected_as_not_normalized(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/old', 'fix', 'approved', '/catalog//new', null, null, true),
        ]);

        $issue = $this->issuesOfCode($report, 'LEGACY_DESTINATION_UNSAFE')[0] ?? null;
        $this->assertNotNull($issue);
        $this->assertSame('not_normalized', $issue['context']['reason']);
    }

    public function test_canonical_url_with_a_non_http_scheme_is_rejected_as_canonical_unsafe(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/keep-me', 'keep', 'approved', null, null, 'javascript:alert(1)', true),
        ]);

        $issue = $this->issuesOfCode($report, 'LEGACY_CANONICAL_UNSAFE')[0] ?? null;
        $this->assertNotNull($issue);
        $this->assertSame('invalid_url', $issue['context']['reason']);
    }

    public function test_expected_status_rejects_non_numeric_values_and_out_of_range_integers(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/a', 'keep', 'approved', null, 'abc', null, true),
            $this->row('/catalog/b', 'keep', 'approved', null, 700, null, true),
        ]);

        $issues = $this->issuesOfCode($report, 'LEGACY_EXPECTED_STATUS_INVALID');
        $this->assertCount(2, $issues);
        $this->assertSame('abc', $issues[0]['context']['expectedStatus']);
        $this->assertSame(700, $issues[1]['context']['expectedStatus']);
    }

    public function test_fix_and_redirect_decisions_require_a_destination_url(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/fix-me', 'fix', 'approved', null, null, null, true),
            $this->row('/catalog/redirect-me', 'redirect', 'approved', null, null, null, true),
        ]);

        $issues = $this->issuesOfCode($report, 'LEGACY_DESTINATION_REQUIRED');
        $this->assertCount(2, $issues);
        $this->assertSame('fix', $issues[0]['context']['decision']);
        $this->assertSame('redirect', $issues[1]['context']['decision']);
    }

    public function test_keep_and_fix_decisions_must_resolve_with_200_when_a_status_is_recorded(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/keep-404', 'keep', 'approved', null, 404, null, true),
            $this->row('/catalog/fix-500', 'fix', 'approved', '/catalog/fix-target', 500, null, true),
        ]);

        $issues = $this->issuesOfCode($report, 'LEGACY_INDEXABLE_DECISION_NOT_200');
        $this->assertCount(2, $issues);
        $this->assertSame(404, $issues[0]['context']['expectedStatus']);
        $this->assertSame(500, $issues[1]['context']['expectedStatus']);
    }

    public function test_remove_decision_cannot_emit_a_canonical_url(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/remove-me', 'remove', 'approved', null, 410, '/catalog/remove-me', true),
        ]);

        $this->assertContains('LEGACY_REMOVE_HAS_CANONICAL', $this->issueCodes($report));
    }

    public function test_remove_decision_status_must_be_404_or_410_when_recorded(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            $this->row('/catalog/remove-bad-status', 'remove', 'approved', null, 403, null, true),
            $this->row('/catalog/remove-404', 'remove', 'approved', null, 404, null, true),
            $this->row('/catalog/remove-410', 'remove', 'approved', null, 410, null, true),
        ]);

        $codes = $this->issueCodesForRow($report, 1);
        $this->assertSame(['LEGACY_REMOVE_INVALID_STATUS'], $codes);
        $this->assertSame([], $this->issueCodesForRow($report, 2));
        $this->assertSame([], $this->issueCodesForRow($report, 3));
    }

    public function test_a_row_that_is_not_an_array_is_treated_as_empty_and_still_reported(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            'this-is-not-a-row-array',
        ]);

        $this->assertFalse($report['passed']);
        $this->assertSame(1, $report['summary']['checkedRows']);
        $codes = $this->issueCodesForRow($report, 1);
        $this->assertContains('LEGACY_URL_INVALID', $codes);
        $this->assertContains('LEGACY_DECISION_INVALID', $codes);

        $missingUrlIssue = $this->issuesOfCode($report, 'LEGACY_URL_INVALID')[0];
        $this->assertSame('missing', $missingUrlIssue['context']['reason']);
        $this->assertNull($missingUrlIssue['legacyUrl']);
    }

    public function test_integer_indexes_number_rows_by_index_plus_one(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            4 => $this->row('/catalog/a', 'archive', 'approved', null, null, null, true),
            9 => $this->row('/catalog/b', 'archive', 'approved', null, null, null, true),
        ]);

        $rows = array_map(fn (array $issue) => $issue['row'], $report['issues']);
        $this->assertSame([5, 10], $rows);
    }

    public function test_non_integer_keys_fall_back_to_a_sequential_row_counter(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', [
            'x' => $this->row('/catalog/a', 'archive', 'approved', null, null, null, true),
            'y' => $this->row('/catalog/b', 'archive', 'approved', null, null, null, true),
        ]);

        $rows = array_map(fn (array $issue) => $issue['row'], $report['issues']);
        $this->assertSame([1, 2], $rows);
    }

    public function test_an_empty_row_set_passes_with_zeroed_summary(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('microchips.by', []);

        $this->assertTrue($report['passed']);
        $this->assertSame(
            ['checkedRows' => 0, 'priorityRows' => 0, 'blockingIssues' => 0, 'warnings' => 0],
            $report['summary'],
        );
        $this->assertSame([], $report['issues']);
    }

    public function test_site_domain_is_normalized_and_used_to_match_absolute_legacy_urls(): void
    {
        $report = app(LegacyUrlMigrationDecisionAuditor::class)->audit('https://WWW.Microchips.BY:8080/ignored', [
            $this->row('https://microchips.by/catalog/example', 'keep', 'approved', null, 200, 'https://microchips.by/catalog/example', true),
        ]);

        $this->assertSame('microchips.by', $report['siteDomain']);
        $this->assertTrue($report['passed']);
        $this->assertSame(0, $report['summary']['blockingIssues']);
    }

    /** @return array<string, mixed> */
    private function row(
        mixed $legacyUrl,
        string $decision,
        string $reviewStatus,
        ?string $destinationUrl,
        mixed $expectedStatus,
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

    /** @param array{issues: list<array{code: string, row: int}>} $report
     * @return list<string>
     */
    private function issueCodesForRow(array $report, int $row): array
    {
        return array_values(array_map(
            fn (array $issue) => $issue['code'],
            array_filter($report['issues'], fn (array $issue) => $issue['row'] === $row),
        ));
    }

    /**
     * @param  array{issues: list<array{code: string, severity: string, row: int, legacyUrl: ?string, context: array<string, mixed>}>}  $report
     * @return list<array{code: string, severity: string, row: int, legacyUrl: ?string, context: array<string, mixed>}>
     */
    private function issuesOfCode(array $report, string $code): array
    {
        return array_values(array_filter($report['issues'], fn (array $issue) => $issue['code'] === $code));
    }
}
