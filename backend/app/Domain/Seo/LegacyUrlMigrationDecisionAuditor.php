<?php

namespace App\Domain\Seo;

/**
 * Read-only regression gate for approved legacy URL migration decisions.
 *
 * The input is deliberately an array/CSV-row contract instead of a database
 * model: the source registry stays auditable and can be prepared before any
 * legacy URL is imported into the new platform.
 */
final class LegacyUrlMigrationDecisionAuditor
{
    /**
     * @param  iterable<int, array<string, mixed>>  $rows
     * @return array{
     *     siteDomain: string,
     *     passed: bool,
     *     summary: array{checkedRows: int, priorityRows: int, blockingIssues: int, warnings: int},
     *     issues: list<array{severity: 'blocker'|'warning', code: string, message: string, row: int, legacyUrl: ?string, context: array<string, mixed>}>
     * }
     */
    public function audit(string $siteDomain, iterable $rows): array
    {
        $siteDomain = $this->normalizeDomain($siteDomain);
        $issues = [];
        $redirects = [];
        $checkedRows = 0;
        $priorityRows = 0;

        foreach ($rows as $index => $row) {
            $checkedRows++;
            $rowNumber = is_int($index) ? $index + 1 : $checkedRows;
            $row = is_array($row) ? $row : [];
            $legacyUrl = $this->stringValue($row['legacy_url'] ?? null);
            $priority = $this->booleanValue($row['priority'] ?? false);
            $priorityRows += $priority ? 1 : 0;
            $source = $this->sitePath($legacyUrl, $siteDomain);
            $decision = strtolower($this->stringValue($row['decision'] ?? null) ?? '');
            $reviewStatus = strtolower($this->stringValue($row['review_status'] ?? null) ?? '');
            $destinationUrl = $this->stringValue($row['destination_url'] ?? null);
            $canonicalUrl = $this->stringValue($row['canonical_url'] ?? null);
            $expectedStatus = $this->statusCode($row['expected_status'] ?? null);

            if (! in_array($decision, ['keep', 'fix', 'redirect', 'remove'], true)) {
                $this->issue(
                    $issues,
                    'blocker',
                    'LEGACY_DECISION_INVALID',
                    'Each legacy URL must have a keep, fix, redirect, or remove decision.',
                    $rowNumber,
                    $legacyUrl,
                    ['decision' => $decision],
                );
            }

            if (! in_array($reviewStatus, ['approved', 'needs_review', 'blocked'], true)) {
                $this->issue(
                    $issues,
                    $priority ? 'blocker' : 'warning',
                    'LEGACY_REVIEW_STATUS_INVALID',
                    'Review status must be approved, needs_review, or blocked.',
                    $rowNumber,
                    $legacyUrl,
                    ['reviewStatus' => $reviewStatus, 'priority' => $priority],
                );
            } elseif ($priority && $reviewStatus !== 'approved') {
                $this->issue(
                    $issues,
                    'blocker',
                    'LEGACY_PRIORITY_DECISION_NOT_APPROVED',
                    'A priority legacy URL cannot be released until its migration decision is approved.',
                    $rowNumber,
                    $legacyUrl,
                    ['reviewStatus' => $reviewStatus],
                );
            } elseif (! $priority && $reviewStatus !== 'approved') {
                $this->issue(
                    $issues,
                    'warning',
                    'LEGACY_NON_PRIORITY_DECISION_NOT_APPROVED',
                    'A non-priority URL still needs a recorded migration review before it can be promoted to priority.',
                    $rowNumber,
                    $legacyUrl,
                    ['reviewStatus' => $reviewStatus],
                );
            }

            if ($source['path'] === null) {
                $this->issue(
                    $issues,
                    'blocker',
                    'LEGACY_URL_INVALID',
                    'Legacy URL must be a normalized path or an absolute URL on the current site domain.',
                    $rowNumber,
                    $legacyUrl,
                    ['reason' => $source['reason']],
                );

                continue;
            }

            $destination = $this->sitePath($destinationUrl, $siteDomain);
            if ($destinationUrl !== null && $destination['path'] === null) {
                $this->issue(
                    $issues,
                    'blocker',
                    $destination['reason'] === 'foreign_host'
                        ? 'LEGACY_DESTINATION_CROSS_SITE'
                        : 'LEGACY_DESTINATION_UNSAFE',
                    $destination['reason'] === 'foreign_host'
                        ? 'Destination URL must stay on the current site; external, cross-site, and cross-country targets are not allowed.'
                        : 'Destination URL must be a normalized local path or an absolute URL on the current site domain.',
                    $rowNumber,
                    $legacyUrl,
                    ['destinationUrl' => $destinationUrl, 'reason' => $destination['reason']],
                );
            }

            $canonical = $this->sitePath($canonicalUrl, $siteDomain);
            if ($canonicalUrl !== null && $canonical['path'] === null) {
                $this->issue(
                    $issues,
                    'blocker',
                    $canonical['reason'] === 'foreign_host'
                        ? 'LEGACY_CANONICAL_CROSS_COUNTRY'
                        : 'LEGACY_CANONICAL_UNSAFE',
                    $canonical['reason'] === 'foreign_host'
                        ? 'Canonical URL must stay on the current site; cross-country canonicals are not allowed.'
                        : 'Canonical URL must be a normalized local path or an absolute URL on the current site domain.',
                    $rowNumber,
                    $legacyUrl,
                    ['canonicalUrl' => $canonicalUrl, 'reason' => $canonical['reason']],
                );
            }

            if ($this->statusValueIsInvalid($expectedStatus)) {
                $this->issue(
                    $issues,
                    'blocker',
                    'LEGACY_EXPECTED_STATUS_INVALID',
                    'Expected status must be a valid integer HTTP status when it is supplied.',
                    $rowNumber,
                    $legacyUrl,
                    ['expectedStatus' => $row['expected_status'] ?? null],
                );
            }

            $status = is_int($expectedStatus) ? $expectedStatus : null;
            $finalPath = $destination['path'] ?? ($decision === 'keep' ? $source['path'] : null);

            if (in_array($decision, ['fix', 'redirect'], true) && $destinationUrl === null) {
                $this->issue(
                    $issues,
                    'blocker',
                    'LEGACY_DESTINATION_REQUIRED',
                    'Fix and redirect decisions require an explicit destination URL.',
                    $rowNumber,
                    $legacyUrl,
                    ['decision' => $decision],
                );
            }

            if (in_array($decision, ['keep', 'fix'], true) && $status !== null && $status !== 200) {
                $this->issue(
                    $issues,
                    'blocker',
                    'LEGACY_INDEXABLE_DECISION_NOT_200',
                    'Keep and fix decisions must resolve with HTTP 200 when an expected status is recorded.',
                    $rowNumber,
                    $legacyUrl,
                    ['decision' => $decision, 'expectedStatus' => $status],
                );
            }

            if ($decision === 'remove') {
                if ($destinationUrl !== null) {
                    $this->issue(
                        $issues,
                        'blocker',
                        'LEGACY_REMOVE_HAS_DESTINATION',
                        'Remove decisions cannot contain a destination URL; use redirect when a replacement exists.',
                        $rowNumber,
                        $legacyUrl,
                    );
                }

                if ($canonicalUrl !== null) {
                    $this->issue(
                        $issues,
                        'blocker',
                        'LEGACY_REMOVE_HAS_CANONICAL',
                        'Remove decisions cannot emit a canonical URL.',
                        $rowNumber,
                        $legacyUrl,
                    );
                }

                if ($status === 200) {
                    $this->issue(
                        $issues,
                        'blocker',
                        'LEGACY_REMOVE_RETURNS_200',
                        'Remove decisions must never return HTTP 200; use an intentional 404 or 410 response.',
                        $rowNumber,
                        $legacyUrl,
                        ['expectedStatus' => $status],
                    );
                } elseif ($status !== null && ! in_array($status, [404, 410], true)) {
                    $this->issue(
                        $issues,
                        'blocker',
                        'LEGACY_REMOVE_INVALID_STATUS',
                        'Remove decisions may only use HTTP 404 or 410 when an expected status is recorded.',
                        $rowNumber,
                        $legacyUrl,
                        ['expectedStatus' => $status],
                    );
                }
            }

            if ($decision === 'redirect') {
                if ($status !== null && ! in_array($status, [301, 308], true)) {
                    $this->issue(
                        $issues,
                        'blocker',
                        'LEGACY_REDIRECT_NOT_PERMANENT',
                        'Redirect decisions must use a permanent 301 or 308 status when an expected status is recorded.',
                        $rowNumber,
                        $legacyUrl,
                        ['expectedStatus' => $status],
                    );
                }

                if ($destination['path'] === '/') {
                    $this->issue(
                        $issues,
                        'blocker',
                        'LEGACY_REDIRECT_TO_HOME',
                        'Redirect decisions cannot use the home page as a fallback target.',
                        $rowNumber,
                        $legacyUrl,
                    );
                }

                if ($canonicalUrl !== null) {
                    $this->issue(
                        $issues,
                        'blocker',
                        'LEGACY_REDIRECT_HAS_CANONICAL',
                        'Redirect sources cannot emit a canonical URL.',
                        $rowNumber,
                        $legacyUrl,
                    );
                }

                if ($destination['path'] !== null) {
                    $redirects[] = [
                        'source' => $source['path'],
                        'target' => $destination['path'],
                        'row' => $rowNumber,
                        'legacyUrl' => $legacyUrl,
                    ];
                }
            }

            if (in_array($decision, ['keep', 'fix'], true) && $canonical['path'] !== null && $canonical['path'] !== $finalPath) {
                $this->issue(
                    $issues,
                    'blocker',
                    'LEGACY_CANONICAL_NOT_SELF',
                    'Keep and fix decisions must use the final URL as their self-referencing canonical.',
                    $rowNumber,
                    $legacyUrl,
                    ['canonicalPath' => $canonical['path'], 'finalPath' => $finalPath],
                );
            }
        }

        $redirectSources = [];
        foreach ($redirects as $redirect) {
            if (isset($redirectSources[$redirect['source']])) {
                $this->issue(
                    $issues,
                    'blocker',
                    'LEGACY_REDIRECT_DUPLICATE_SOURCE',
                    'A legacy redirect source must have exactly one final destination.',
                    $redirect['row'],
                    $redirect['legacyUrl'],
                    ['sourcePath' => $redirect['source']],
                );
            }

            $redirectSources[$redirect['source']] = true;
        }

        foreach ($redirects as $redirect) {
            if (isset($redirectSources[$redirect['target']])) {
                $this->issue(
                    $issues,
                    'blocker',
                    'LEGACY_REDIRECT_CHAIN',
                    'Redirect destination is another legacy redirect source; map directly to the final URL.',
                    $redirect['row'],
                    $redirect['legacyUrl'],
                    ['sourcePath' => $redirect['source'], 'targetPath' => $redirect['target']],
                );
            }
        }

        $blockers = count(array_filter($issues, fn (array $issue) => $issue['severity'] === 'blocker'));
        $warnings = count($issues) - $blockers;

        return [
            'siteDomain' => $siteDomain,
            'passed' => $blockers === 0,
            'summary' => [
                'checkedRows' => $checkedRows,
                'priorityRows' => $priorityRows,
                'blockingIssues' => $blockers,
                'warnings' => $warnings,
            ],
            'issues' => $issues,
        ];
    }

    /** @return array{path: ?string, reason: ?string} */
    private function sitePath(?string $url, string $siteDomain): array
    {
        if ($url === null || $url === '') {
            return ['path' => null, 'reason' => 'missing'];
        }

        if (str_starts_with($url, '/')) {
            if (str_starts_with($url, '//')) {
                return ['path' => null, 'reason' => 'authority'];
            }

            return $this->normalizedPath($url);
        }

        $parts = parse_url($url);
        if ($parts === false || ! isset($parts['scheme'], $parts['host']) || ! in_array(strtolower($parts['scheme']), ['http', 'https'], true)) {
            return ['path' => null, 'reason' => 'invalid_url'];
        }

        if (isset($parts['user'], $parts['pass']) || isset($parts['query']) || isset($parts['fragment'])) {
            return ['path' => null, 'reason' => 'unsafe_url'];
        }

        if ($this->normalizeDomain($parts['host']) !== $siteDomain) {
            return ['path' => null, 'reason' => 'foreign_host'];
        }

        return $this->normalizedPath($parts['path'] ?? '/');
    }

    /** @return array{path: ?string, reason: ?string} */
    private function normalizedPath(string $path): array
    {
        if (! str_starts_with($path, '/') || str_starts_with($path, '//') || str_contains($path, '\\')) {
            return ['path' => null, 'reason' => 'invalid_path'];
        }

        $parts = parse_url($path);
        if ($parts === false || isset($parts['scheme'], $parts['host'], $parts['port'], $parts['user'], $parts['pass'], $parts['query'], $parts['fragment'])) {
            return ['path' => null, 'reason' => 'unsafe_path'];
        }

        $normalized = '/'.ltrim((string) ($parts['path'] ?? '/'), '/');
        $normalized = preg_replace('#/+#', '/', $normalized) ?? '/';
        $normalized = $normalized === '/' ? $normalized : rtrim($normalized, '/');

        return $normalized === $path
            ? ['path' => $normalized, 'reason' => null]
            : ['path' => null, 'reason' => 'not_normalized'];
    }

    private function normalizeDomain(string $domain): string
    {
        $domain = strtolower(trim($domain));
        $domain = preg_replace('#^https?://#', '', $domain) ?? $domain;
        $domain = explode('/', $domain)[0];
        $domain = explode(':', $domain)[0];

        return str_starts_with($domain, 'www.') ? substr($domain, 4) : $domain;
    }

    private function stringValue(mixed $value): ?string
    {
        if (! is_string($value) && ! is_numeric($value)) {
            return null;
        }

        $value = trim((string) $value);

        return $value === '' ? null : $value;
    }

    private function booleanValue(mixed $value): bool
    {
        return filter_var($value, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE) ?? false;
    }

    /** @return int|'invalid'|null */
    private function statusCode(mixed $value): int|string|null
    {
        if ($value === null || $value === '') {
            return null;
        }

        if (is_int($value) || (is_string($value) && ctype_digit($value))) {
            $status = (int) $value;

            return $status >= 100 && $status <= 599 ? $status : 'invalid';
        }

        return 'invalid';
    }

    /** @param int|'invalid'|null $status */
    private function statusValueIsInvalid(int|string|null $status): bool
    {
        return $status === 'invalid';
    }

    /**
     * @param  list<array{severity: 'blocker'|'warning', code: string, message: string, row: int, legacyUrl: ?string, context: array<string, mixed>}>  $issues
     * @param  'blocker'|'warning'  $severity
     * @param  array<string, mixed>  $context
     */
    private function issue(
        array &$issues,
        string $severity,
        string $code,
        string $message,
        int $row,
        ?string $legacyUrl,
        array $context = [],
    ): void {
        $issues[] = [
            'severity' => $severity,
            'code' => $code,
            'message' => $message,
            'row' => $row,
            'legacyUrl' => $legacyUrl,
            'context' => $context,
        ];
    }
}
