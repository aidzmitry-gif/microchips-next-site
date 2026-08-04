<?php

namespace App\Console\Commands;

use App\Models\ProductDescriptionDraft;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Console\Command;
use Illuminate\Support\Collection;
use RuntimeException;

class BuildCatalogEnrichmentQueue extends Command
{
    protected $signature = 'catalog:build-enrichment-queue
                            {site : Site key}
                            {output : Destination CSV path}
                            {--baseline= : Fixed catalog denominator}
                            {--target-percent=10 : Target percentage of content-complete cards}
                            {--published-only : Include only products already visible on the regional storefront}
                            {--exclude-category=* : Category external ID excluded from this wave}
                            {--skip-file= : CSV of confirmed hold product_external_id values to omit from this pending queue only}
                            {--audit-output= : Optional full CSV readiness registry for every eligible product}';

    protected $description = 'Build a deterministic evidence-enrichment queue to a fixed content-completeness target';

    /** @var array<string, int> */
    private const CATEGORY_PRIORITY = [
        'seo:batteries-ups' => 10,
        'seo:batteries-industrial' => 20,
        'seo:batteries-traction' => 30,
        'seo:ups-systems' => 40,
        'seo:power-supplies' => 50,
        'seo:power-converters' => 60,
        'seo:chargers' => 70,
        'seo:primary-cells' => 80,
        'seo:rechargeable-cells' => 90,
    ];

    public function handle(): int
    {
        $site = Site::query()->where('key', trim((string) $this->argument('site')))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        $baseline = filter_var($this->option('baseline'), FILTER_VALIDATE_INT);
        $percent = filter_var($this->option('target-percent'), FILTER_VALIDATE_FLOAT);
        if ($baseline === false || $baseline < 1 || $percent === false || $percent <= 0 || $percent > 100) {
            $this->error('A positive --baseline and --target-percent between 0 and 100 are required.');

            return self::FAILURE;
        }

        try {
            $skippedExternalIds = $this->readSkippedExternalIds($this->option('skip-file'));
        } catch (RuntimeException $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $excludedCategories = collect((array) $this->option('exclude-category'))
            ->map(fn (mixed $value): string => trim((string) $value))
            ->filter()->unique()->values();
        $productsQuery = SiteProduct::query()
            ->where('site_id', $site->id)
            ->with(['product', 'categories']);
        if ((bool) $this->option('published-only')) {
            $productsQuery->published();
        }
        $eligible = collect();
        $productsQuery->chunkById(500, function (Collection $products) use (&$eligible, $site, $excludedCategories): void {
            $productIds = $products->pluck('product_id')->all();
            $descriptionDrafts = ProductDescriptionDraft::query()
                ->whereIn('product_id', $productIds)
                ->where('locale', $site->default_locale)
                ->where('status', 'applied')
                ->get(['product_id', 'source_tier', 'manufacturer_primary'])
                ->keyBy('product_id');
            $legacyDescriptions = ProductDescriptionDraft::query()
                ->whereIn('product_id', $productIds)
                ->where('locale', $site->default_locale)
                ->where('source_kind', 'legacy_bitrix_exact_element_preview')
                ->where('status', 'legacy_preview_applied')
                ->pluck('product_id')->flip();
            $strictImaged = ProductMedia::query()
                ->whereIn('product_id', $productIds)
                ->storefrontReady()
                ->pluck('product_id')->flip();
            $previewImaged = ProductMedia::query()
                ->whereIn('product_id', $productIds)
                ->previewReady()
                ->pluck('product_id')->flip();

            foreach ($products as $siteProduct) {
                $categories = $siteProduct->categories
                    ->reject(fn ($category): bool => $excludedCategories->contains($category->external_id))
                    ->sortBy(fn ($category): array => [self::CATEGORY_PRIORITY[$category->external_id] ?? 500, $category->external_id])
                    ->values();
                $product = $siteProduct->product;
                if ($categories->isEmpty() || $product === null) {
                    continue;
                }
                $descriptionDraft = $descriptionDrafts->get($product->id);
                $hasDescription = $descriptionDraft !== null && filled($product->short_description);
                $hasLegacyDescription = $legacyDescriptions->has($product->id) && filled($product->short_description);
                $hasImage = $strictImaged->has($product->id);
                $hasPreviewImage = $previewImaged->has($product->id);
                $category = $categories->first();
                $identityFields = collect([$product->sku, $product->mpn, $product->manufacturer])
                    ->filter(fn ($value): bool => filled($value))->count();
                $stableIdentifiers = collect([$product->sku, $product->mpn])
                    ->filter(fn ($value): bool => filled($value))->count();
                $hasManufacturer = filled($product->manufacturer);
                $identityReady = $hasManufacturer && $stableIdentifiers > 0;
                $technicalFactCount = $this->publicTechnicalFactCount($product->technical_attributes);
                $readinessClass = $this->readinessClass(
                    $identityReady,
                    $hasDescription,
                    $technicalFactCount,
                    $hasImage,
                    $hasPreviewImage,
                    $hasLegacyDescription,
                );
                $eligible->push([
                    'product_external_id' => $product->external_id,
                    'name' => $product->name,
                    'sku' => $product->sku,
                    'mpn' => $product->mpn,
                    'manufacturer' => $product->manufacturer,
                    'category_external_id' => $category->external_id,
                    'category_name' => $category->name,
                    'category_priority' => self::CATEGORY_PRIORITY[$category->external_id] ?? 500,
                    'has_applied_description' => $hasDescription,
                    'has_legacy_preview_description' => $hasLegacyDescription,
                    'has_verified_published_image' => $hasImage,
                    'has_displayable_preview_image' => $hasPreviewImage,
                    'description_source_tier' => $descriptionDraft?->source_tier,
                    'description_manufacturer_primary' => (bool) ($descriptionDraft?->manufacturer_primary ?? false),
                    'completion_gap_count' => (int) ! $hasDescription + (int) ! $hasImage,
                    'identity_fields_present' => $identityFields,
                    'stable_identifier_fields_present' => $stableIdentifiers,
                    'has_manufacturer' => $hasManufacturer,
                    'identity_ready' => $identityReady,
                    'technical_fact_count' => $technicalFactCount,
                    'readiness_class' => $readinessClass,
                    'is_published' => $siteProduct->is_published,
                ]);
            }
        });
        $eligible = $eligible->values();

        $targetCards = (int) ceil($baseline * ((float) $percent / 100));
        $currentComplete = $eligible->where('completion_gap_count', 0)->count();
        $needed = max(0, $targetCards - $currentComplete);
        $queue = $eligible->where('completion_gap_count', '>', 0)
            ->reject(fn (array $row): bool => $skippedExternalIds->contains($row['product_external_id']))
            ->sortBy(fn (array $row): array => [
                $row['completion_gap_count'],
                $row['category_priority'],
                -$row['identity_fields_present'],
                mb_strtolower((string) $row['name']),
                $row['product_external_id'],
            ])->take($needed)->values();

        try {
            $this->writeQueue((string) $this->argument('output'), $queue);
            $auditOutput = trim((string) $this->option('audit-output'));
            if ($auditOutput !== '') {
                $this->writeAudit($auditOutput, $eligible);
            }
        } catch (RuntimeException $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $summary = [
            'site_key' => $site->key,
            'fixed_baseline' => $baseline,
            'target_percent' => (float) $percent,
            'published_only' => (bool) $this->option('published-only'),
            'target_content_complete_cards' => $targetCards,
            'eligible_site_products' => $eligible->count(),
            'current_content_complete_cards' => $currentComplete,
            'queue_records' => $queue->count(),
            'remaining_gap_after_queue' => max(0, $needed - $queue->count()),
            'skipped_hold_products' => $skippedExternalIds->count(),
            'skip_file_path' => $this->normalizedSkipFilePath($this->option('skip-file')),
            'excluded_categories' => $excludedCategories->all(),
            'category_distribution' => $queue->countBy('category_external_id')->sortKeys()->all(),
            'audit_output_path' => $auditOutput === '' ? null : $auditOutput,
            'readiness_distribution' => $eligible->countBy('readiness_class')->sortKeys()->all(),
        ];
        $summaryPath = preg_replace('/\.csv$/i', '', (string) $this->argument('output')).'.summary.json';
        file_put_contents($summaryPath, json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR).PHP_EOL);
        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return $summary['remaining_gap_after_queue'] === 0 ? self::SUCCESS : self::FAILURE;
    }

    /** @return Collection<int, string> */
    private function readSkippedExternalIds(mixed $skipFile): Collection
    {
        $path = $this->normalizedSkipFilePath($skipFile);
        if ($path === null) {
            return collect();
        }
        if (! is_file($path) || ! is_readable($path)) {
            throw new RuntimeException('Skip file must be a readable CSV file.');
        }

        $handle = fopen($path, 'rb');
        if ($handle === false) {
            throw new RuntimeException('Skip file must be a readable CSV file.');
        }

        try {
            $rawHeader = fgets($handle);
            if ($rawHeader === false) {
                throw new RuntimeException('Skip file must contain a CSV header with product_external_id.');
            }
            // A UTF-8 BOM precedes the opening quote in CSVs produced by
            // PowerShell/Excel. fgetcsv() would then treat that quote as a
            // literal character, so remove the BOM before parsing the line.
            $rawHeader = preg_replace('/^\xEF\xBB\xBF/', '', $rawHeader) ?? $rawHeader;
            $header = str_getcsv($rawHeader, ',', '"', '');
            $header = array_map(fn (?string $value): string => trim((string) $value), $header);
            $headerPositions = array_keys($header, 'product_external_id', true);
            if (count($headerPositions) !== 1) {
                throw new RuntimeException('Skip file must contain exactly one product_external_id header.');
            }
            $externalIdColumn = $headerPositions[0];
            $externalIds = [];
            $line = 1;
            while (($row = fgetcsv($handle, 0, ',', '"', '')) !== false) {
                $line++;
                $externalId = trim((string) ($row[$externalIdColumn] ?? ''));
                if ($externalId === '') {
                    throw new RuntimeException("Skip file contains an empty product_external_id at line {$line}.");
                }
                if (isset($externalIds[$externalId])) {
                    throw new RuntimeException("Skip file contains duplicate product_external_id '{$externalId}'.");
                }
                $externalIds[$externalId] = true;
            }

            return collect(array_keys($externalIds));
        } finally {
            fclose($handle);
        }
    }

    private function normalizedSkipFilePath(mixed $skipFile): ?string
    {
        $path = trim((string) $skipFile);

        return $path === '' ? null : $path;
    }

    /** @param Collection<int, array<string, mixed>> $queue */
    private function writeQueue(string $output, Collection $queue): void
    {
        $directory = dirname($output);
        if (! is_dir($directory) && ! mkdir($directory, 0777, true) && ! is_dir($directory)) {
            throw new RuntimeException('Unable to create queue output directory.');
        }
        $handle = fopen($output, 'wb');
        if ($handle === false) {
            throw new RuntimeException('Unable to create queue CSV.');
        }
        try {
            fwrite($handle, "\xEF\xBB\xBF");
            fputcsv($handle, [
                'priority', 'product_external_id', 'name', 'sku', 'mpn', 'manufacturer',
                'category_external_id', 'category_name', 'has_applied_description',
                'has_verified_published_image', 'completion_gap_count', 'identity_fields_present',
                'is_published', 'research_status',
            ], ',', '"', '');
            foreach ($queue as $index => $row) {
                fputcsv($handle, [
                    $index + 1,
                    $row['product_external_id'],
                    $row['name'],
                    $row['sku'],
                    $row['mpn'],
                    $row['manufacturer'],
                    $row['category_external_id'],
                    $row['category_name'],
                    $row['has_applied_description'] ? 'true' : 'false',
                    $row['has_verified_published_image'] ? 'true' : 'false',
                    $row['completion_gap_count'],
                    $row['identity_fields_present'],
                    $row['is_published'] ? 'true' : 'false',
                    'pending_official_source_research',
                ], ',', '"', '');
            }
        } finally {
            fclose($handle);
        }
    }

    /** @param Collection<int, array<string, mixed>> $eligible */
    private function writeAudit(string $output, Collection $eligible): void
    {
        $directory = dirname($output);
        if (! is_dir($directory) && ! mkdir($directory, 0777, true) && ! is_dir($directory)) {
            throw new RuntimeException('Unable to create audit output directory.');
        }
        $handle = fopen($output, 'wb');
        if ($handle === false) {
            throw new RuntimeException('Unable to create readiness audit CSV.');
        }

        try {
            fwrite($handle, "\xEF\xBB\xBF");
            fputcsv($handle, [
                'product_external_id', 'name', 'category_external_id', 'category_name',
                'manufacturer', 'sku', 'mpn', 'identity_ready', 'stable_identifier_fields_present',
                'technical_fact_count', 'has_applied_description', 'description_source_tier',
                'description_manufacturer_primary', 'has_legacy_preview_description', 'has_displayable_preview_image',
                'has_verified_published_image', 'readiness_class', 'is_published',
            ], ',', '"', '');

            foreach ($eligible->sortBy(fn (array $row): array => [
                $row['category_priority'],
                $row['readiness_class'],
                mb_strtolower((string) $row['name']),
                $row['product_external_id'],
            ]) as $row) {
                fputcsv($handle, [
                    $row['product_external_id'], $row['name'], $row['category_external_id'], $row['category_name'],
                    $row['manufacturer'], $row['sku'], $row['mpn'], $row['identity_ready'] ? 'true' : 'false',
                    $row['stable_identifier_fields_present'], $row['technical_fact_count'],
                    $row['has_applied_description'] ? 'true' : 'false', $row['description_source_tier'],
                    $row['description_manufacturer_primary'] ? 'true' : 'false',
                    $row['has_legacy_preview_description'] ? 'true' : 'false',
                    $row['has_displayable_preview_image'] ? 'true' : 'false',
                    $row['has_verified_published_image'] ? 'true' : 'false',
                    $row['readiness_class'], $row['is_published'] ? 'true' : 'false',
                ], ',', '"', '');
            }
        } finally {
            fclose($handle);
        }
    }

    /** @param array<string, mixed>|null $attributes */
    private function publicTechnicalFactCount(?array $attributes): int
    {
        return collect($attributes ?? [])
            ->filter(function (mixed $value, mixed $key): bool {
                if (! is_string($key) || str_starts_with($key, '_')) {
                    return false;
                }

                return is_scalar($value) && trim((string) $value) !== '';
            })
            ->count();
    }

    private function readinessClass(
        bool $identityReady,
        bool $hasDescription,
        int $technicalFactCount,
        bool $hasStrictImage,
        bool $hasPreviewImage,
        bool $hasLegacyDescription,
    ): string {
        if ($identityReady && $hasDescription && $technicalFactCount >= 2 && $hasStrictImage) {
            return 'strict_content_ready';
        }
        if ($hasDescription || $hasStrictImage || ($identityReady && $technicalFactCount >= 2)) {
            return 'source_backed_partial';
        }
        if ($hasLegacyDescription && $hasPreviewImage) {
            return 'legacy_content_preview';
        }
        if ($hasPreviewImage) {
            return 'legacy_preview_only';
        }
        if ($hasLegacyDescription) {
            return 'legacy_text_only';
        }
        if ($identityReady) {
            return 'thin_identified';
        }

        return 'thin_unidentified';
    }
}
