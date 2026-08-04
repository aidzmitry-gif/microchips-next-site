<?php

namespace App\Console\Commands;

use App\Domain\Imports\ProductIdentity;
use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use Throwable;

/** Imports exact-model source images only after rights and visual verification. */
class ImportVerifiedSourceImages extends Command
{
    protected $signature = 'media:import-verified-source-images
                            {site : Site key}
                            {file : JSON verified source-image manifest}
                            {--assets-root= : Directory containing reviewed local image files}
                            {--apply : Copy and publish verified images; default is dry-run}';

    protected $description = 'Publish locally reviewed manufacturer/source images with exact identity, hash and rights evidence';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $summary = $this->import(
                $site,
                (string) $this->argument('file'),
                (string) $this->option('assets-root'),
                (bool) $this->option('apply'),
            );
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /** @return array{mode: string, records: int, imported: int, promoted: int, unchanged: int, published: int} */
    private function import(Site $site, string $file, string $assetsRoot, bool $apply): array
    {
        if (! is_readable($file) || ! is_dir($assetsRoot)) {
            throw new RuntimeException('Media manifest or assets root is not readable.');
        }

        $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest)
            || ($manifest['locale'] ?? null) !== $site->default_locale
            || ! is_array($manifest['images'] ?? null)
            || $manifest['images'] === []) {
            throw new RuntimeException('Media manifest must match the site locale and contain images.');
        }

        $validated = [];
        $seen = [];
        foreach ($manifest['images'] as $index => $row) {
            if (! is_array($row)) {
                throw new RuntimeException("Media row {$index} must be an object.");
            }

            foreach ([
                'external_id', 'mpn', 'asset_file', 'sha256', 'source_page_url',
                'source_asset_url', 'source_kind', 'rights_basis', 'visual_verification_note',
            ] as $field) {
                if (! is_string($row[$field] ?? null) || blank(trim($row[$field]))) {
                    throw new RuntimeException("Media row {$index} requires {$field}.");
                }
            }

            $externalId = trim($row['external_id']);
            if (isset($seen[$externalId])) {
                throw new RuntimeException("Media manifest repeats {$externalId}.");
            }
            $seen[$externalId] = true;

            foreach (['source_page_url', 'source_asset_url'] as $urlField) {
                $url = trim($row[$urlField]);
                if (! filter_var($url, FILTER_VALIDATE_URL) || parse_url($url, PHP_URL_SCHEME) !== 'https') {
                    throw new RuntimeException("Media row {$index} requires an HTTPS {$urlField}.");
                }
            }

            $assetFile = trim($row['asset_file']);
            if (basename($assetFile) !== $assetFile || str_contains($assetFile, '..')) {
                throw new RuntimeException("Media row {$index} has an unsafe asset_file.");
            }
            $source = rtrim($assetsRoot, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR.$assetFile;
            if (! is_file($source) || ! is_readable($source)) {
                throw new RuntimeException("Media source is missing for {$externalId}.");
            }

            $hash = strtolower(hash_file('sha256', $source));
            if (! preg_match('/^[a-f0-9]{64}$/', trim($row['sha256']))
                || ! hash_equals(strtolower(trim($row['sha256'])), $hash)) {
                throw new RuntimeException("Media hash mismatch for {$externalId}.");
            }

            $image = @getimagesize($source);
            if ($image === false || ! in_array($image['mime'] ?? null, ['image/png', 'image/jpeg', 'image/webp'], true)) {
                throw new RuntimeException("Media source for {$externalId} is not a supported raster image.");
            }

            $product = Product::query()->where('external_id', $externalId)->first();
            if ($product === null || ! $product->sites()->where('site_id', $site->id)->where('is_published', true)->exists()) {
                throw new RuntimeException("Media product {$externalId} is not published for {$site->key}.");
            }
            if (ProductIdentity::normalize($product->mpn) !== ProductIdentity::normalize(trim($row['mpn']))) {
                throw new RuntimeException("Media MPN does not match product {$externalId}.");
            }

            $validated[] = [
                'row' => $row,
                'product' => $product,
                'source' => $source,
                'hash' => $hash,
                'mime' => $image['mime'],
            ];
        }

        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'records' => count($validated),
            'imported' => 0,
            'promoted' => 0,
            'unchanged' => 0,
            'published' => 0,
        ];

        if (! $apply) {
            foreach ($validated as $item) {
                $existing = ProductMedia::query()
                    ->where('product_id', $item['product']->id)
                    ->where('content_sha256', $item['hash'])
                    ->first();
                if ($existing !== null) {
                    if (! $existing->is_published || $existing->verification_status !== 'verified') {
                        throw new RuntimeException("Existing hash for {$item['product']->external_id} is not verified and published.");
                    }
                    $summary['unchanged']++;

                    continue;
                }

                $candidate = ProductMedia::query()
                    ->where('product_id', $item['product']->id)
                    ->whereNull('content_sha256')
                    ->where('source_asset_url', trim($item['row']['source_asset_url']))
                    ->first();
                $summary[$candidate === null ? 'imported' : 'promoted']++;
            }

            return $summary;
        }

        DB::transaction(function () use ($validated, $site, &$summary): void {
            foreach ($validated as $item) {
                $row = $item['row'];
                $existing = ProductMedia::query()
                    ->where('product_id', $item['product']->id)
                    ->where('content_sha256', $item['hash'])
                    ->first();
                if ($existing !== null) {
                    if (! $existing->is_published || $existing->verification_status !== 'verified') {
                        throw new RuntimeException("Existing hash for {$item['product']->external_id} is not verified and published.");
                    }
                    $summary['unchanged']++;

                    continue;
                }

                $extension = match ($item['mime']) {
                    'image/jpeg' => 'jpg',
                    'image/webp' => 'webp',
                    default => 'png',
                };
                $path = 'product-media/'.$item['product']->id.'/'.$item['hash'].'.'.$extension;
                Storage::disk('public')->put($path, file_get_contents($item['source']));

                $media = ProductMedia::query()
                    ->where('product_id', $item['product']->id)
                    ->whereNull('content_sha256')
                    ->where('source_asset_url', trim($row['source_asset_url']))
                    ->first();
                $wasCandidate = $media !== null;
                $media ??= new ProductMedia(['product_id' => $item['product']->id]);
                $media->fill([
                    'kind' => 'image',
                    'role' => 'primary',
                    'source_page_url' => trim($row['source_page_url']),
                    'source_asset_url' => trim($row['source_asset_url']),
                    'source_kind' => trim($row['source_kind']),
                    'rights_basis' => trim($row['rights_basis']),
                    'storage_path' => $path,
                    'content_sha256' => $item['hash'],
                    'verification_status' => 'verified',
                    'verification_note' => trim($row['visual_verification_note']),
                    'verified_at' => now(),
                    'is_published' => true,
                    'sort_order' => 0,
                ])->save();

                $summary[$wasCandidate ? 'promoted' : 'imported']++;
                $summary['published']++;

                SiteProduct::query()
                    ->where('site_id', $site->id)
                    ->where('product_id', $item['product']->id)
                    ->each(static fn (SiteProduct $siteProduct): bool => $siteProduct->touch());
            }
        });

        return $summary;
    }
}
