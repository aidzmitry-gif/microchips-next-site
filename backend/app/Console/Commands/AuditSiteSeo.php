<?php

namespace App\Console\Commands;

use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Models\Site;
use Illuminate\Console\Command;

class AuditSiteSeo extends Command
{
    protected $signature = 'seo:audit
                            {site : Site key or configured domain}
                            {--json : Emit the read-only audit report as JSON}';

    protected $description = 'Run read-only release-blocking SEO validation for one site profile';

    public function handle(SiteSeoReleaseAuditor $auditor): int
    {
        $identifier = (string) $this->argument('site');
        $site = Site::query()
            ->where('key', $identifier)
            ->orWhere('domain', $identifier)
            ->first();

        if ($site === null) {
            $this->error("Site [{$identifier}] was not found. The audit did not change any data.");

            return self::INVALID;
        }

        $report = $auditor->audit($site);

        if ($this->option('json')) {
            $this->line((string) json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));
        } elseif ($report['passed']) {
            $this->info("PASS: SEO release audit passed for {$site->key} ({$site->domain}).");
            $this->line("Checked {$report['summary']['checkedUrls']} URL(s), {$report['summary']['checkedRedirects']} redirect(s), and {$report['summary']['checkedHreflangAlternates']} hreflang alternate(s).");
        } else {
            $this->error("BLOCKED: {$report['summary']['blockingIssues']} release blocker(s) found for {$site->key}.");
            $this->table(
                ['Code', 'Path', 'Message'],
                array_map(
                    fn (array $issue) => [$issue['code'], $issue['path'] ?? '-', $issue['message']],
                    $report['issues'],
                ),
            );
        }

        return $report['passed'] ? self::SUCCESS : self::FAILURE;
    }
}
