<?php

namespace App\Console\Commands;

use App\Domain\Imports\SiteCategoryTaxonomyImporter;
use App\Models\ImportRun;
use App\Models\Site;
use Illuminate\Console\Command;
use Throwable;

class ImportSiteCategoryTaxonomy extends Command
{
    protected $signature = 'catalog:import-site-categories
                            {site : Site key receiving the category tree}
                            {file : Absolute or project-relative path to the category CSV}
                            {--delimiter=, : Single-character CSV delimiter}
                            {--source=bitrix_sections : Stable source namespace}
                            {--allow-missing-parent=* : External parent ID intentionally outside this CSV boundary}
                            {--apply : Persist changes; without this option the transaction is rolled back}';

    protected $description = 'Validate and idempotently import a site-scoped category tree (dry-run by default)';

    public function __construct(private readonly SiteCategoryTaxonomyImporter $importer)
    {
        parent::__construct();
    }

    public function handle(): int
    {
        $file = (string) $this->argument('file');
        $siteKey = trim((string) $this->argument('site'));
        $delimiter = (string) $this->option('delimiter');
        $source = trim((string) $this->option('source'));
        $apply = (bool) $this->option('apply');

        if (! is_file($file)) {
            $this->error('CSV file was not found.');

            return self::FAILURE;
        }
        if (mb_strlen($delimiter) !== 1 || $source === '' || mb_strlen($source) > 255) {
            $this->error('Delimiter must be one character and source must be 1-255 characters.');

            return self::FAILURE;
        }

        $site = Site::query()->where('key', $siteKey)->first();
        if ($site === null) {
            $this->error("Site was not found: {$siteKey}.");

            return self::FAILURE;
        }

        $run = ImportRun::create([
            'source' => 'site_category_taxonomy_csv',
            'source_file' => basename($file),
            'status' => 'running',
            'started_at' => now(),
        ]);

        try {
            $summary = $this->importer->import(
                $site,
                $file,
                $delimiter,
                $source,
                (array) $this->option('allow-missing-parent'),
                $apply,
            );
            $hasErrors = $summary['validation_error_count'] > 0;
            $run->update([
                'status' => $hasErrors ? 'needs_review' : ($apply ? 'completed' : 'dry_run_complete'),
                'total_records' => $summary['csv_records'],
                'processed_records' => $hasErrors ? 0 : $summary['accepted_records'],
                'failed_records' => $summary['validation_error_count'],
                'summary' => $summary,
                'finished_at' => now(),
            ]);

            if ($hasErrors) {
                $this->error("Import run {$run->id} blocked by {$summary['validation_error_count']} validation error(s).");

                return self::FAILURE;
            }

            $verb = $apply ? 'applied' : 'validated in dry-run';
            $this->info("Import run {$run->id} {$verb}: {$summary['accepted_records']} categories, {$summary['created']} create(s), {$summary['updated']} update(s), {$summary['unchanged']} unchanged.");

            return self::SUCCESS;
        } catch (Throwable $error) {
            $run->update([
                'status' => 'failed',
                'summary' => ['mode' => $apply ? 'apply' : 'dry_run', 'site_key' => $site->key, 'error' => $error->getMessage()],
                'finished_at' => now(),
            ]);
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }
}
