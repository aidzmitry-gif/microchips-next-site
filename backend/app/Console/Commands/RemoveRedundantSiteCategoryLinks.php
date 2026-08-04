<?php

namespace App\Console\Commands;

use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteCategoryProduct;
use App\Models\SiteProduct;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/** Remove an exact redundant category link while preserving a canonical link. */
class RemoveRedundantSiteCategoryLinks extends Command
{
    protected $signature = 'catalog:remove-redundant-category-links
                            {site : Site key}
                            {file : CSV with product_external_id and category_external_id}
                            {--category-source=full_catalog_seo_tree : Source namespace of links being removed}
                            {--apply : Persist removals; otherwise roll back}';

    protected $description = 'Remove exact redundant category links only when every product keeps another category';

    public function handle(): int
    {
        $site = Site::query()->where('key', trim((string) $this->argument('site')))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }
        $apply = (bool) $this->option('apply');
        $run = ImportRun::create([
            'source' => 'remove_redundant_site_category_links',
            'source_file' => basename((string) $this->argument('file')),
            'status' => 'running',
            'started_at' => now(),
        ]);

        try {
            $rows = $this->rows((string) $this->argument('file'));
            $source = trim((string) $this->option('category-source'));
            if ($source === '') {
                throw new RuntimeException('Category source is required.');
            }
            $removed = 0;
            $work = function () use ($site, $rows, $source, &$removed): void {
                foreach ($rows as $row) {
                    $product = Product::query()->where('external_id', $row['product_external_id'])->first();
                    $siteProduct = $product === null ? null : SiteProduct::query()
                        ->where('site_id', $site->id)->where('product_id', $product->id)->first();
                    $category = SiteCategory::query()
                        ->where('site_id', $site->id)
                        ->where('source', $source)
                        ->where('external_id', $row['category_external_id'])
                        ->first();
                    if ($siteProduct === null || $category === null) {
                        throw new RuntimeException("Unknown product/category pair: {$row['product_external_id']} / {$row['category_external_id']}.");
                    }
                    $link = SiteCategoryProduct::query()
                        ->where('site_id', $site->id)
                        ->where('site_product_id', $siteProduct->id)
                        ->where('site_category_id', $category->id)
                        ->first();
                    if ($link === null) {
                        throw new RuntimeException("Redundant category link is missing for {$row['product_external_id']}.");
                    }
                    $remaining = SiteCategoryProduct::query()
                        ->where('site_id', $site->id)
                        ->where('site_product_id', $siteProduct->id)
                        ->where('id', '!=', $link->id)
                        ->count();
                    if ($remaining < 1) {
                        throw new RuntimeException("Removal would leave {$row['product_external_id']} without a category.");
                    }
                    $link->delete();
                    $removed++;
                }
            };
            if ($apply) {
                DB::transaction($work);
            } else {
                DB::beginTransaction();
                try {
                    $work();
                } finally {
                    DB::rollBack();
                }
            }
            $summary = [
                'mode' => $apply ? 'apply' : 'dry_run',
                'site_key' => $site->key,
                'records' => count($rows),
                'links_removed' => $removed,
                'products_deleted' => 0,
                'publication_flags_changed' => 0,
                'products_left_without_category' => 0,
            ];
            $run->update([
                'status' => $apply ? 'completed' : 'dry_run_complete',
                'total_records' => count($rows),
                'processed_records' => $apply ? $removed : 0,
                'summary' => $summary,
                'finished_at' => now(),
            ]);
            $this->info(sprintf('%s %d redundant category link(s); every product retained another category.', $apply ? 'Removed' : 'Validated', $removed));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $run->update(['status' => 'failed', 'summary' => ['error' => $error->getMessage()], 'finished_at' => now()]);
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /** @return list<array{product_external_id: string, category_external_id: string}> */
    private function rows(string $file): array
    {
        $handle = is_readable($file) ? fopen($file, 'rb') : false;
        if ($handle === false) {
            throw new RuntimeException('CSV is not readable.');
        }
        try {
            $header = fgetcsv($handle, 0, ',', '"', '');
            if ($header === false) {
                throw new RuntimeException('CSV has no header.');
            }
            $header = array_map(static fn ($value): string => mb_strtolower(ltrim(trim((string) $value), "\xEF\xBB\xBF")), $header);
            if ($header !== ['product_external_id', 'category_external_id']) {
                throw new RuntimeException('CSV headers must be exactly product_external_id,category_external_id.');
            }
            $rows = [];
            $seen = [];
            while (($raw = fgetcsv($handle, 0, ',', '"', '')) !== false) {
                if (count($raw) !== 2) {
                    throw new RuntimeException('CSV row must contain exactly two fields.');
                }
                $productExternalId = trim((string) $raw[0]);
                $categoryExternalId = trim((string) $raw[1]);
                $key = $productExternalId."\0".$categoryExternalId;
                if ($productExternalId === '' || $categoryExternalId === '' || isset($seen[$key])) {
                    throw new RuntimeException('CSV contains an empty or duplicate product/category pair.');
                }
                $seen[$key] = true;
                $rows[] = [
                    'product_external_id' => $productExternalId,
                    'category_external_id' => $categoryExternalId,
                ];
            }
            if ($rows === []) {
                throw new RuntimeException('CSV has no data rows.');
            }

            return $rows;
        } finally {
            fclose($handle);
        }
    }
}
