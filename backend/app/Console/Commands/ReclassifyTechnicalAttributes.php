<?php

namespace App\Console\Commands;

use App\Events\SiteContentChanged;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/** Move an already-known fact between technical-attribute keys without changing its value. */
class ReclassifyTechnicalAttributes extends Command
{
    protected $signature = 'catalog:reclassify-technical-attributes
                            {site : Site key used as the reviewed manifest context}
                            {file : JSON manifest with exact before/after pins}
                            {--apply : Persist the reclassification; default is a write-free dry-run}';

    protected $description = 'Fail-closed reclassification of a technical attribute key on shared canonical products';

    public function handle(): int
    {
        try {
            $site = Site::query()->where('key', trim((string) $this->argument('site')))->first();
            if ($site === null) {
                throw new RuntimeException('Site was not found.');
            }

            $file = (string) $this->argument('file');
            $rows = $this->manifest($site, $file);
            $apply = (bool) $this->option('apply');
            $plans = $this->validateRows($rows);
            $summary = $this->summary($site, $plans, $apply);

            if ($apply) {
                $events = $this->apply($site, $file, $rows, $plans, $summary);
                foreach ($events as $event) {
                    SiteContentChanged::dispatch($event['site'], $event['paths']);
                }
            }

            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
            $this->warn($summary['canonical_write_note']);

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /** @param list<array<string, mixed>> $rows
     * @return list<array{product: Product, row: array<string, mixed>, before: array<string, mixed>, after: array<string, mixed>, state: string, linked_site_products: list<SiteProduct>}>
     */
    private function validateRows(array $rows): array
    {
        $plans = [];
        $seen = [];

        foreach ($rows as $index => $row) {
            $allowed = [
                'external_id', 'expected_name', 'expected_manufacturer', 'expected_mpn',
                'name_evidence_phrase', 'source_key', 'source_value', 'target_key',
                'expected_linked_site_keys', 'expected_before_attributes', 'expected_after_attributes',
                'evidence_note',
            ];
            $unknown = array_values(array_diff(array_keys($row), $allowed));
            if ($unknown !== []) {
                throw new RuntimeException("Correction row {$index} contains unknown fields: ".implode(', ', $unknown).'.');
            }
            foreach (['external_id', 'expected_name', 'expected_manufacturer', 'expected_mpn', 'name_evidence_phrase', 'source_key', 'source_value', 'target_key', 'evidence_note'] as $field) {
                if (! is_string($row[$field] ?? null) || trim($row[$field]) === '') {
                    throw new RuntimeException("Correction row {$index} requires non-empty {$field}.");
                }
            }
            foreach (['expected_before_attributes', 'expected_after_attributes'] as $field) {
                if (! is_array($row[$field] ?? null) || array_is_list($row[$field])) {
                    throw new RuntimeException("Correction row {$index} requires {$field} as an object.");
                }
            }
            $linkedKeys = $row['expected_linked_site_keys'] ?? null;
            if (! is_array($linkedKeys) || $linkedKeys === [] || ! array_is_list($linkedKeys)
                || count($linkedKeys) !== count(array_unique($linkedKeys))
                || collect($linkedKeys)->contains(fn (mixed $key): bool => ! is_string($key) || trim($key) === '')) {
                throw new RuntimeException("Correction row {$index} requires unique non-empty expected_linked_site_keys.");
            }

            $externalId = trim($row['external_id']);
            if (isset($seen[$externalId])) {
                throw new RuntimeException("Manifest repeats product {$externalId}.");
            }
            $seen[$externalId] = true;

            $sourceKey = trim($row['source_key']);
            $targetKey = trim($row['target_key']);
            $sourceValue = trim($row['source_value']);
            if ($sourceKey === $targetKey) {
                throw new RuntimeException("Correction row {$index} source_key equals target_key.");
            }

            $before = $this->canonicalize($row['expected_before_attributes']);
            $expectedAfter = $before;
            if (! array_key_exists($sourceKey, $expectedAfter) || $expectedAfter[$sourceKey] !== $sourceValue) {
                throw new RuntimeException("Correction row {$index} before attributes do not pin source_key/source_value.");
            }
            if (array_key_exists($targetKey, $expectedAfter)) {
                throw new RuntimeException("Correction row {$index} target_key already exists in before attributes.");
            }
            unset($expectedAfter[$sourceKey]);
            $expectedAfter[$targetKey] = $sourceValue;
            $expectedAfter = $this->canonicalize($expectedAfter);
            $after = $this->canonicalize($row['expected_after_attributes']);
            if ($after !== $expectedAfter) {
                throw new RuntimeException("Correction row {$index} after attributes must only move the unchanged source value to target_key.");
            }

            $product = Product::query()->where('external_id', $externalId)->first();
            if ($product === null
                || $product->name !== trim($row['expected_name'])
                || (string) $product->manufacturer !== trim($row['expected_manufacturer'])
                || (string) $product->mpn !== trim($row['expected_mpn'])) {
                throw new RuntimeException("Product {$externalId} identity pins do not match.");
            }
            if (! str_contains($product->name, trim($row['name_evidence_phrase']))) {
                throw new RuntimeException("Product {$externalId} name lacks the exact evidence phrase.");
            }

            $linked = SiteProduct::query()->with(['site', 'categories'])->where('product_id', $product->id)->get();
            $actualLinkedKeys = $linked->pluck('site.key')->filter()->sort()->values()->all();
            $expectedLinkedKeys = collect($linkedKeys)->map(fn (string $key): string => trim($key))->sort()->values()->all();
            if ($actualLinkedKeys !== $expectedLinkedKeys) {
                throw new RuntimeException("Product {$externalId} linked sites drifted from the manifest.");
            }

            $current = $this->canonicalize(is_array($product->technical_attributes) ? $product->technical_attributes : []);
            $state = match (true) {
                $current === $before => 'pending',
                $current === $after => 'already_applied',
                default => throw new RuntimeException("Product {$externalId} technical attributes drifted from both manifest states."),
            };
            $plans[] = [
                'product' => $product,
                'row' => $row,
                'before' => $before,
                'after' => $after,
                'state' => $state,
                'linked_site_products' => $linked->values()->all(),
            ];
        }

        return $plans;
    }

    /** @param list<array<string, mixed>> $rows
     * @param  list<array{product: Product, row: array<string, mixed>, before: array<string, mixed>, after: array<string, mixed>, state: string, linked_site_products: list<SiteProduct>}>  $plans
     * @param  array<string, mixed>  $summary
     * @return list<array{site: Site, paths: list<string>}>
     */
    private function apply(Site $contextSite, string $file, array $rows, array $plans, array &$summary): array
    {
        $eventsBySite = [];

        DB::transaction(function () use ($contextSite, $file, $rows, $plans, &$summary, &$eventsBySite): void {
            // Lock and validate again inside the transaction to close the gap between validation and write.
            foreach ($plans as $plan) {
                $locked = Product::query()->lockForUpdate()->findOrFail($plan['product']->id);
                $current = $this->canonicalize(is_array($locked->technical_attributes) ? $locked->technical_attributes : []);
                $expected = $plan['state'] === 'pending' ? $plan['before'] : $plan['after'];
                if ($current !== $expected) {
                    throw new RuntimeException("Product {$locked->external_id} changed after validation; no corrections were applied.");
                }
            }

            $run = ImportRun::query()->create([
                'source' => 'technical_attribute_reclassification_manifest',
                'source_file' => basename($file),
                'status' => 'running',
                'total_records' => count($plans),
                'started_at' => now(),
            ]);

            foreach ($plans as $index => $plan) {
                /** @var Product $product */
                $product = $plan['product'];
                $changed = $plan['state'] === 'pending';
                if ($changed) {
                    $product->technical_attributes = $plan['after'];
                    $product->save();
                    $summary['reclassified']++;
                } else {
                    $summary['already_applied']++;
                }

                StagedImportRecord::query()->create([
                    'import_run_id' => $run->id,
                    'row_number' => $index + 1,
                    'entity_type' => 'technical_attribute_reclassification',
                    'external_id' => $product->external_id,
                    'payload' => $rows[$index],
                    'normalized_payload' => [
                        'before_technical_attributes' => $plan['before'],
                        'after_technical_attributes' => $plan['after'],
                        'linked_site_keys' => collect($plan['linked_site_products'])->pluck('site.key')->sort()->values()->all(),
                        'writes_canonical_product_attributes' => true,
                    ],
                    'validation_errors' => [],
                    'status' => $changed ? 'applied' : 'unchanged',
                    'review_note' => trim($plan['row']['evidence_note']),
                    'published_product_id' => $product->id,
                    'published_site_id' => $contextSite->id,
                    'publication_snapshot' => [
                        'publication_changes' => 0,
                        'commercial_changes' => 0,
                        'identity_changes' => 0,
                        'canonical_product_attribute_change' => $changed,
                    ],
                ]);

                foreach ($plan['linked_site_products'] as $siteProduct) {
                    $siteId = $siteProduct->site_id;
                    $paths = SiteUrl::query()
                        ->where('site_id', $siteId)
                        ->where('target_type', 'product')
                        ->where('target_id', $siteProduct->id)
                        ->pluck('path')
                        ->all();
                    $categoryIds = $siteProduct->categories->pluck('id')->map(fn (mixed $id): int => (int) $id)->all();
                    $paths = array_values(array_unique([
                        ...$paths,
                        ...SiteCategory::revalidationPaths($siteId, $categoryIds),
                        '/catalog',
                        '/sitemap.xml',
                    ]));
                    $eventsBySite[$siteId] ??= ['site' => $siteProduct->site, 'paths' => []];
                    $eventsBySite[$siteId]['paths'] = array_values(array_unique([...$eventsBySite[$siteId]['paths'], ...$paths]));
                }
            }

            $run->update([
                'status' => 'completed',
                'processed_records' => $summary['reclassified'],
                'failed_records' => 0,
                'summary' => $summary,
                'finished_at' => now(),
            ]);
            $summary['import_run_id'] = $run->id;
        });

        return array_values($eventsBySite);
    }

    /** @param list<array{product: Product, row: array<string, mixed>, before: array<string, mixed>, after: array<string, mixed>, state: string, linked_site_products: list<SiteProduct>}> $plans
     * @return array<string, mixed>
     */
    private function summary(Site $site, array $plans, bool $apply): array
    {
        $affected = collect($plans)->flatMap(fn (array $plan): array => collect($plan['linked_site_products'])->pluck('site.key')->all())->unique()->sort()->values()->all();

        return [
            'mode' => $apply ? 'apply' : 'dry_run',
            'context_site' => $site->key,
            'records' => count($plans),
            'pending' => collect($plans)->where('state', 'pending')->count(),
            'reclassified' => 0,
            'already_applied' => $apply ? 0 : collect($plans)->where('state', 'already_applied')->count(),
            'affected_site_keys' => $affected,
            'writes_canonical_product_attributes' => true,
            'canonical_write_note' => 'WARNING: technical_attributes live on the shared canonical products table; an applied correction affects every linked site listed in affected_site_keys.',
            'fact_value_changes' => 0,
            'publication_changes' => 0,
            'commercial_changes' => 0,
            'identity_changes' => 0,
        ];
    }

    /** @return list<array<string, mixed>> */
    private function manifest(Site $site, string $file): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Technical-attribute reclassification manifest is not readable.');
        }
        $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest)
            || array_keys($manifest) !== ['schema_version', 'site_key', 'corrections']
            || ($manifest['schema_version'] ?? null) !== 1
            || ($manifest['site_key'] ?? null) !== $site->key
            || ! is_array($manifest['corrections'] ?? null)
            || $manifest['corrections'] === []) {
            throw new RuntimeException('Manifest requires only schema_version=1, matching site_key, and non-empty corrections.');
        }

        return $manifest['corrections'];
    }

    /** @param array<string, mixed> $value
     * @return array<string, mixed>
     */
    private function canonicalize(array $value): array
    {
        foreach ($value as $key => $item) {
            if (is_array($item)) {
                $value[$key] = array_is_list($item)
                    ? array_map(fn (mixed $nested): mixed => is_array($nested) ? $this->canonicalize($nested) : $nested, $item)
                    : $this->canonicalize($item);
            }
        }
        ksort($value, SORT_STRING);

        return $value;
    }
}
