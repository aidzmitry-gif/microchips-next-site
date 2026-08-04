<?php

namespace App\Domain\Imports;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteCategoryProduct;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class SiteProductCategoryMover
{
    /** @return array<string, mixed> */
    public function move(Site $site, string $file, string $delimiter, string $categorySource, bool $apply): array
    {
        [$rows, $readErrors] = $this->read($file, $delimiter);
        $validation = $this->validate($site, $categorySource, $rows, $readErrors);
        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'site_id' => $site->id,
            'site_key' => $site->key,
            'category_source' => $categorySource,
            'csv_records' => count($rows),
            'accepted_records' => 0,
            'moves_completed' => 0,
            'already_moved' => 0,
            'target_links_reused' => 0,
            'routes_updated' => 0,
            'move_details' => [],
            'is_published_changed' => 0,
            'validation_error_count' => count($validation['errors']),
            'validation_errors' => array_slice($validation['errors'], 0, 50),
        ];

        if ($validation['errors'] !== []) {
            return $summary;
        }

        $summary['accepted_records'] = count($rows);
        DB::beginTransaction();

        try {
            foreach ($validation['moves'] as $move) {
                $from = SiteCategoryProduct::query()
                    ->where('site_category_id', $move['from_category_id'])
                    ->where('site_product_id', $move['site_product_id'])
                    ->first();
                $to = SiteCategoryProduct::query()
                    ->where('site_category_id', $move['to_category_id'])
                    ->where('site_product_id', $move['site_product_id'])
                    ->first();

                if ($from === null && $to !== null) {
                    $summary['already_moved']++;
                } else {
                    $targetReused = $to !== null;
                    if ($to === null) {
                        $to = SiteCategoryProduct::create([
                            'site_id' => $site->id,
                            'site_category_id' => $move['to_category_id'],
                            'site_product_id' => $move['site_product_id'],
                        ]);
                    } else {
                        $summary['target_links_reused']++;
                    }

                    $from?->delete();
                    $summary['moves_completed']++;
                    $summary['move_details'][] = [
                        'product_external_id' => $move['product_external_id'],
                        'site_product_id' => $move['site_product_id'],
                        'from_category_external_id' => $move['from_category_external_id'],
                        'to_category_external_id' => $move['to_category_external_id'],
                        'target_link_id' => $to->id,
                        'target_link_reused' => $targetReused,
                    ];
                }

                $url = SiteUrl::query()
                    ->where('site_id', $site->id)
                    ->where('target_type', 'product')
                    ->where('target_id', $move['site_product_id'])
                    ->first();
                if ($url !== null && $url->path !== $move['target_path']) {
                    $url->update(['path' => $move['target_path']]);
                    SiteSeo::query()
                        ->where('site_id', $site->id)
                        ->where('resource_type', 'product')
                        ->where('resource_id', $move['site_product_id'])
                        ->update(['canonical_path' => $move['target_path']]);
                    $summary['routes_updated']++;
                }
            }

            if ($apply) {
                DB::commit();
            } else {
                DB::rollBack();
            }
        } catch (Throwable $error) {
            if (DB::transactionLevel() > 0) {
                DB::rollBack();
            }
            throw $error;
        }

        return $summary;
    }

    /**
     * @param  list<array<string, mixed>>  $rows
     * @param  list<array<string, mixed>>  $readErrors
     * @return array{errors: list<array<string, mixed>>, moves: list<array<string, mixed>>}
     */
    private function validate(Site $site, string $categorySource, array $rows, array $readErrors): array
    {
        $errors = $readErrors;
        $seenProducts = [];
        foreach ($rows as $row) {
            if (isset($seenProducts[$row['product_external_id']])) {
                $errors[] = $this->error($row['row_number'], 'duplicate_product_row', [
                    'product_external_id' => $row['product_external_id'],
                ]);
            }
            $seenProducts[$row['product_external_id']] = true;
            if ($row['from_category_external_id'] === $row['to_category_external_id']) {
                $errors[] = $this->error($row['row_number'], 'source_and_target_are_identical');
            }
        }

        $products = Product::query()
            ->whereIn('external_id', array_values(array_unique(array_column($rows, 'product_external_id'))))
            ->get()->keyBy('external_id');
        $siteProducts = SiteProduct::query()
            ->where('site_id', $site->id)
            ->whereIn('product_id', $products->pluck('id')->all())
            ->get()->keyBy('product_id');
        $categoryIds = array_values(array_unique([
            ...array_column($rows, 'from_category_external_id'),
            ...array_column($rows, 'to_category_external_id'),
        ]));
        $categories = SiteCategory::query()
            ->where('site_id', $site->id)
            ->where('source', $categorySource)
            ->whereIn('external_id', $categoryIds)
            ->get()->keyBy('external_id');

        $moves = [];
        foreach ($rows as $row) {
            $product = $products->get($row['product_external_id']);
            $siteProduct = $product === null ? null : $siteProducts->get($product->id);
            $from = $categories->get($row['from_category_external_id']);
            $to = $categories->get($row['to_category_external_id']);

            if ($product === null) {
                $errors[] = $this->error($row['row_number'], 'unknown_product', ['product_external_id' => $row['product_external_id']]);
            } elseif ($siteProduct === null) {
                $errors[] = $this->error($row['row_number'], 'product_not_linked_to_site', ['product_external_id' => $row['product_external_id']]);
            }
            if ($from === null) {
                $errors[] = $this->error($row['row_number'], 'unknown_source_category', ['external_id' => $row['from_category_external_id']]);
            }
            if ($to === null) {
                $errors[] = $this->error($row['row_number'], 'unknown_target_category', ['external_id' => $row['to_category_external_id']]);
            }
            if ($siteProduct === null || $from === null || $to === null) {
                continue;
            }

            $hasFrom = SiteCategoryProduct::query()
                ->where('site_category_id', $from->id)
                ->where('site_product_id', $siteProduct->id)->exists();
            $hasTo = SiteCategoryProduct::query()
                ->where('site_category_id', $to->id)
                ->where('site_product_id', $siteProduct->id)->exists();
            if (! $hasFrom && ! $hasTo) {
                $errors[] = $this->error($row['row_number'], 'source_assignment_missing', [
                    'product_external_id' => $row['product_external_id'],
                    'from_category_external_id' => $row['from_category_external_id'],
                ]);

                continue;
            }

            $targetPath = '/'.trim($to->slug, '/').'/'.trim($siteProduct->slug, '/');
            $urls = SiteUrl::query()
                ->where('site_id', $site->id)
                ->where('target_type', 'product')
                ->where('target_id', $siteProduct->id)
                ->get();
            if ($urls->count() > 1) {
                $errors[] = $this->error($row['row_number'], 'ambiguous_product_urls', [
                    'product_external_id' => $row['product_external_id'],
                ]);

                continue;
            }
            if ($urls->isNotEmpty() && SiteUrl::query()
                ->where('site_id', $site->id)
                ->where('path', $targetPath)
                ->where('id', '!=', $urls->first()->id)
                ->exists()) {
                $errors[] = $this->error($row['row_number'], 'target_path_conflict', [
                    'product_external_id' => $row['product_external_id'],
                    'target_path' => $targetPath,
                ]);

                continue;
            }

            $moves[] = [
                'product_external_id' => $row['product_external_id'],
                'site_product_id' => $siteProduct->id,
                'from_category_id' => $from->id,
                'to_category_id' => $to->id,
                'from_category_external_id' => $row['from_category_external_id'],
                'to_category_external_id' => $row['to_category_external_id'],
                'target_path' => $targetPath,
            ];
        }

        return ['errors' => $errors, 'moves' => $errors === [] ? $moves : []];
    }

    /** @return array{list<array<string, mixed>>, list<array<string, mixed>>} */
    private function read(string $file, string $delimiter): array
    {
        $handle = fopen($file, 'rb');
        if ($handle === false) {
            throw new RuntimeException("Unable to open {$file}.");
        }

        try {
            $headers = fgetcsv($handle, 0, $delimiter, '"', '');
            if ($headers === false) {
                throw new RuntimeException('CSV file does not contain a header row.');
            }
            $headers = array_map(fn ($header): string => mb_strtolower(ltrim(trim((string) $header), "\xEF\xBB\xBF")), $headers);
            $required = ['product_external_id', 'from_category_external_id', 'to_category_external_id'];
            if ($headers !== $required) {
                throw new RuntimeException('CSV headers must be exactly: '.implode(',', $required).'.');
            }

            $rows = [];
            $errors = [];
            $rowNumber = 1;
            while (($raw = fgetcsv($handle, 0, $delimiter, '"', '')) !== false) {
                $rowNumber++;
                if ($raw === [null] || $raw === []) {
                    continue;
                }
                if (count($raw) !== 3) {
                    $errors[] = $this->error($rowNumber, 'column_count_mismatch');

                    continue;
                }
                $values = array_map(fn ($value): string => trim((string) $value), $raw);
                if (in_array('', $values, true) || collect($values)->contains(fn (string $value): bool => mb_strlen($value) > 255)) {
                    $errors[] = $this->error($rowNumber, 'invalid_required_fields');

                    continue;
                }
                $rows[] = [
                    'row_number' => $rowNumber,
                    'product_external_id' => $values[0],
                    'from_category_external_id' => $values[1],
                    'to_category_external_id' => $values[2],
                ];
            }

            return [$rows, $errors];
        } finally {
            fclose($handle);
        }
    }

    /** @param array<string, mixed> $context */
    private function error(?int $rowNumber, string $reason, array $context = []): array
    {
        return ['row_number' => $rowNumber, 'reason' => $reason, ...$context];
    }
}
