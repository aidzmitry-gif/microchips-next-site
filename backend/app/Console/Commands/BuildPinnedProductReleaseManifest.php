<?php

namespace App\Console\Commands;

use App\Domain\Seo\ProductReleaseState;
use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use Throwable;

/** Convert the strict read-only Wave249A cohort into the exact live-state release contract. */
class BuildPinnedProductReleaseManifest extends Command
{
    protected $signature = 'seo:build-product-release-manifest
                            {site : Site key}
                            {cohort : Strict Wave249A cohort JSON}
                            {output : Release manifest JSON to create}';

    protected $description = 'Build a hash-pinned product release manifest from strict Wave249A output and current live records';

    public function handle(ProductReleaseState $state): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $cohortPath = (string) $this->argument('cohort');
            $outputPath = (string) $this->argument('output');
            $cohort = $this->readCohort($site, $cohortPath);
            $cohortDirectory = realpath(dirname($cohortPath));
            $outputDirectory = realpath(dirname($outputPath));
            if ($cohortDirectory === false || $outputDirectory === false || $cohortDirectory !== $outputDirectory) {
                throw new RuntimeException('Release manifest must be written beside its hash-pinned Wave249A cohort file.');
            }
            if (file_exists($outputPath)) {
                throw new RuntimeException('Release manifest output already exists; rebuild to a new file instead of overwriting evidence.');
            }

            // These calls deliberately fail before a manifest can exist while
            // global robots or verified regional ownership remains unready.
            $commercialHash = $state->hash($state->commercialProfile($site));
            $rootHash = $state->hash($state->root($site));
            $products = [];
            foreach ($cohort['records'] as $index => $row) {
                $products[] = $this->buildRow($site, $state, $row, $index);
            }

            $manifest = [
                'schema' => 'rb_product_indexability_release_v1',
                'site_key' => $site->key,
                'locale' => $site->default_locale,
                'source_wave' => 'wave249a_first_indexable_b2b_cohort',
                'source_cohort_file' => basename($cohortPath),
                'source_cohort_sha256' => strtolower((string) hash_file('sha256', $cohortPath)),
                'commercial_profile_sha256' => $commercialHash,
                'root_state_sha256' => $rootHash,
                'products' => $products,
            ];
            $this->writeJsonAtomically($outputPath, $manifest);
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode([
            'mode' => 'read_only_live_validation',
            'records' => count($products),
            'database_mutations' => 0,
            'output' => $outputPath,
            'manifest_sha256' => hash_file('sha256', $outputPath),
        ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

        return self::SUCCESS;
    }

    /** @return array<string, mixed> */
    private function readCohort(Site $site, string $path): array
    {
        if (! is_file($path) || ! is_readable($path)) {
            throw new RuntimeException('Wave249A cohort JSON is not readable.');
        }
        $cohort = json_decode((string) file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($cohort)
            || ($cohort['schema_version'] ?? null) !== 1
            || ($cohort['wave'] ?? null) !== 'wave249a_first_indexable_b2b_cohort'
            || ($cohort['mode'] ?? null) !== 'live_database_read_only'
            || ($cohort['site_key'] ?? null) !== $site->key
            || ! is_array($cohort['records'] ?? null)
            || $cohort['records'] === []
            || (int) ($cohort['selected'] ?? -1) !== count($cohort['records'])) {
            throw new RuntimeException('Cohort must be a non-empty strict live Wave249A result with an exact selected count.');
        }
        $quality = $cohort['quality'] ?? null;
        $count = count($cohort['records']);
        if (! is_array($quality)
            || (int) ($quality['selected_unique_external_ids'] ?? -1) !== $count
            || (int) ($quality['selected_unique_identity_pairs'] ?? -1) !== $count
            || (int) ($quality['selected_unique_canonical_paths'] ?? -1) !== $count
            || (int) ($quality['selected_with_verified_media'] ?? -1) !== $count
            || (int) ($quality['selected_with_valid_source_provenance'] ?? -1) !== $count
            || (int) ($quality['selected_open_conflicts'] ?? -1) !== 0
            || (int) ($quality['selected_stale_or_unpinned_visible_prices'] ?? -1) !== 0
            || (int) ($quality['database_mutations'] ?? -1) !== 0) {
            throw new RuntimeException('Wave249A cohort quality counters do not prove a safe selected set.');
        }

        return $cohort;
    }

    /** @param array<string, mixed> $row
     * @return array<string, mixed>
     */
    private function buildRow(Site $site, ProductReleaseState $state, array $row, int $index): array
    {
        foreach (['product_external_id', 'product_id', 'site_product_id', 'canonical_path', 'verified_media_ids', 'release_decision'] as $field) {
            if (! is_string($row[$field] ?? null) || trim($row[$field]) === '') {
                throw new RuntimeException("Wave249A row {$index} requires {$field}.");
            }
        }
        if ($row['release_decision'] !== 'READY_FOR_BOUNDED_INDEXABLE_RELEASE') {
            throw new RuntimeException("Wave249A row {$index} is not release-ready.");
        }
        $productId = $this->positiveInteger($row['product_id'], "Wave249A row {$index} product_id");
        $siteProductId = $this->positiveInteger($row['site_product_id'], "Wave249A row {$index} site_product_id");
        $product = Product::query()->find($productId);
        $siteProduct = SiteProduct::query()->where('site_id', $site->id)->find($siteProductId);
        $url = SiteUrl::query()->where('site_id', $site->id)->where('target_type', 'product')->where('target_id', $siteProductId)->sole();
        $seo = SiteSeo::query()->where('site_id', $site->id)->where('locale', $site->default_locale)
            ->where('resource_type', 'product')->where('resource_id', $siteProductId)->sole();
        if ($product === null || $siteProduct === null || $siteProduct->product_id !== $product->id
            || $product->external_id !== trim($row['product_external_id']) || ! $siteProduct->is_published
            || $url->path !== trim($row['canonical_path']) || $url->is_indexable
            || $seo->canonical_path !== $url->path || $seo->is_indexable) {
            throw new RuntimeException("Wave249A row {$index} drifted from its live published noindex URL/SEO identity.");
        }

        $mediaIds = json_decode($row['verified_media_ids'], true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($mediaIds) || $mediaIds === []) {
            throw new RuntimeException("Wave249A row {$index} has no verified media IDs.");
        }
        $mediaIds = array_map(fn (mixed $id): int => $this->positiveInteger($id, "Wave249A row {$index} media ID"), $mediaIds);
        $media = ProductMedia::query()->storefrontReady()
            ->where('product_id', $product->id)->whereIn('id', $mediaIds)
            ->orderBy('sort_order')->orderBy('id')->first();
        if ($media === null || ! in_array($media->id, $mediaIds, true)) {
            throw new RuntimeException("Wave249A row {$index} no longer has its pinned storefront-ready media.");
        }
        $asset = Storage::disk('public')->path((string) $media->storage_path);
        if (! Storage::disk('public')->exists((string) $media->storage_path) || ! is_file($asset)
            || ! hash_equals((string) $media->content_sha256, strtolower((string) hash_file('sha256', $asset)))) {
            throw new RuntimeException("Wave249A row {$index} verified media bytes fail SHA-256 validation.");
        }

        return [
            'external_id' => $product->external_id,
            'product_id' => $product->id,
            'site_product_id' => $siteProduct->id,
            'site_url_id' => $url->id,
            'site_seo_id' => $seo->id,
            'path' => $url->path,
            'product_state_sha256' => $state->hash($state->product($product)),
            'site_product_state_sha256' => $state->hash($state->siteProduct($siteProduct)),
            'url_state_sha256' => $state->hash($state->url($url)),
            'seo_state_sha256' => $state->hash($state->seo($seo)),
            'verified_media' => [
                'media_id' => $media->id,
                'storage_path' => $media->storage_path,
                'content_sha256' => $media->content_sha256,
                'rights_basis' => $media->rights_basis,
                'verified_at' => $media->verified_at?->toAtomString(),
            ],
        ];
    }

    private function positiveInteger(mixed $value, string $label): int
    {
        if ((! is_int($value) && ! (is_string($value) && ctype_digit($value))) || (int) $value < 1) {
            throw new RuntimeException("{$label} must be a positive integer.");
        }

        return (int) $value;
    }

    /** @param array<string, mixed> $manifest */
    private function writeJsonAtomically(string $path, array $manifest): void
    {
        $directory = dirname($path);
        if (! is_dir($directory) || ! is_writable($directory)) {
            throw new RuntimeException('Release manifest output directory is not writable.');
        }
        $temporary = $path.'.tmp.'.bin2hex(random_bytes(6));
        $written = file_put_contents($temporary, json_encode($manifest, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES).PHP_EOL, LOCK_EX);
        if ($written === false || ! rename($temporary, $path)) {
            @unlink($temporary);
            throw new RuntimeException('Release manifest could not be written atomically.');
        }
    }
}
