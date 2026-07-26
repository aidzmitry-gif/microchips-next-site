<?php

namespace App\Console\Commands;

use App\Models\CatalogIdentityCandidate;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use RuntimeException;

class ReportRbApprovedProducts extends Command
{
    protected $signature = 'catalog:report-rb-approved-products
                            {site : Site key}
                            {manifest : CSV manifest generated from the Bitrix snapshot}
                            {output : JSON evidence report path}';

    protected $description = 'Create a read-only evidence report for products published from reviewed RB staging records.';

    public function handle(): int
    {
        $site = Site::query()->where('key', $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $manifest = $this->manifest((string) $this->argument('manifest'));
        } catch (RuntimeException $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $rows = [];
        $records = StagedImportRecord::query()
            ->where('status', 'published')
            ->where('published_site_id', $site->id)
            ->with('publishedProduct')
            ->orderBy('id')
            ->get();

        foreach ($records as $record) {
            $errors = [];
            $product = $record->publishedProduct;
            if ($product === null || $product->id !== $record->published_product_id || $product->external_id !== $record->external_id) {
                $errors[] = 'published_product_mismatch';
            }

            $siteProducts = $product === null ? collect() : SiteProduct::query()
                ->where('site_id', $site->id)->where('product_id', $product->id)->get();
            if ($siteProducts->count() !== 1) {
                $errors[] = 'site_product_not_unique';
            }
            $siteProduct = $siteProducts->first();

            $candidates = CatalogIdentityCandidate::query()
                ->where('review_status', 'approved_for_staging')
                ->whereHas('oneCItem', fn ($query) => $query->where('external_id', $record->external_id))
                ->with('oneCItem')
                ->get();
            if ($candidates->count() !== 1) {
                $errors[] = 'identity_candidate_not_unique';
            }
            $candidate = $candidates->first();
            $manifestRows = $candidate === null ? [] : ($manifest[$candidate->legacy_id] ?? []);
            if (count($manifestRows) !== 1) {
                $errors[] = 'manifest_row_not_unique';
            }
            $manifestRow = $manifestRows[0] ?? null;

            $categories = SiteCategory::query()
                ->where('site_id', $site->id)
                ->whereHas('products', fn ($query) => $query->whereKey($siteProduct?->id))
                ->orderBy('external_id')
                ->get(['external_id', 'source', 'name', 'slug', 'is_published'])
                ->map(fn (SiteCategory $category) => $category->only(['external_id', 'source', 'name', 'slug', 'is_published']))
                ->all();
            if ($categories === []) {
                $errors[] = 'missing_category_assignment';
            }

            $urls = $siteProduct === null ? collect() : SiteUrl::query()
                ->where('site_id', $site->id)->where('target_type', 'product')->where('target_id', $siteProduct->id)->get();
            if ($urls->count() > 1) {
                $errors[] = 'ambiguous_final_url';
            }
            $attributes = $product?->technical_attributes ?? [];

            $rows[] = [
                'status' => $errors === [] ? 'PASS' : 'FAIL',
                'errors' => $errors,
                'external_id_1c' => $record->external_id,
                'staged_record_id' => $record->id,
                'catalog_product' => $product?->only(['id', 'external_id', 'name', 'sku', 'mpn', 'manufacturer', 'status']),
                'identity_candidate' => $candidate?->only(['id', 'legacy_source', 'legacy_id', 'legacy_name', 'match_method', 'confidence', 'confirmed_sku', 'confirmed_mpn']),
                'bitrix_manifest' => $manifestRow === null ? null : array_intersect_key($manifestRow, array_flip(['legacy_iblock_id', 'legacy_element_id', 'primary_section_path', 'focus_section_path', 'legacy_url_candidate', 'technology_from_name'])),
                'site_product' => $siteProduct?->only(['id', 'slug', 'is_published', 'availability', 'price']),
                'category_assignments' => $categories,
                'technology' => [
                    'chemistry' => $attributes['chemistry'] ?? null,
                    'provenance' => $attributes['chemistry_provenance'] ?? null,
                ],
                'final_url' => match ($urls->count()) {
                    0 => ['status' => 'not_configured'],
                    1 => ['status' => 'configured', ...$urls->first()->only(['path', 'locale', 'is_indexable'])],
                    default => ['status' => 'ambiguous'],
                },
            ];
        }

        $report = [
            'schema_version' => 1,
            'generated_at' => now()->toIso8601String(),
            'site' => $site->only(['id', 'key', 'domain']),
            'summary' => ['records' => count($rows), 'passed' => count(array_filter($rows, fn ($row) => $row['status'] === 'PASS')), 'failed' => count(array_filter($rows, fn ($row) => $row['status'] === 'FAIL'))],
            'rows' => $rows,
        ];
        $output = (string) $this->argument('output');
        if (! is_dir(dirname($output)) && ! mkdir(dirname($output), 0777, true) && ! is_dir(dirname($output))) {
            throw new RuntimeException('Unable to create report directory.');
        }
        file_put_contents($output, json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR));
        $this->info("Evidence report: {$report['summary']['passed']} PASS / {$report['summary']['failed']} FAIL.");

        return $report['summary']['failed'] === 0 ? self::SUCCESS : self::FAILURE;
    }

    /** @return array<string, list<array<string, string>>> */
    private function manifest(string $file): array
    {
        $handle = fopen($file, 'rb');
        if ($handle === false) {
            throw new RuntimeException('Manifest CSV was not found.');
        }
        if (fread($handle, 3) !== "\xEF\xBB\xBF") {
            rewind($handle);
        }
        $headers = fgetcsv($handle, 0, ',', '"', '');
        if ($headers === false || ! in_array('legacy_element_id', $headers, true)) {
            throw new RuntimeException('Manifest CSV must include legacy_element_id.');
        }
        $result = [];
        while (($values = fgetcsv($handle)) !== false) {
            if (count($values) !== count($headers)) {
                continue;
            }
            $row = array_combine($headers, $values);
            $result[(string) $row['legacy_element_id']][] = $row;
        }
        fclose($handle);

        return $result;
    }
}
