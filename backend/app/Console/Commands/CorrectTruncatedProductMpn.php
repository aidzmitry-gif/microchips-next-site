<?php

namespace App\Console\Commands;

use App\Domain\Content\ModelCoreIdentityMatcher;
use App\Domain\Imports\ProductIdentity;
use App\Events\SiteContentChanged;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use DateTimeImmutable;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use Throwable;

/** Correct only a non-empty MPN proven to have been truncated during legacy extraction. */
class CorrectTruncatedProductMpn extends Command
{
    private const SOURCE = 'verified_truncated_mpn_correction:';

    /** @var list<string> */
    private array $revalidationPaths = [];

    protected $signature = 'catalog:correct-truncated-mpn
                            {site : Site key}
                            {file : JSON evidence manifest}
                            {--apply : Persist the guarded MPN correction; default is dry-run}';

    protected $description = 'Correct a truncated legacy MPN only when official text and company-owned visible media prove the full model';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        $apply = (bool) $this->option('apply');
        $run = ImportRun::query()->create([
            'source' => self::SOURCE.$site->key,
            'source_file' => basename((string) $this->argument('file')),
            'status' => 'running',
            'started_at' => now(),
        ]);

        try {
            $summary = $this->correct($site, (string) $this->argument('file'), $apply, $run);
            $run->update([
                'status' => $apply ? 'completed' : 'dry_run_complete',
                'total_records' => $summary['records'],
                'processed_records' => $summary['records'],
                'summary' => $summary,
                'finished_at' => now(),
            ]);
            if ($apply) {
                $this->dispatchRevalidation($site);
            }
            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $run->update(['status' => 'failed', 'summary' => ['error' => $error->getMessage()], 'finished_at' => now()]);
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /** @return array{mode:string,records:int,corrected:int,product_identity_changes:int,commercial_changes:int,publication_changes:int} */
    private function correct(Site $site, string $file, bool $apply, ImportRun $run): array
    {
        $manifest = $this->manifest($file);
        if (($manifest['locale'] ?? null) !== $site->default_locale || ! is_array($manifest['corrections'] ?? null) || $manifest['corrections'] === []) {
            throw new RuntimeException('Correction manifest locale must match the site and contain corrections.');
        }

        $validated = [];
        $externalIds = [];
        $correctedMpns = [];
        foreach ($manifest['corrections'] as $index => $row) {
            if (! is_array($row)) {
                throw new RuntimeException("Correction row {$index} must be an object.");
            }
            $validated[] = $this->validateRow($site, $row, $index, $externalIds, $correctedMpns);
        }

        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'records' => count($validated),
            'corrected' => 0,
            'product_identity_changes' => 0,
            'commercial_changes' => 0,
            'publication_changes' => 0,
        ];
        DB::transaction(function () use ($validated, $apply, $run, $site, &$summary): void {
            foreach ($validated as $index => $item) {
                /** @var Product $product */
                $product = Product::query()->lockForUpdate()->findOrFail($item['product']->id);
                $siteProduct = SiteProduct::query()->where('site_id', $site->id)->where('product_id', $product->id)->lockForUpdate()->first();
                /** @var ProductMedia $media */
                $media = ProductMedia::query()->lockForUpdate()->findOrFail($item['media_id']);
                if ($product->external_id !== $item['external_id']
                    || $product->name !== $item['current_name'] || $product->status !== 'draft'
                    || ProductIdentity::normalize($product->manufacturer) !== $item['manufacturer_normalized']
                    || ProductIdentity::normalize($product->mpn) !== $item['current_normalized']
                    || $siteProduct === null || ! $siteProduct->is_published
                    || $media->product_id !== $product->id || $media->kind !== 'image'
                    || $media->verification_status !== ProductMedia::STATUS_LEGACY_EXACT_PREVIEW || ! $media->is_published
                    || $media->storage_path !== $item['storage_path'] || $media->content_sha256 !== $item['media_content_sha256']
                    || $media->rights_basis !== $item['rights_basis']) {
                    throw new RuntimeException("Product {$product->external_id} identity or evidence state changed after validation.");
                }
                if (! hash_equals($item['source_snapshot_sha256'], strtolower((string) hash_file('sha256', $item['source_snapshot_path'])))
                    || ! hash_equals($item['source_extraction_sha256'], strtolower((string) hash_file('sha256', $item['source_extraction_path'])))
                    || ! hash_equals($item['media_content_sha256'], strtolower((string) hash_file('sha256', Storage::disk('public')->path($item['storage_path']))))) {
                    throw new RuntimeException("Product {$product->external_id} evidence files changed after validation.");
                }
                $duplicate = Product::query()
                    ->whereKeyNot($product->id)
                    ->where(fn ($query) => $query->where('mpn_normalized', $item['corrected_normalized'])->orWhere('sku_normalized', $item['corrected_normalized']))
                    ->lockForUpdate()
                    ->exists();
                if ($duplicate) {
                    throw new RuntimeException("Corrected MPN for {$product->external_id} already belongs to another product.");
                }

                if ($apply) {
                    $before = $product->only(['external_id', 'sku', 'manufacturer', 'name', 'status']);
                    $changed = DB::table('products')
                        ->where('id', $product->id)
                        ->where('mpn_normalized', $item['current_normalized'])
                        ->update(['mpn' => $item['corrected_mpn'], 'mpn_normalized' => $item['corrected_normalized'], 'updated_at' => now()]);
                    if ($changed !== 1) {
                        throw new RuntimeException("Product {$product->external_id} truncated MPN correction was not atomic.");
                    }
                    $product->refresh();
                    if ($product->only(['external_id', 'sku', 'manufacturer', 'name', 'status']) !== $before) {
                        throw new RuntimeException("Product {$product->external_id} changed outside the permitted MPN fields.");
                    }
                    $summary['corrected']++;
                    $summary['product_identity_changes']++;
                }

                StagedImportRecord::query()->create([
                    'import_run_id' => $run->id,
                    'row_number' => $index + 1,
                    'entity_type' => 'verified_truncated_mpn_correction',
                    'external_id' => $product->external_id,
                    'payload' => $item['payload'],
                    'normalized_payload' => [
                        'current_mpn_normalized' => $item['current_normalized'],
                        'corrected_mpn_normalized' => $item['corrected_normalized'],
                        'media_id' => $media->id,
                        'source_evidence_text_sha256' => $item['source_evidence_text_sha256'],
                        'source_snapshot_sha256' => $item['source_snapshot_sha256'],
                        'source_extraction_sha256' => $item['source_extraction_sha256'],
                    ],
                    'status' => $apply ? 'completed' : 'dry_run_validated',
                    'review_note' => 'Official manufacturer text and company-owned visible label prove a truncated legacy MPN correction.',
                ]);
            }
        });

        if ($apply) {
            $productIds = collect($validated)->map(fn (array $item): int => (int) $item['product']->id)->all();
            $paths = SiteUrl::query()->where('site_id', $site->id)->where('target_type', 'product')->whereIn('target_id', $productIds)->pluck('path')->all();
            $this->revalidationPaths = array_values(array_unique([...$paths, '/catalog', '/sitemap.xml']));
        }

        return $summary;
    }

    private function dispatchRevalidation(Site $site): void
    {
        try {
            SiteContentChanged::dispatch($site, $this->revalidationPaths);
        } catch (Throwable $error) {
            report($error);
            $this->warn('Catalogue changes were committed, but page revalidation dispatch failed and must be retried.');
        }
    }

    /** @return array<string,mixed> */
    private function manifest(string $file): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Correction manifest is not readable.');
        }
        $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest)) {
            throw new RuntimeException('Correction manifest must be an object.');
        }

        return $manifest;
    }

    /** @return array<string,mixed> */
    private function validateRow(Site $site, array $row, int $index, array &$externalIds, array &$correctedMpns): array
    {
        $allowed = [
            'external_id', 'current_name', 'manufacturer', 'current_mpn', 'corrected_mpn',
            'source_url', 'source_kind', 'source_snapshot_path', 'source_snapshot_sha256',
            'source_extraction_path', 'source_extraction_sha256', 'source_evidence_text',
            'source_evidence_text_sha256', 'media_id', 'media_content_sha256', 'storage_path',
            'rights_basis', 'observed_visible_mpn', 'checked_at', 'review_note',
        ];
        $unknown = array_values(array_diff(array_keys($row), $allowed));
        if ($unknown !== []) {
            throw new RuntimeException("Correction row {$index} contains prohibited fields: ".implode(', ', $unknown).'.');
        }
        foreach ($allowed as $field) {
            if ($field === 'media_id') {
                continue;
            }
            if (! is_string($row[$field] ?? null) || blank(trim($row[$field]))) {
                throw new RuntimeException("Correction row {$index} requires {$field}.");
            }
        }
        if (! is_int($row['media_id'] ?? null) && ! (is_string($row['media_id'] ?? null) && ctype_digit($row['media_id']))) {
            throw new RuntimeException("Correction row {$index} requires an integer media_id.");
        }
        $externalId = trim($row['external_id']);
        $correctedMpn = trim($row['corrected_mpn']);
        $currentNormalized = ProductIdentity::normalize(trim($row['current_mpn']));
        $correctedNormalized = ProductIdentity::normalize($correctedMpn);
        if ($currentNormalized === null || $correctedNormalized === null || $currentNormalized === $correctedNormalized
            || strlen($currentNormalized) < 4 || ! str_starts_with($correctedNormalized, $currentNormalized)) {
            throw new RuntimeException("Correction row {$index} is not a strict truncated-prefix MPN correction.");
        }
        if (isset($externalIds[$externalId]) || isset($correctedMpns[$correctedNormalized])) {
            throw new RuntimeException("Correction manifest repeats external_id or corrected MPN at row {$index}.");
        }
        $externalIds[$externalId] = true;
        $correctedMpns[$correctedNormalized] = true;

        foreach (['source_snapshot_sha256', 'source_extraction_sha256', 'source_evidence_text_sha256', 'media_content_sha256'] as $hashField) {
            if (preg_match('/^[a-f0-9]{64}$/', trim($row[$hashField])) !== 1) {
                throw new RuntimeException("Correction row {$index} requires lowercase SHA-256 {$hashField}.");
            }
        }
        $manifestDirectory = dirname((string) $this->argument('file'));
        $snapshotName = trim($row['source_snapshot_path']);
        $extractionName = trim($row['source_extraction_path']);
        if (basename($snapshotName) !== $snapshotName || basename($extractionName) !== $extractionName) {
            throw new RuntimeException("Correction row {$index} source evidence files must be beside the manifest.");
        }
        $snapshotPath = $manifestDirectory.DIRECTORY_SEPARATOR.$snapshotName;
        $extractionPath = $manifestDirectory.DIRECTORY_SEPARATOR.$extractionName;
        $snapshotHash = strtolower(trim($row['source_snapshot_sha256']));
        $extractionHash = strtolower(trim($row['source_extraction_sha256']));
        if (! is_file($snapshotPath) || ! is_readable($snapshotPath)
            || ! hash_equals($snapshotHash, strtolower((string) hash_file('sha256', $snapshotPath)))) {
            throw new RuntimeException("Correction row {$index} official source snapshot does not match its hash pin.");
        }
        if (! is_file($extractionPath) || ! is_readable($extractionPath)
            || ! hash_equals($extractionHash, strtolower((string) hash_file('sha256', $extractionPath)))) {
            throw new RuntimeException("Correction row {$index} official source extraction does not match its hash pin.");
        }
        $evidenceText = trim($row['source_evidence_text']);
        $evidenceHash = strtolower(trim($row['source_evidence_text_sha256']));
        $extractionText = (string) file_get_contents($extractionPath);
        if (! hash_equals($evidenceHash, hash('sha256', $evidenceText))
            || ! str_contains((string) ProductIdentity::normalize($evidenceText), $correctedNormalized)
            || ! str_contains((string) ProductIdentity::normalize($extractionText), (string) ProductIdentity::normalize($evidenceText))) {
            throw new RuntimeException("Correction row {$index} official evidence text does not prove the corrected MPN.");
        }
        if (! filter_var($row['source_url'], FILTER_VALIDATE_URL) || parse_url($row['source_url'], PHP_URL_SCHEME) !== 'https'
            || ! in_array($row['source_kind'], ['official_manufacturer_catalogue', 'official_manufacturer_product_page'], true)) {
            throw new RuntimeException("Correction row {$index} requires an HTTPS official manufacturer source.");
        }
        $date = DateTimeImmutable::createFromFormat('!Y-m-d', trim($row['checked_at']));
        if ($date === false || $date->format('Y-m-d') !== trim($row['checked_at'])) {
            throw new RuntimeException("Correction row {$index} checked_at must be YYYY-MM-DD.");
        }
        if (ProductIdentity::normalize($row['observed_visible_mpn']) !== $correctedNormalized) {
            throw new RuntimeException("Correction row {$index} visible MPN does not equal the corrected MPN.");
        }

        $product = Product::query()->where('external_id', $externalId)->first();
        $siteProduct = $product === null ? null : SiteProduct::query()->where('site_id', $site->id)->where('product_id', $product->id)->where('is_published', true)->first();
        if ($product === null || $siteProduct === null || $product->status !== 'draft'
            || $product->name !== $row['current_name']
            || ProductIdentity::normalize($product->manufacturer) !== ProductIdentity::normalize($row['manufacturer'])
            || ProductIdentity::normalize($product->mpn) !== $currentNormalized
            || ! ModelCoreIdentityMatcher::nameContains($product->name, $correctedMpn)) {
            throw new RuntimeException("Correction row {$index} current catalogue identity does not match its pins.");
        }
        $duplicate = Product::query()->whereKeyNot($product->id)
            ->where(fn ($query) => $query->where('mpn_normalized', $correctedNormalized)->orWhere('sku_normalized', $correctedNormalized))->exists();
        if ($duplicate) {
            throw new RuntimeException("Correction row {$index} corrected MPN already exists on another product.");
        }

        $media = ProductMedia::query()->find((int) $row['media_id']);
        $mediaHash = strtolower(trim($row['media_content_sha256']));
        $storagePath = trim($row['storage_path']);
        if ($media === null || $media->product_id !== $product->id || $media->kind !== 'image'
            || $media->source_kind !== 'legacy_bitrix_exact_element_preview'
            || $media->verification_status !== ProductMedia::STATUS_LEGACY_EXACT_PREVIEW || ! $media->is_published
            || $media->storage_path !== $storagePath || $media->content_sha256 !== $mediaHash
            || $media->rights_basis !== trim($row['rights_basis']) || ! str_contains(mb_strtolower($media->rights_basis), 'company-owned')) {
            throw new RuntimeException("Correction row {$index} company-owned visible media does not match its pins.");
        }
        $disk = Storage::disk('public');
        $absolutePath = $disk->path($storagePath);
        if (! $disk->exists($storagePath) || ! is_file($absolutePath) || ! hash_equals($mediaHash, strtolower((string) hash_file('sha256', $absolutePath)))) {
            throw new RuntimeException("Correction row {$index} media asset hash does not match its pin.");
        }

        return [
            'product' => $product, 'external_id' => $externalId, 'current_name' => $product->name,
            'manufacturer_normalized' => ProductIdentity::normalize($product->manufacturer),
            'media_id' => $media->id, 'current_normalized' => $currentNormalized,
            'corrected_normalized' => $correctedNormalized, 'corrected_mpn' => $correctedMpn,
            'source_snapshot_path' => $snapshotPath, 'source_snapshot_sha256' => $snapshotHash,
            'source_extraction_path' => $extractionPath, 'source_extraction_sha256' => $extractionHash,
            'source_evidence_text_sha256' => $evidenceHash, 'storage_path' => $storagePath,
            'media_content_sha256' => $mediaHash, 'rights_basis' => trim($row['rights_basis']),
            'payload' => $row,
        ];
    }
}
