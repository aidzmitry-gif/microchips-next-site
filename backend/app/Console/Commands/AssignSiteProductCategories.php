<?php

namespace App\Console\Commands;

use App\Domain\Imports\SiteProductCategoryAssigner;
use App\Models\ImportRun;
use App\Models\Site;
use Illuminate\Console\Command;
use Throwable;

class AssignSiteProductCategories extends Command
{
    protected $signature = 'catalog:assign-site-product-categories
                            {site : Site key whose staged products receive category assignments}
                            {file : Absolute or project-relative path to the assignment CSV}
                            {--delimiter=, : Single-character CSV delimiter}
                            {--category-source=bitrix_sections : Source namespace of the already-imported site category tree}
                            {--apply : Persist changes; without this option the transaction is rolled back}';

    protected $description = 'Assign already-staged site products to an already-imported site category tree (dry-run by default). Never publishes products and never creates categories or products.';

    public function __construct(private readonly SiteProductCategoryAssigner $assigner)
    {
        parent::__construct();
    }

    public function handle(): int
    {
        $file = (string) $this->argument('file');
        $siteKey = trim((string) $this->argument('site'));
        $delimiter = (string) $this->option('delimiter');
        $categorySource = trim((string) $this->option('category-source'));
        $apply = (bool) $this->option('apply');

        if (! is_file($file)) {
            $this->error('CSV file was not found.');

            return self::FAILURE;
        }
        if (mb_strlen($delimiter) !== 1 || $categorySource === '' || mb_strlen($categorySource) > 255) {
            $this->error('Delimiter must be one character and category-source must be 1-255 characters.');

            return self::FAILURE;
        }

        $site = Site::query()->where('key', $siteKey)->first();
        if ($site === null) {
            $this->error("Site was not found: {$siteKey}.");

            return self::FAILURE;
        }

        $run = ImportRun::create([
            'source' => 'site_product_category_assignment_csv',
            'source_file' => basename($file),
            'status' => 'running',
            'started_at' => now(),
        ]);

        try {
            $summary = $this->assigner->assign($site, $file, $delimiter, $categorySource, $apply);
            $hasErrors = $summary['validation_error_count'] > 0;
            // processed_records reflects what was actually PERSISTED. A dry run never
            // persists anything (the transaction is rolled back), so it must stay 0
            // even when validation passed -- otherwise a reader could mistake a
            // dry-run summary for an applied one. accepted_records is what a
            // subsequent --apply run would persist.
            $run->update([
                'status' => $hasErrors ? 'needs_review' : ($apply ? 'completed' : 'dry_run_complete'),
                'total_records' => $summary['csv_records'],
                'processed_records' => ($hasErrors || ! $apply) ? 0 : $summary['accepted_records'],
                'failed_records' => $summary['validation_error_count'],
                'summary' => $summary,
                'finished_at' => now(),
            ]);

            if ($hasErrors) {
                $this->error("Import run {$run->id} blocked by {$summary['validation_error_count']} validation error(s).");

                return self::FAILURE;
            }

            $verb = $apply ? 'applied' : 'validated in dry-run';
            $this->info("Import run {$run->id} {$verb}: {$summary['assignments_created']} new assignment(s), {$summary['assignments_unchanged']} unchanged, {$summary['chemistry_attributes_set']} chemistry attribute(s) set.");
            $this->warn('Chemistry attributes are written to the shared products table (canonical, cross-site) -- not to a site-scoped table. See summary.canonical_write_note.');

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
