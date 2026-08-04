<?php

namespace App\Console\Commands;

use App\Domain\Imports\SiteProductCategoryMover;
use App\Models\ImportRun;
use App\Models\Site;
use Illuminate\Console\Command;
use Throwable;

class MoveSiteProductCategories extends Command
{
    protected $signature = 'catalog:move-site-product-categories
                            {site : Site key whose category assignments are corrected}
                            {file : CSV with product, source category and target category IDs}
                            {--delimiter=, : Single-character CSV delimiter}
                            {--category-source=bitrix_sections : Category source namespace}
                            {--apply : Persist changes; without this option the transaction is rolled back}';

    protected $description = 'Atomically move exact site products between existing site categories (dry-run by default)';

    public function __construct(private readonly SiteProductCategoryMover $mover)
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
            'source' => 'site_product_category_move_csv',
            'source_file' => basename($file),
            'status' => 'running',
            'started_at' => now(),
        ]);

        try {
            $summary = $this->mover->move($site, $file, $delimiter, $categorySource, $apply);
            $hasErrors = $summary['validation_error_count'] > 0;
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
            $this->info("Import run {$run->id} {$verb}: {$summary['moves_completed']} move(s), {$summary['already_moved']} already moved.");

            return self::SUCCESS;
        } catch (Throwable $error) {
            $run->update([
                'status' => 'failed',
                'summary' => ['mode' => $apply ? 'apply' : 'dry_run', 'site_key' => $siteKey, 'error' => $error->getMessage()],
                'finished_at' => now(),
            ]);
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }
}
