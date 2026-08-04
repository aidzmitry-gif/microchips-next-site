<?php

namespace App\Console\Commands;

use App\Domain\Seo\ProductReleaseState;
use App\Domain\Seo\SiteIndexabilityPublisher;
use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Events\SiteContentChanged;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use Throwable;

/** Release a hash-pinned, already-published product cohort without editing content or commercial facts. */
class ReleasePinnedProductCohort extends Command
{
    private const RELEASE_SCHEMA = 'rb_product_indexability_release_v1';

    private const ROLLBACK_SCHEMA = 'rb_product_indexability_rollback_v1';

    private const MIN_DESCRIPTION_CHARACTERS = 120;

    private ProductReleaseState $releaseState;

    protected $signature = 'seo:release-product-cohort
                            {site : Site key}
                            {file : Hash-pinned JSON release or rollback manifest}
                            {--apply : Persist the indexability change; default is dry-run}
                            {--rollback : Consume a rollback manifest and restore noindex}
                            {--rollback-output= : File written before an apply; defaults beside the release manifest}';

    protected $description = 'Atomically release or roll back a manifest-pinned product cohort through the shared SEO release auditor';

    public function handle(SiteIndexabilityPublisher $publisher, SiteSeoReleaseAuditor $auditor, ProductReleaseState $releaseState): int
    {
        $this->releaseState = $releaseState;
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
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
            DB::beginTransaction();
            try {
                if ($rollback) {
                    $result = $this->rollback($site, $manifest, $apply, $auditor, $file);
                } else {
                    $result = $this->release($site, $manifest, $apply, $publisher, $file);
                }

                $apply ? DB::commit() : DB::rollBack();
            } catch (Throwable $error) {
                if (DB::transactionLevel() > 0) {
                    DB::rollBack();
                }
                throw $error;
            }
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

        return self::SUCCESS;
    }

    /** @param array<string, mixed> $manifest
     * @return array<string, mixed>
     */
    private function release(Site $site, array $manifest, bool $apply, SiteIndexabilityPublisher $publisher, string $file): array
    {
        $items = $this->validateReleaseManifest($site, $manifest);
        $rollbackPath = null;
        if ($apply) {
            $rollbackPath = $this->rollbackOutputPath($file);
        }

        // Running the real publisher inside this outer transaction makes the
        // dry run exercise exactly the same auditor and SQL path. The outer
        // rollback guarantees zero persisted changes and suppresses after-
        // commit revalidation events.
        $report = $publisher->promoteMany(array_column($items, 'url'));
        if ($rollbackPath !== null) {
            // The publisher has passed, but the surrounding transaction has
            // not committed yet. A write failure therefore still restores the
            // complete cohort to noindex; a failed audit never leaves a stale
            // rollback artefact for a change that did not happen.
            $this->writeJsonAtomically($rollbackPath, $this->buildRollbackManifest($site, $items));
        }
        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'operation' => 'release',
            'site' => $site->key,
            'records' => count($items),
            'indexable_urls' => count($items),
            'seo_audit_passed' => $report['passed'],
            'seo_audit_summary' => $report['summary'],
            'rollback_manifest' => $rollbackPath,
        ];

        if ($apply) {
            $this->recordAudit($site, $file, $items, $summary, 'released_indexable');
        }

        return $summary;
    }

    /** @param array<string, mixed> $manifest
     * @return array<string, mixed>
     */
    private function rollback(Site $site, array $manifest, bool $apply, SiteSeoReleaseAuditor $auditor, string $file): array
    {
        $items = $this->validateRollbackManifest($site, $manifest);
        $paths = [];
        foreach ($items as $item) {
            /** @var SiteUrl $url */
            $url = $item['url'];
            /** @var SiteSeo $seo */
            $seo = $item['seo'];
            $url->forceFill(['is_indexable' => false])->saveQuietly();
            $seo->forceFill(['is_indexable' => false])->saveQuietly();
            $paths[] = $url->path;
        }

        $report = $auditor->audit($site);
        if (! $report['passed']) {
            $codes = implode(', ', array_unique(array_column($report['issues'], 'code')));
            throw new RuntimeException("Rollback leaves the site release audit failing: {$codes}");
        }
        SiteContentChanged::dispatch($site, array_values(array_unique([...$paths, '/sitemap.xml'])));

        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'operation' => 'rollback',
            'site' => $site->key,
            'records' => count($items),
            'indexable_urls' => 0,
            'seo_audit_passed' => true,
            'seo_audit_summary' => $report['summary'],
        ];
        if ($apply) {
            $this->recordAudit($site, $file, $items, $summary, 'restored_noindex');
        }

        return $summary;
    }

    /** @param array<string, mixed> $manifest
     * @return list<array{row: array<string, mixed>, product: Product, site_product: SiteProduct, url: SiteUrl, seo: SiteSeo, media: ProductMedia}>
     */
    private function validateReleaseManifest(Site $site, array $manifest): array
    {
        $this->validateEnvelope($site, $manifest, self::RELEASE_SCHEMA, requireCommercialPin: true);
        $seen = [];
        $items = [];
        foreach ($manifest['products'] as $index => $row) {
            if (! is_array($row)) {
                throw new RuntimeException("Release row {$index} must be an object.");
            }
            $this->assertExactKeys($row, [
                'external_id', 'product_id', 'site_product_id', 'site_url_id', 'site_seo_id', 'path',
                'product_state_sha256', 'site_product_state_sha256', 'url_state_sha256', 'seo_state_sha256',
                'verified_media',
            ], "Release row {$index}");
            $externalId = $this->requiredString($row, 'external_id', "Release row {$index}");
            if (isset($seen[$externalId])) {
                throw new RuntimeException("Release manifest repeats external_id {$externalId}.");
            }
            $seen[$externalId] = true;

            $product = Product::query()->lockForUpdate()->find($this->positiveInteger($row, 'product_id', $index));
            $siteProduct = SiteProduct::query()->lockForUpdate()->find($this->positiveInteger($row, 'site_product_id', $index));
            $url = SiteUrl::query()->lockForUpdate()->find($this->positiveInteger($row, 'site_url_id', $index));
            $seo = SiteSeo::query()->lockForUpdate()->find($this->positiveInteger($row, 'site_seo_id', $index));
            if ($product === null || $siteProduct === null || $url === null || $seo === null) {
                throw new RuntimeException("Release row {$index} references a missing pinned record.");
            }
            if ($product->external_id !== $externalId
                || $siteProduct->site_id !== $site->id || $siteProduct->product_id !== $product->id || ! $siteProduct->is_published
                || $url->site_id !== $site->id || $url->target_type !== 'product' || $url->target_id !== $siteProduct->id || $url->is_indexable
                || $url->locale !== $site->default_locale || $url->path !== $row['path']
                || $seo->site_id !== $site->id || $seo->locale !== $site->default_locale
                || $seo->resource_type !== 'product' || $seo->resource_id !== $siteProduct->id || $seo->is_indexable
                || $seo->canonical_path !== $url->path) {
                throw new RuntimeException("Release row {$index} is not the current published, self-canonical noindex product resource.");
            }
            if (blank($product->manufacturer) || blank($product->mpn)) {
                throw new RuntimeException("Product {$externalId} requires a current manufacturer and MPN identity.");
            }
            if (mb_strlen(trim((string) $product->short_description)) < self::MIN_DESCRIPTION_CHARACTERS) {
                throw new RuntimeException("Product {$externalId} requires at least ".self::MIN_DESCRIPTION_CHARACTERS.' description characters.');
            }

            $this->assertHash($row, 'product_state_sha256', $this->productState($product), $index);
            $this->assertHash($row, 'site_product_state_sha256', $this->siteProductState($siteProduct), $index);
            $this->assertHash($row, 'url_state_sha256', $this->urlState($url), $index);
            $this->assertHash($row, 'seo_state_sha256', $this->seoState($seo), $index);
            $media = $this->validatePinnedMedia($product, $row['verified_media'], $index);
            $items[] = compact('row', 'product', 'url', 'seo', 'media') + ['site_product' => $siteProduct];
        }

        return $items;
    }

    /** @param array<string, mixed> $manifest
     * @return list<array{row: array<string, mixed>, url: SiteUrl, seo: SiteSeo}>
     */
    private function validateRollbackManifest(Site $site, array $manifest): array
    {
        $this->validateEnvelope($site, $manifest, self::ROLLBACK_SCHEMA, requireCommercialPin: false);
        $seen = [];
        $items = [];
        foreach ($manifest['products'] as $index => $row) {
            if (! is_array($row)) {
                throw new RuntimeException("Rollback row {$index} must be an object.");
            }
            $this->assertExactKeys($row, [
                'external_id', 'site_product_id', 'site_url_id', 'site_seo_id', 'path',
                'restore_url_indexable', 'restore_seo_indexable',
            ], "Rollback row {$index}");
            $externalId = $this->requiredString($row, 'external_id', "Rollback row {$index}");
            if (isset($seen[$externalId]) || $row['restore_url_indexable'] !== false || $row['restore_seo_indexable'] !== false) {
                throw new RuntimeException("Rollback row {$index} is duplicated or does not restore noindex.");
            }
            $seen[$externalId] = true;
            $siteProduct = SiteProduct::query()->where('site_id', $site->id)->find($this->positiveInteger($row, 'site_product_id', $index));
            $product = $siteProduct?->product()->first();
            $url = SiteUrl::query()->lockForUpdate()->find($this->positiveInteger($row, 'site_url_id', $index));
            $seo = SiteSeo::query()->lockForUpdate()->find($this->positiveInteger($row, 'site_seo_id', $index));
            if ($product === null || $product->external_id !== $externalId || $url === null || $seo === null
                || $url->site_id !== $site->id || $url->target_type !== 'product' || $url->target_id !== $siteProduct->id
                || $url->path !== $row['path'] || ! $url->is_indexable
                || $seo->site_id !== $site->id || $seo->resource_type !== 'product' || $seo->resource_id !== $siteProduct->id
                || $seo->locale !== ($url->locale ?: $site->default_locale) || ! $seo->is_indexable) {
                throw new RuntimeException("Rollback row {$index} no longer identifies the released URL and SEO pair.");
            }
            $items[] = compact('row', 'url', 'seo');
        }

        return $items;
    }

    /** @param array<string, mixed> $manifest */
    private function validateEnvelope(Site $site, array $manifest, string $schema, bool $requireCommercialPin): void
    {
        $required = ['schema', 'site_key', 'locale', 'products'];
        if ($requireCommercialPin) {
            $required = [...$required, 'commercial_profile_sha256', 'root_state_sha256', 'source_cohort_file', 'source_cohort_sha256', 'source_wave'];
        }
        $this->assertExactKeys($manifest, $required, 'Manifest');
        if (($manifest['schema'] ?? null) !== $schema || ($manifest['site_key'] ?? null) !== $site->key
            || ($manifest['locale'] ?? null) !== $site->default_locale
            || ! is_array($manifest['products'] ?? null) || $manifest['products'] === []) {
            throw new RuntimeException('Manifest schema, site, locale, or non-empty products collection is invalid.');
        }
        if ($requireCommercialPin) {
            if (($manifest['source_wave'] ?? null) !== 'wave249a_first_indexable_b2b_cohort') {
                throw new RuntimeException('Release manifest must originate from the strict Wave249A indexable B2B cohort.');
            }
            $sourceFile = $this->requiredString($manifest, 'source_cohort_file', 'Manifest');
            $sourceHash = $this->requiredString($manifest, 'source_cohort_sha256', 'Manifest');
            if (basename($sourceFile) !== $sourceFile || preg_match('/^[a-f0-9]{64}$/', $sourceHash) !== 1) {
                throw new RuntimeException('Release manifest source cohort requires a local basename and lowercase SHA-256 pin.');
            }
            $sourcePath = dirname((string) $this->argument('file')).DIRECTORY_SEPARATOR.$sourceFile;
            if (! is_file($sourcePath) || ! hash_equals($sourceHash, strtolower((string) hash_file('sha256', $sourcePath)))) {
                throw new RuntimeException('Strict Wave249A source cohort file is missing or does not match its SHA-256 pin.');
            }
            $expected = $this->hashState($this->commercialProfileState($site));
            if (! hash_equals($expected, (string) $manifest['commercial_profile_sha256'])) {
                throw new RuntimeException('Published verified commercial profile changed after the release manifest was built.');
            }
            $rootExpected = $this->hashState($this->rootReleaseState($site));
            if (! hash_equals($rootExpected, (string) $manifest['root_state_sha256'])) {
                throw new RuntimeException('Indexable non-demo root state changed after the release manifest was built.');
            }
        }
    }

    private function validatePinnedMedia(Product $product, mixed $pin, int $index): ProductMedia
    {
        if (! is_array($pin)) {
            throw new RuntimeException("Release row {$index} requires one pinned verified_media object.");
        }
        $this->assertExactKeys($pin, ['media_id', 'storage_path', 'content_sha256', 'rights_basis', 'verified_at'], "Release row {$index} media");
        $media = ProductMedia::query()->storefrontReady()->lockForUpdate()->find($this->positiveInteger($pin, 'media_id', $index));
        if ($media === null || $media->product_id !== $product->id
            || $media->storage_path !== $pin['storage_path'] || $media->content_sha256 !== $pin['content_sha256']
            || $media->rights_basis !== $pin['rights_basis'] || $media->verified_at?->toAtomString() !== $pin['verified_at']) {
            throw new RuntimeException("Release row {$index} media is not the current storefront-ready verified asset.");
        }
        $path = (string) $media->storage_path;
        $disk = Storage::disk('public');
        $absolute = $disk->path($path);
        if (! $disk->exists($path) || ! is_file($absolute)
            || ! hash_equals((string) $media->content_sha256, strtolower((string) hash_file('sha256', $absolute)))) {
            throw new RuntimeException("Release row {$index} verified media bytes do not match the stored SHA-256 pin.");
        }

        return $media;
    }

    /** @param list<array<string, mixed>> $items
     * @param  array<string, mixed>  $source
     * @return array<string, mixed>
     */
    private function buildRollbackManifest(Site $site, array $items): array
    {
        return [
            'schema' => self::ROLLBACK_SCHEMA,
            'site_key' => $site->key,
            'locale' => $site->default_locale,
            'products' => array_map(static fn (array $item): array => [
                'external_id' => $item['product']->external_id,
                'site_product_id' => $item['site_product']->id,
                'site_url_id' => $item['url']->id,
                'site_seo_id' => $item['seo']->id,
                'path' => $item['url']->path,
                'restore_url_indexable' => false,
                'restore_seo_indexable' => false,
            ], $items),
        ];
    }

    /** @param list<array<string, mixed>> $items
     * @param  array<string, mixed>  $summary
     */
    private function recordAudit(Site $site, string $file, array $items, array $summary, string $status): void
    {
        $run = ImportRun::query()->create([
            'source' => 'seo_product_cohort:'.$site->key,
            'source_file' => basename($file),
            'status' => 'completed',
            'total_records' => count($items),
            'processed_records' => count($items),
            'summary' => $summary + ['manifest_sha256' => hash_file('sha256', $file)],
            'started_at' => now(),
            'finished_at' => now(),
        ]);
        foreach ($items as $index => $item) {
            StagedImportRecord::query()->create([
                'import_run_id' => $run->id,
                'row_number' => $index + 1,
                'entity_type' => 'product_indexability_release',
                'external_id' => $item['row']['external_id'],
                'payload' => $item['row'],
                'normalized_payload' => [
                    'site_url_id' => $item['url']->id,
                    'site_seo_id' => $item['seo']->id,
                    'path' => $item['url']->path,
                    'is_indexable' => $status === 'released_indexable',
                ],
                'status' => $status,
            ]);
        }
    }

    /** @return array<string, mixed> */
    private function readManifest(string $file): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Product cohort manifest is not readable.');
        }
        $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest)) {
            throw new RuntimeException('Product cohort manifest must be a JSON object.');
        }

        return $manifest;
    }

    private function rollbackOutputPath(string $manifestPath): string
    {
        $option = $this->option('rollback-output');
        if (is_string($option) && trim($option) !== '') {
            return $option;
        }

        return preg_replace('/\.json$/i', '', $manifestPath).'.rollback.json';
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

    /** @param array<string, mixed> $row
     * @param  array<string, mixed>  $state
     */
    private function assertHash(array $row, string $field, array $state, int $index): void
    {
        $pin = $row[$field] ?? null;
        if (! is_string($pin) || preg_match('/^[a-f0-9]{64}$/', $pin) !== 1 || ! hash_equals($this->hashState($state), $pin)) {
            throw new RuntimeException("Release row {$index} current {$field} does not match its manifest pin.");
        }
    }

    /** @param array<string, mixed> $actual
     * @param  list<string>  $expected
     */
    private function assertExactKeys(array $actual, array $expected, string $label): void
    {
        $actualKeys = array_keys($actual);
        sort($actualKeys);
        sort($expected);
        if ($actualKeys !== $expected) {
            throw new RuntimeException("{$label} fields must be exactly: ".implode(', ', $expected).'.');
        }
    }

    /** @return array<string, mixed> */
    private function productState(Product $product): array
    {
        return $this->releaseState->product($product);
    }

    /** @return array<string, mixed> */
    private function siteProductState(SiteProduct $product): array
    {
        return $this->releaseState->siteProduct($product);
    }

    /** @return array<string, mixed> */
    private function urlState(SiteUrl $url): array
    {
        return $this->releaseState->url($url);
    }

    /** @return array<string, mixed> */
    private function seoState(SiteSeo $seo): array
    {
        return $this->releaseState->seo($seo);
    }

    /** @return array<string, mixed> */
    private function commercialProfileState(Site $site): array
    {
        return $this->releaseState->commercialProfile($site);
    }

    /**
     * Frontend robots.ts emits `Disallow: /` unless the resolved root SEO is
     * indexable. A product cohort must therefore never be released ahead of
     * the real home page, even if every individual product passes SEO audit.
     *
     * @return array<string, mixed>
     */
    private function rootReleaseState(Site $site): array
    {
        return $this->releaseState->root($site);
    }

    /** @param array<string, mixed> $state */
    private function hashState(array $state): string
    {
        return $this->releaseState->hash($state);
    }
}
