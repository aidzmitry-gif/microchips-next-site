<?php

namespace App\Console\Commands;

use App\Domain\Launch\SiteLaunchPreflight;
use App\Models\Site;
use Illuminate\Console\Command;

class LaunchPreflight extends Command
{
    protected $signature = 'site:launch-preflight {site : Site key or configured domain} {--json : Emit a read-only JSON report}';

    protected $description = 'List configured launch blockers for one country site without changing data';

    public function handle(SiteLaunchPreflight $preflight): int
    {
        $identifier = (string) $this->argument('site');
        $site = Site::query()->where('key', $identifier)->orWhere('domain', $identifier)->first();
        if ($site === null) {
            $this->error("Site [{$identifier}] was not found. The preflight did not change any data.");

            return self::INVALID;
        }
        $report = $preflight->inspect($site);
        if ($this->option('json')) {
            $this->line((string) json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
        } elseif ($report['passed']) {
            $this->info("PASS: configured preflight passed for {$site->key}; external launch evidence is still required.");
        } else {
            $this->error("BLOCKED: {$report['summary']['blockingIssues']} configured blocker(s) found for {$site->key}.");
            $this->table(['Code', 'Path', 'Message'], array_map(fn (array $issue) => [$issue['code'], $issue['path'] ?? '-', $issue['message']], $report['issues']));
        }

        return $report['passed'] ? self::SUCCESS : self::FAILURE;
    }
}
