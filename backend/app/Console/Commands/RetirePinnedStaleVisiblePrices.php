<?php

namespace App\Console\Commands;

use App\Events\SiteContentChanged;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/**
 * Remove a reviewed stale storefront price without altering publication,
 * indexability, availability, content, or product identity.
 */
class RetirePinnedStaleVisiblePrices extends Command
{
    private const RELEASE_SCHEMA = 'rb_stale_visible_price_retirement_v1';

    private const ROLLBACK_SCHEMA = 'rb_stale_visible_price_rollback_v1';

    protected $signature = 'catalog:retire-stale-visible-prices
                            {site : Site key}
                            {file : Hash-pinned retirement or rollback JSON manifest}
                            {--apply : Persist the change; default is a write-free dry run}
                            {--rollback : Restore the exact price and current-evidence flag}
                            {--rollback-output= : Rollback path written before apply}';

    protected $description = 'Fail-closed retirement and rollback of manifest-pinned stale visible prices';

    public function handle(): int
    {
        $site = Site::query()->where('key', trim((string) $this->argument('site')))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        $apply = (bool) $this->option('apply');
        $rollback = (bool) $this->option('rollback');
        $file = (string) $this->argument('file');
        if ($rollback && filled($this->option('rollback-output'))) {
            $this->error('--rollback-output cannot be used with --rollback.');

            return self::FAILURE;
        }

        try {
            $manifest = $this->readManifest($file);
            $plans = $rollback
                ? $this->validateRollback($site, $manifest)
                : $this->validateRetirement($site, $manifest);
            $rollbackPath = null;
            if ($apply && ! $rollback) {
                $rollbackPath = $this->rollbackOutputPath($file);
                $this->writeJsonAtomically($rollbackPath, $this->buildRollbackManifest($site, $file, $plans));
            }

            $paths = [];
            $summary = DB::transaction(function () use ($site, $file, $apply, $rollback, $rollbackPath, &$paths): array {
                // Re-read with row locks after the initial validation. This closes
                // the race between a price refresh and retirement.
                $lockedPlans = $rollback
                    ? $this->validateRollback($site, $this->readManifest($file), true)
                    : $this->validateRetirement($site, $this->readManifest($file), true);

                foreach ($lockedPlans as $plan) {
                    /** @var SiteProduct $siteProduct */
                    $siteProduct = $plan['site_product'];
                    /** @var SiteProductPriceEvidence $evidence */
                    $evidence = $plan['evidence'];
                    if ($rollback) {
                        $siteProduct->forceFill(['price' => $plan['restore_price']])->saveQuietly();
                        $evidence->forceFill(['is_current' => true])->saveQuietly();
                    } else {
                        $siteProduct->forceFill(['price' => null])->saveQuietly();
                        $evidence->forceFill(['is_current' => false])->saveQuietly();
                    }
                    $paths = array_values(array_unique([...$paths, ...$this->revalidationPaths($siteProduct, $plan['url'])]));
                }

                $summary = [
                    'mode' => $apply ? 'apply' : 'dry_run',
                    'operation' => $rollback ? 'rollback' : 'retire_stale_visible_price',
                    'site' => $site->key,
                    'records' => count($lockedPlans),
                    'price_changes' => count($lockedPlans),
                    'current_evidence_flag_changes' => count($lockedPlans),
                    'publication_changes' => 0,
                    'indexability_changes' => 0,
                    'availability_changes' => 0,
                    'content_changes' => 0,
                    'rollback_manifest' => $rollbackPath,
                ];

                if ($apply) {
                    $this->recordAudit($site, $file, $lockedPlans, $summary, $rollback);
                }

                if (! $apply) {
                    // Exercise the exact write path, then leave no rows or audit
                    // records behind.
                    DB::rollBack();
                    DB::beginTransaction();
                }

                return $summary;
            });

            if ($apply) {
                SiteContentChanged::dispatch($site, $paths);
            }

            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /**
     * @param  array<string, mixed>  $manifest
     * @return list<array{row: array<string,mixed>, product: Product, site_product: SiteProduct, evidence: SiteProductPriceEvidence, url: SiteUrl}>
     */
    private function validateRetirement(Site $site, array $manifest, bool $lock = false): array
    {
        $this->assertExactKeys($manifest, ['schema', 'site_key', 'source_cohort', 'max_age_days', 'products'], 'Manifest');
        if (($manifest['schema'] ?? null) !== self::RELEASE_SCHEMA
            || ($manifest['site_key'] ?? null) !== $site->key
            || ($manifest['max_age_days'] ?? null) !== 30
            || ! is_array($manifest['products'] ?? null)
            || $manifest['products'] === []) {
            throw new RuntimeException('Retirement manifest schema, site, max_age_days=30, or products is invalid.');
        }
        $this->validateSourceCohort($manifest['source_cohort']);

        $plans = [];
        $seen = [];
        foreach ($manifest['products'] as $index => $row) {
            if (! is_array($row)) {
                throw new RuntimeException("Retirement row {$index} must be an object.");
            }
            $this->assertExactKeys($row, [
                'external_id', 'product_id', 'site_product_id', 'price_evidence_id', 'site_url_id', 'path',
                'visible_price', 'currency', 'evidence_observed_at', 'evidence_key',
                'product_state_sha256', 'site_product_state_sha256', 'evidence_state_sha256', 'url_state_sha256',
            ], "Retirement row {$index}");
            $externalId = $this->requiredString($row, 'external_id', "Retirement row {$index}");
            if (isset($seen[$externalId])) {
                throw new RuntimeException("Retirement manifest repeats {$externalId}.");
            }
            $seen[$externalId] = true;

            $productQuery = Product::query();
            $siteProductQuery = SiteProduct::query();
            $evidenceQuery = SiteProductPriceEvidence::query();
            $urlQuery = SiteUrl::query();
            if ($lock) {
                $productQuery->lockForUpdate();
                $siteProductQuery->lockForUpdate();
                $evidenceQuery->lockForUpdate();
                $urlQuery->lockForUpdate();
            }
            $product = $productQuery->find($this->positiveInteger($row, 'product_id', $index));
            $siteProduct = $siteProductQuery->find($this->positiveInteger($row, 'site_product_id', $index));
            $evidence = $evidenceQuery->find($this->positiveInteger($row, 'price_evidence_id', $index));
            $url = $urlQuery->find($this->positiveInteger($row, 'site_url_id', $index));
            if ($product === null || $siteProduct === null || $evidence === null || $url === null) {
                throw new RuntimeException("Retirement row {$index} references a missing pinned record.");
            }
            if ($product->external_id !== $externalId
                || $siteProduct->site_id !== $site->id || $siteProduct->product_id !== $product->id
                || $evidence->site_id !== $site->id || $evidence->site_product_id !== $siteProduct->id
                || $url->site_id !== $site->id || $url->target_type !== 'product' || $url->target_id !== $siteProduct->id
                || $url->path !== $row['path']) {
                throw new RuntimeException("Retirement row {$index} site, identity, or path pins do not match.");
            }
            if ($siteProduct->price === null
                || ! $this->moneyEquals($siteProduct->price, $row['visible_price'])
                || ! $this->moneyEquals($evidence->calculated_price, $siteProduct->price)
                || ! $this->moneyEquals($evidence->calculated_price, $row['visible_price'])
                || $evidence->currency !== $row['currency']
                || $site->currency_code !== $row['currency']
                || ! $evidence->is_current
                || $evidence->evidence_key !== $row['evidence_key']
                || $evidence->observed_at?->toAtomString() !== $row['evidence_observed_at']) {
                throw new RuntimeException("Retirement row {$index} visible price or exact current evidence drifted.");
            }
            if (SiteProductPriceEvidence::query()->where('site_product_id', $siteProduct->id)->where('is_current', true)->count() !== 1) {
                throw new RuntimeException("Retirement row {$index} requires exactly one current price evidence row.");
            }
            if ($evidence->observed_at === null || ! $evidence->observed_at->lt(now()->subDays(30))) {
                throw new RuntimeException("Retirement row {$index} evidence is not older than 30 full days.");
            }

            $this->assertStateHash($row, 'product_state_sha256', $this->productState($product), $index);
            $this->assertStateHash($row, 'site_product_state_sha256', $this->siteProductState($siteProduct), $index);
            $this->assertStateHash($row, 'evidence_state_sha256', $this->evidenceState($evidence), $index);
            $this->assertStateHash($row, 'url_state_sha256', $this->urlState($url), $index);
            $plans[] = compact('row', 'product', 'siteProduct', 'evidence', 'url') + ['site_product' => $siteProduct];
        }

        return $plans;
    }

    /**
     * @param  array<string, mixed>  $manifest
     * @return list<array{row: array<string,mixed>, product: Product, site_product: SiteProduct, evidence: SiteProductPriceEvidence, url: SiteUrl, restore_price: string}>
     */
    private function validateRollback(Site $site, array $manifest, bool $lock = false): array
    {
        $this->assertExactKeys($manifest, ['schema', 'site_key', 'source_manifest_sha256', 'products'], 'Manifest');
        if (($manifest['schema'] ?? null) !== self::ROLLBACK_SCHEMA
            || ($manifest['site_key'] ?? null) !== $site->key
            || ! preg_match('/^[a-f0-9]{64}$/', (string) ($manifest['source_manifest_sha256'] ?? ''))
            || ! is_array($manifest['products'] ?? null)
            || $manifest['products'] === []) {
            throw new RuntimeException('Rollback manifest schema, site, source hash, or products is invalid.');
        }

        $plans = [];
        $seen = [];
        foreach ($manifest['products'] as $index => $row) {
            if (! is_array($row)) {
                throw new RuntimeException("Rollback row {$index} must be an object.");
            }
            $this->assertExactKeys($row, [
                'external_id', 'product_id', 'site_product_id', 'price_evidence_id', 'site_url_id', 'path',
                'restore_price', 'restore_evidence_current', 'retired_site_product_state_sha256',
                'retired_evidence_state_sha256', 'product_state_sha256', 'url_state_sha256',
            ], "Rollback row {$index}");
            $externalId = $this->requiredString($row, 'external_id', "Rollback row {$index}");
            if (isset($seen[$externalId]) || ($row['restore_evidence_current'] ?? null) !== true) {
                throw new RuntimeException("Rollback row {$index} is duplicated or does not restore the current flag.");
            }
            $seen[$externalId] = true;

            $productQuery = Product::query();
            $siteProductQuery = SiteProduct::query();
            $evidenceQuery = SiteProductPriceEvidence::query();
            $urlQuery = SiteUrl::query();
            if ($lock) {
                $productQuery->lockForUpdate();
                $siteProductQuery->lockForUpdate();
                $evidenceQuery->lockForUpdate();
                $urlQuery->lockForUpdate();
            }
            $product = $productQuery->find($this->positiveInteger($row, 'product_id', $index));
            $siteProduct = $siteProductQuery->find($this->positiveInteger($row, 'site_product_id', $index));
            $evidence = $evidenceQuery->find($this->positiveInteger($row, 'price_evidence_id', $index));
            $url = $urlQuery->find($this->positiveInteger($row, 'site_url_id', $index));
            if ($product === null || $siteProduct === null || $evidence === null || $url === null
                || $product->external_id !== $externalId
                || $siteProduct->site_id !== $site->id || $siteProduct->product_id !== $product->id
                || $siteProduct->price !== null
                || $evidence->site_id !== $site->id || $evidence->site_product_id !== $siteProduct->id || $evidence->is_current
                || $url->site_id !== $site->id || $url->target_type !== 'product' || $url->target_id !== $siteProduct->id
                || $url->path !== $row['path']) {
                throw new RuntimeException("Rollback row {$index} no longer matches the exact retired state.");
            }
            if (SiteProductPriceEvidence::query()->where('site_product_id', $siteProduct->id)->where('is_current', true)->exists()) {
                throw new RuntimeException("Rollback row {$index} refuses to supersede newer current price evidence.");
            }
            $this->assertStateHash($row, 'product_state_sha256', $this->productState($product), $index);
            $this->assertStateHash($row, 'retired_site_product_state_sha256', $this->siteProductState($siteProduct), $index);
            $this->assertStateHash($row, 'retired_evidence_state_sha256', $this->evidenceState($evidence), $index);
            $this->assertStateHash($row, 'url_state_sha256', $this->urlState($url), $index);
            $restorePrice = $this->normalizeMoney($row['restore_price'] ?? null, "Rollback row {$index} restore_price");
            if (! $this->moneyEquals($restorePrice, $evidence->calculated_price)) {
                throw new RuntimeException("Rollback row {$index} restore price no longer matches the pinned evidence.");
            }
            $plans[] = compact('row', 'product', 'siteProduct', 'evidence', 'url') + [
                'site_product' => $siteProduct,
                'restore_price' => $restorePrice,
            ];
        }

        return $plans;
    }

    private function validateSourceCohort(mixed $source): void
    {
        if (! is_array($source)) {
            throw new RuntimeException('Manifest source_cohort must be an object.');
        }
        $this->assertExactKeys($source, ['path', 'sha256'], 'Manifest source_cohort');
        $path = $this->requiredString($source, 'path', 'Manifest source_cohort');
        $hash = (string) ($source['sha256'] ?? '');
        $resolved = collect([
            $path,
            base_path($path),
            base_path('../'.ltrim(str_replace('\\', '/', $path), '/')),
            storage_path($path),
        ])->first(fn (string $candidate): bool => is_file($candidate));
        if (! preg_match('/^[a-f0-9]{64}$/', $hash)
            || ! is_string($resolved)
            || ! hash_equals($hash, strtolower((string) hash_file('sha256', $resolved)))) {
            throw new RuntimeException('Pinned source cohort file is missing or its SHA-256 changed.');
        }
    }

    /**
     * @param  list<array{row: array<string,mixed>, product: Product, site_product: SiteProduct, evidence: SiteProductPriceEvidence, url: SiteUrl}>  $plans
     * @return array<string, mixed>
     */
    private function buildRollbackManifest(Site $site, string $sourceFile, array $plans): array
    {
        return [
            'schema' => self::ROLLBACK_SCHEMA,
            'site_key' => $site->key,
            'source_manifest_sha256' => strtolower((string) hash_file('sha256', $sourceFile)),
            'products' => array_map(fn (array $plan): array => [
                'external_id' => $plan['product']->external_id,
                'product_id' => $plan['product']->id,
                'site_product_id' => $plan['site_product']->id,
                'price_evidence_id' => $plan['evidence']->id,
                'site_url_id' => $plan['url']->id,
                'path' => $plan['url']->path,
                'restore_price' => $this->normalizeMoney($plan['site_product']->price, 'visible price'),
                'restore_evidence_current' => true,
                'retired_site_product_state_sha256' => $this->hashState([
                    ...$this->siteProductState($plan['site_product']),
                    'price' => null,
                ]),
                'retired_evidence_state_sha256' => $this->hashState([
                    ...$this->evidenceState($plan['evidence']),
                    'is_current' => false,
                ]),
                'product_state_sha256' => $this->hashState($this->productState($plan['product'])),
                'url_state_sha256' => $this->hashState($this->urlState($plan['url'])),
            ], $plans),
        ];
    }

    /**
     * @param  list<array{row: array<string,mixed>, product: Product, site_product: SiteProduct, evidence: SiteProductPriceEvidence, url: SiteUrl}>  $plans
     * @param  array<string, mixed>  $summary
     */
    private function recordAudit(Site $site, string $file, array $plans, array $summary, bool $rollback): void
    {
        $run = ImportRun::query()->create([
            'source' => ($rollback ? 'stale_visible_price_rollback:' : 'stale_visible_price_retirement:').$site->key,
            'source_file' => basename($file),
            'status' => 'completed',
            'total_records' => count($plans),
            'processed_records' => count($plans),
            'failed_records' => 0,
            'summary' => $summary + ['manifest_sha256' => strtolower((string) hash_file('sha256', $file))],
            'started_at' => now(),
            'finished_at' => now(),
        ]);
        foreach ($plans as $index => $plan) {
            StagedImportRecord::query()->create([
                'import_run_id' => $run->id,
                'row_number' => $index + 1,
                'entity_type' => 'site_product_stale_visible_price',
                'external_id' => $plan['product']->external_id,
                'payload' => $plan['row'],
                'normalized_payload' => [
                    'site_product_id' => $plan['site_product']->id,
                    'price_evidence_id' => $plan['evidence']->id,
                    'path' => $plan['url']->path,
                    'price' => $rollback ? $plan['restore_price'] : null,
                    'evidence_is_current' => $rollback,
                ],
                'validation_errors' => [],
                'status' => $rollback ? 'restored' : 'retired',
                'review_note' => $rollback
                    ? 'Restored exact manifest-pinned price and current evidence flag.'
                    : 'Retired stale visible price; publication, indexability, availability, and content were unchanged.',
                'published_product_id' => $plan['product']->id,
                'published_site_id' => $site->id,
                'publication_snapshot' => [
                    'publication_changes' => 0,
                    'indexability_changes' => 0,
                    'availability_changes' => 0,
                    'content_changes' => 0,
                ],
            ]);
        }
    }

    /** @return list<string> */
    private function revalidationPaths(SiteProduct $siteProduct, SiteUrl $url): array
    {
        $categoryIds = $siteProduct->categories()->pluck('site_categories.id')->map(fn (mixed $id): int => (int) $id)->all();

        return array_values(array_unique([
            $url->path,
            ...SiteCategory::revalidationPaths($siteProduct->site_id, $categoryIds),
            '/catalog',
        ]));
    }

    /** @return array<string, mixed> */
    private function readManifest(string $file): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Stale-price manifest is not readable.');
        }
        $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest)) {
            throw new RuntimeException('Stale-price manifest must be a JSON object.');
        }

        return $manifest;
    }

    private function rollbackOutputPath(string $manifestPath): string
    {
        $option = $this->option('rollback-output');
        if (is_string($option) && trim($option) !== '') {
            return trim($option);
        }

        return (preg_replace('/\.json$/i', '', $manifestPath) ?: $manifestPath).'.rollback.json';
    }

    /** @param array<string, mixed> $value */
    private function writeJsonAtomically(string $path, array $value): void
    {
        $directory = dirname($path);
        if (! is_dir($directory) || ! is_writable($directory)) {
            throw new RuntimeException('Rollback manifest directory is not writable.');
        }
        $temporary = $path.'.tmp.'.bin2hex(random_bytes(6));
        $bytes = file_put_contents($temporary, json_encode($value, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES).PHP_EOL, LOCK_EX);
        if ($bytes === false || ! rename($temporary, $path)) {
            @unlink($temporary);
            throw new RuntimeException('Rollback manifest could not be written atomically.');
        }
    }

    /** @param array<string, mixed> $row */
    private function assertStateHash(array $row, string $field, array $state, int $index): void
    {
        $expected = (string) ($row[$field] ?? '');
        if (! preg_match('/^[a-f0-9]{64}$/', $expected) || ! hash_equals($expected, $this->hashState($state))) {
            throw new RuntimeException("Retirement row {$index} {$field} does not match current state.");
        }
    }

    /** @param array<string, mixed> $state */
    private function hashState(array $state): string
    {
        return hash('sha256', json_encode($this->canonicalize($state), JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    }

    private function canonicalize(mixed $value): mixed
    {
        if (! is_array($value)) {
            return $value;
        }
        if (! array_is_list($value)) {
            ksort($value);
        }
        foreach ($value as $key => $child) {
            $value[$key] = $this->canonicalize($child);
        }

        return $value;
    }

    /** @return array<string, mixed> */
    private function productState(Product $product): array
    {
        return [
            'id' => $product->id,
            'external_id' => $product->external_id,
            'sku' => $product->sku,
            'manufacturer' => $product->manufacturer,
            'mpn' => $product->mpn,
            'slug' => $product->slug,
            'name' => $product->name,
            'short_description' => $product->short_description,
            'technical_attributes' => $product->technical_attributes,
            'status' => $product->status,
        ];
    }

    /** @return array<string, mixed> */
    private function siteProductState(SiteProduct $siteProduct): array
    {
        return [
            'id' => $siteProduct->id,
            'site_id' => $siteProduct->site_id,
            'product_id' => $siteProduct->product_id,
            'slug' => $siteProduct->slug,
            'price' => $siteProduct->price === null ? null : $this->normalizeMoney($siteProduct->price, 'price'),
            'availability' => $siteProduct->availability,
            'is_published' => (bool) $siteProduct->is_published,
            'seo' => $siteProduct->seo,
            'sort_order' => $siteProduct->sort_order,
        ];
    }

    /** @return array<string, mixed> */
    private function evidenceState(SiteProductPriceEvidence $evidence): array
    {
        return [
            'id' => $evidence->id,
            'site_id' => $evidence->site_id,
            'site_product_id' => $evidence->site_product_id,
            'source' => $evidence->source,
            'source_price' => number_format((float) $evidence->source_price, 4, '.', ''),
            'multiplier' => number_format((float) $evidence->multiplier, 4, '.', ''),
            'calculated_price' => $this->normalizeMoney($evidence->calculated_price, 'calculated_price'),
            'currency' => $evidence->currency,
            'price_type' => $evidence->price_type,
            'source_external_id' => $evidence->source_external_id,
            'source_reference' => $evidence->source_reference,
            'observed_at' => $evidence->observed_at?->toAtomString(),
            'evidence_key' => $evidence->evidence_key,
            'evidence' => $evidence->evidence,
            'is_current' => (bool) $evidence->is_current,
        ];
    }

    /** @return array<string, mixed> */
    private function urlState(SiteUrl $url): array
    {
        return [
            'id' => $url->id,
            'site_id' => $url->site_id,
            'path' => $url->path,
            'locale' => $url->locale,
            'target_type' => $url->target_type,
            'target_id' => $url->target_id,
            'is_indexable' => (bool) $url->is_indexable,
        ];
    }

    private function moneyEquals(mixed $left, mixed $right): bool
    {
        try {
            return $this->normalizeMoney($left, 'price') === $this->normalizeMoney($right, 'price');
        } catch (RuntimeException) {
            return false;
        }
    }

    private function normalizeMoney(mixed $value, string $label): string
    {
        if (! is_int($value) && ! is_float($value) && ! is_string($value)) {
            throw new RuntimeException("{$label} must be numeric.");
        }
        $normalized = filter_var($value, FILTER_VALIDATE_FLOAT);
        if ($normalized === false || $normalized < 0) {
            throw new RuntimeException("{$label} must be a non-negative number.");
        }

        return number_format((float) $normalized, 2, '.', '');
    }

    /** @param array<string, mixed> $row */
    private function requiredString(array $row, string $field, string $label): string
    {
        if (! is_string($row[$field] ?? null) || trim($row[$field]) === '') {
            throw new RuntimeException("{$label} requires {$field}.");
        }

        return trim($row[$field]);
    }

    /** @param array<string, mixed> $row */
    private function positiveInteger(array $row, string $field, int $index): int
    {
        $value = $row[$field] ?? null;
        if ((! is_int($value) && ! (is_string($value) && ctype_digit($value))) || (int) $value < 1) {
            throw new RuntimeException("Manifest row {$index} requires positive integer {$field}.");
        }

        return (int) $value;
    }

    /** @param array<string, mixed> $value
     * @param  list<string>  $expected
     */
    private function assertExactKeys(array $value, array $expected, string $label): void
    {
        $actual = array_keys($value);
        sort($actual);
        sort($expected);
        if ($actual !== $expected) {
            throw new RuntimeException("{$label} keys do not match the fail-closed schema.");
        }
    }
}
