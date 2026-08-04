<?php

namespace App\Console\Commands;

use App\Domain\Content\ModelCoreIdentityMatcher;
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

/** Imports company-owned legacy assets only after explicit visual and catalogue-identity evidence. */
class ImportVerifiedLegacyImages extends Command
{
    private const EVIDENCE_VISIBLE_EXACT_MPN = 'visible_exact_mpn';

    private const EVIDENCE_VISIBLE_EXACT_MODEL_CORE = 'visible_exact_model_core';

    private const EVIDENCE_UNIQUE_CATALOG_IDENTITY = 'unique_catalog_identity_plus_visual_consistency';

    protected $signature = 'media:import-verified-legacy-images
                            {site : Site key}
                            {file : JSON media manifest}
                            {--assets-root= : Directory containing the extracted legacy files}
                            {--apply : Copy verified assets and publish them; default is dry-run}';

    protected $description = 'Import exact-MPN company-owned legacy images after hash and explicit identity-evidence gates';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $summary = $this->import($site, (string) $this->argument('file'), (string) $this->option('assets-root'), (bool) $this->option('apply'));
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /** @return array{mode: string, records: int, imported: int, unchanged: int, published: int} */
    private function import(Site $site, string $file, string $assetsRoot, bool $apply): array
    {
        if (! is_readable($file) || ! is_dir($assetsRoot)) {
            throw new RuntimeException('Media manifest or assets root is not readable.');
        }
        $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest) || ! is_array($manifest['images'] ?? null) || $manifest['images'] === []) {
            throw new RuntimeException('Media manifest must contain images.');
        }

        $validated = [];
        $seen = [];
        foreach ($manifest['images'] as $index => $row) {
            if (! is_array($row)) {
                throw new RuntimeException("Media row {$index} must be an object.");
            }
            foreach (['external_id', 'asset_file', 'sha256', 'archive_member', 'rights_basis', 'visual_verification_note'] as $field) {
                if (! is_string($row[$field] ?? null) || blank(trim($row[$field]))) {
                    throw new RuntimeException("Media row {$index} requires {$field}.");
                }
            }
            $identityScope = $row['identity_scope'] ?? 'exact';
            if (! is_string($identityScope) || ! in_array($identityScope, ['exact', 'model_core'], true)) {
                throw new RuntimeException("Media row {$index} identity_scope must be exact or model_core.");
            }
            $identityField = $identityScope === 'exact' ? 'mpn' : 'model_core';
            if (! is_string($row[$identityField] ?? null) || blank(trim($row[$identityField]))) {
                throw new RuntimeException("Media row {$index} requires {$identityField} for {$identityScope} identity.");
            }
            $identityEvidenceLevel = $row['identity_evidence_level'] ?? ($identityScope === 'exact'
                ? self::EVIDENCE_VISIBLE_EXACT_MPN
                : self::EVIDENCE_VISIBLE_EXACT_MODEL_CORE);
            if (! is_string($identityEvidenceLevel)
                || ! in_array($identityEvidenceLevel, [self::EVIDENCE_VISIBLE_EXACT_MPN, self::EVIDENCE_VISIBLE_EXACT_MODEL_CORE, self::EVIDENCE_UNIQUE_CATALOG_IDENTITY], true)) {
                throw new RuntimeException("Media row {$index} has an unsupported identity_evidence_level.");
            }
            if ($identityScope === 'model_core' && $identityEvidenceLevel !== self::EVIDENCE_VISIBLE_EXACT_MODEL_CORE) {
                throw new RuntimeException("Media row {$index} model_core identity requires visible_exact_model_core evidence.");
            }
            $catalogIdentityReference = $row['catalog_identity_reference'] ?? null;
            if ($identityEvidenceLevel === self::EVIDENCE_UNIQUE_CATALOG_IDENTITY
                && (! is_string($catalogIdentityReference) || blank(trim($catalogIdentityReference)))) {
                throw new RuntimeException("Media row {$index} requires catalog_identity_reference for unique catalogue identity evidence.");
            }
            if ($catalogIdentityReference !== null && ! is_string($catalogIdentityReference)) {
                throw new RuntimeException("Media row {$index} catalog_identity_reference must be a string when present.");
            }
            $externalId = trim($row['external_id']);
            if (isset($seen[$externalId])) {
                throw new RuntimeException("Media manifest repeats {$externalId}.");
            }
            $seen[$externalId] = true;
            $assetFile = trim($row['asset_file']);
            if (basename($assetFile) !== $assetFile || str_contains($assetFile, '..')) {
                throw new RuntimeException("Media row {$index} has an unsafe asset_file.");
            }
            $source = rtrim($assetsRoot, DIRECTORY_SEPARATOR).DIRECTORY_SEPARATOR.$assetFile;
            if (! is_file($source) || ! is_readable($source)) {
                throw new RuntimeException("Media source is missing for {$externalId}.");
            }
            $hash = strtolower(hash_file('sha256', $source));
            if (! hash_equals(strtolower(trim($row['sha256'])), $hash)) {
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
            if ($identityScope === 'exact') {
                if (ProductIdentity::normalize($product->mpn) !== ProductIdentity::normalize(trim($row['mpn']))) {
                    throw new RuntimeException("Media MPN does not match product {$externalId}.");
                }
            } else {
                $modelCore = trim($row['model_core']);
                if (! ModelCoreIdentityMatcher::nameContains($product->name, $modelCore)) {
                    throw new RuntimeException("Media model_core does not match product {$externalId} name.");
                }
                if (! is_string($row['manufacturer'] ?? null) || blank(trim($row['manufacturer']))) {
                    throw new RuntimeException("Media row {$index} requires manufacturer for model_core identity.");
                }
                $mediaManufacturer = trim($row['manufacturer']);
                if (filled($product->manufacturer)) {
                    if (ProductIdentity::normalize($product->manufacturer) !== ProductIdentity::normalize($mediaManufacturer)) {
                        throw new RuntimeException("Media manufacturer does not match product {$externalId}.");
                    }
                } elseif (! ModelCoreIdentityMatcher::nameContains($product->name, $mediaManufacturer)) {
                    throw new RuntimeException("Media manufacturer is not present in product {$externalId} name with exact boundaries.");
                }
            }
            $validated[] = [
                'row' => $row,
                'product' => $product,
                'source' => $source,
                'hash' => $hash,
                'mime' => $image['mime'],
                'identity_evidence_level' => $identityEvidenceLevel,
                'identity_scope' => $identityScope,
                'catalog_identity_reference' => is_string($catalogIdentityReference) ? trim($catalogIdentityReference) : null,
            ];
        }

        $summary = ['mode' => $apply ? 'apply' : 'dry_run', 'records' => count($validated), 'imported' => 0, 'unchanged' => 0, 'published' => 0];
        if (! $apply) {
            foreach ($validated as $item) {
                $existing = ProductMedia::query()->where('product_id', $item['product']->id)->where('content_sha256', $item['hash'])->exists();
                $summary[$existing ? 'unchanged' : 'imported']++;
            }

            return $summary;
        }

        DB::transaction(function () use ($validated, $site, &$summary): void {
            foreach ($validated as $item) {
                $row = $item['row'];
                $extension = match ($item['mime']) {
                    'image/jpeg' => 'jpg', 'image/webp' => 'webp', default => 'png'
                };
                $path = 'product-media/'.$item['product']->id.'/'.$item['hash'].'.'.$extension;
                $existing = ProductMedia::query()->where('product_id', $item['product']->id)->where('content_sha256', $item['hash'])->first();
                if ($existing !== null) {
                    $summary['unchanged']++;

                    continue;
                }
                Storage::disk('public')->put($path, file_get_contents($item['source']));
                ProductMedia::query()->create([
                    'product_id' => $item['product']->id,
                    'kind' => 'image', 'role' => 'primary',
                    'source_page_url' => 'legacy-bitrix-archive://microchips_upload_20260623.tar/'.$row['archive_member'],
                    'source_asset_url' => null, 'source_kind' => 'company-owned legacy Bitrix upload backup',
                    'rights_basis' => trim($row['rights_basis']), 'storage_path' => $path,
                    'content_sha256' => $item['hash'], 'verification_status' => 'verified',
                    'verification_note' => $this->verificationNote(
                        $item['identity_evidence_level'],
                        trim($row['visual_verification_note']),
                        $item['catalog_identity_reference'],
                    ), 'verified_at' => now(),
                    'is_published' => true, 'sort_order' => 0,
                ]);
                // Media changes must invalidate the exact regional product path
                // through the normal SiteProduct observer. A raw SQL update
                // would leave the Next.js card cached without its image.
                SiteProduct::query()
                    ->where('site_id', $site->id)
                    ->where('product_id', $item['product']->id)
                    ->each(static fn (SiteProduct $siteProduct): bool => $siteProduct->touch());
                $summary['imported']++;
                $summary['published']++;
            }
        });

        return $summary;
    }

    private function verificationNote(string $level, string $visualNote, ?string $catalogIdentityReference): string
    {
        $note = "Identity evidence: {$level}. {$visualNote}";
        if ($catalogIdentityReference !== null) {
            $note .= " Catalogue identity reference: {$catalogIdentityReference}.";
        }

        return $note;
    }
}
