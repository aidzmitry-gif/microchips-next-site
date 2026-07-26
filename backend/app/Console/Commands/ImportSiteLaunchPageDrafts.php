<?php

namespace App\Console\Commands;

use App\Domain\Imports\SiteLaunchPageDraftImporter;
use App\Models\ImportRun;
use App\Models\Site;
use Illuminate\Console\Command;
use Throwable;

class ImportSiteLaunchPageDrafts extends Command
{
    protected $signature = 'site:import-launch-page-drafts
                            {site : Site key}
                            {file : JSON launch-page draft manifest}
                            {--apply : Persist drafts; otherwise transaction is rolled back}';

    protected $description = 'Validate and import unpublished, noindex regional page drafts';

    public function __construct(private readonly SiteLaunchPageDraftImporter $importer)
    {
        parent::__construct();
    }

    public function handle(): int
    {
        $site = Site::query()->where('key', $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }
        $apply = (bool) $this->option('apply');
        $run = ImportRun::create(['source' => 'site_launch_page_drafts', 'source_file' => basename((string) $this->argument('file')), 'status' => 'running', 'started_at' => now()]);
        try {
            $summary = $this->importer->import($site, (string) $this->argument('file'), $apply);
            $run->update(['status' => $apply ? 'completed' : 'dry_run_complete', 'total_records' => $summary['drafts'], 'processed_records' => $summary['drafts'], 'summary' => $summary, 'finished_at' => now()]);
            $this->info("Launch draft import {$run->id}: {$summary['drafts']} drafts, {$summary['created']} created, {$summary['updated']} updated, {$summary['unchanged']} unchanged.");

            return self::SUCCESS;
        } catch (Throwable $error) {
            $run->update(['status' => 'failed', 'summary' => ['mode' => $apply ? 'apply' : 'dry_run', 'error' => $error->getMessage()], 'finished_at' => now()]);
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }
}
