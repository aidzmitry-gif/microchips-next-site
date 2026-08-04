<?php

namespace App\Console\Commands;

use App\Domain\Imports\SiteCommercialProfileDraftImporter;
use App\Models\ImportRun;
use App\Models\Site;
use Illuminate\Console\Command;
use Throwable;

class ImportSiteCommercialProfileDrafts extends Command
{
    protected $signature = 'site:import-commercial-profile-drafts {site : Site key} {file : JSON commercial profile draft manifest} {--apply : Persist drafts; otherwise transaction is rolled back}';

    protected $description = 'Validate and import unpublished site-scoped commercial profile drafts';

    public function __construct(private readonly SiteCommercialProfileDraftImporter $importer)
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
        $run = ImportRun::create(['source' => 'site_commercial_profile_drafts', 'source_file' => basename((string) $this->argument('file')), 'status' => 'running', 'started_at' => now()]);
        try {
            $summary = $this->importer->import($site, (string) $this->argument('file'), $apply);
            $records = array_sum(array_map(static fn (string $key): int => (int) $summary[$key], ['contacts_created', 'contacts_updated', 'contacts_unchanged', 'facts_created', 'facts_updated', 'facts_unchanged']));
            $run->update(['status' => $apply ? 'completed' : 'dry_run_complete', 'total_records' => $records, 'processed_records' => $records, 'summary' => $summary, 'finished_at' => now()]);
            $this->info("Commercial profile import {$run->id}: {$records} records processed; the import never publishes or changes verification.");

            return self::SUCCESS;
        } catch (Throwable $error) {
            $run->update(['status' => 'failed', 'summary' => ['mode' => $apply ? 'apply' : 'dry_run', 'error' => $error->getMessage()], 'finished_at' => now()]);
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }
}
