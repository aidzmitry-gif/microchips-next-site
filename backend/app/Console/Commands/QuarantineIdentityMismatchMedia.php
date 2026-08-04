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

/** Quarantine visually identified wrong-product media without changing catalogue records. */
class QuarantineIdentityMismatchMedia extends Command
{
    private const SOURCE_PREFIX = 'media_identity_mismatch_quarantine:';

    private const DISPOSITION_WRONG_PRODUCT = 'quarantine_wrong_product_media';

    private const DISPOSITION_TRUNCATED_HOLD = 'hold_truncated_identity_preview';

    /** @var list<string> */
    private array $revalidationPaths = [];

    protected $signature = 'media:quarantine-identity-mismatches
                            {site : Site key}
                            {file : JSON mismatch-review manifest pinning existing media}
                            {--apply : Persist only ProductMedia quarantine/hold changes; default is dry-run}';

    protected $description = 'Quarantine reviewed wrong-product media while preserving Product and SiteProduct fields';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        $apply = (bool) $this->option('apply');
        $run = ImportRun::query()->create([
            'source' => self::SOURCE_PREFIX.$site->key,
            'source_file' => basename((string) $this->argument('file')),
            'status' => 'running',
            'started_at' => now(),
        ]);

        try {
            $summary = $this->quarantine($site, (string) $this->argument('file'), $apply, $run);
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
            $run->update([
                'status' => 'failed',
                'summary' => ['mode' => $apply ? 'apply' : 'dry_run', 'error' => $error->getMessage()],
                'finished_at' => now(),
            ]);
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /** @return array{mode:string,records:int,quarantined:int,truncated_identity_holds:int,product_changes:int,site_product_changes:int,publication_changes:int,commercial_changes:int} */
    private function quarantine(Site $site, string $file, bool $apply, ImportRun $run): array
    {
        $manifest = $this->manifest($file);
        if (($manifest['locale'] ?? null) !== $site->default_locale || ! is_array($manifest['images'] ?? null) || $manifest['images'] === []) {
            throw new RuntimeException('Mismatch manifest locale must match the site default locale and contain images.');
        }

        $externalIds = [];
        $mediaIds = [];
        $validated = [];
        foreach ($manifest['images'] as $index => $row) {
            if (! is_array($row)) {
                throw new RuntimeException("Mismatch row {$index} must be an object.");
            }
            $validated[] = $this->validateRow($site, $row, $index, $externalIds, $mediaIds);
        }

        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run', 'records' => count($validated),
            'quarantined' => 0, 'truncated_identity_holds' => 0,
            'product_changes' => 0, 'site_product_changes' => 0,
            'publication_changes' => 0, 'commercial_changes' => 0,
        ];
        DB::transaction(function () use ($validated, $apply, $run, $site, &$summary): void {
            foreach ($validated as $index => $item) {
                /** @var Product $product */
                $product = Product::query()->lockForUpdate()->findOrFail($item['product_id']);
                $siteProduct = SiteProduct::query()->where('site_id', $site->id)->where('product_id', $product->id)->lockForUpdate()->first();
                /** @var ProductMedia $media */
                $media = ProductMedia::query()->lockForUpdate()->findOrFail($item['media_id']);
                if ($product->external_id !== $item['external_id']
                    || ProductIdentity::normalize($product->mpn) !== $item['expected_normalized']
                    || $siteProduct === null || ! $siteProduct->is_published
                    || $media->product_id !== $product->id || $media->kind !== 'image' || ! $media->is_published
                    || $media->verification_status !== $item['current_status']
                    || $media->storage_path !== $item['storage_path']
                    || $media->content_sha256 !== $item['content_sha256']
                    || $media->rights_basis !== $item['rights_basis']) {
                    throw new RuntimeException("Mismatch media {$item['media_id']} state changed after validation.");
                }
                $disposition = $item['disposition'];
                $isWrongProduct = $disposition === self::DISPOSITION_WRONG_PRODUCT;
                if ($apply) {
                    $media->forceFill([
                        'verification_status' => $isWrongProduct ? ProductMedia::STATUS_NEEDS_REVIEW : ProductMedia::STATUS_LEGACY_EXACT_PREVIEW,
                        'is_published' => ! $isWrongProduct,
                        'verified_at' => null,
                        'verification_note' => $item['verification_note'],
                    ])->save();
                    $summary[$isWrongProduct ? 'quarantined' : 'truncated_identity_holds']++;
                    if ($isWrongProduct) {
                        $summary['publication_changes']++;
                    }
                }
                StagedImportRecord::query()->create([
                    'import_run_id' => $run->id,
                    'row_number' => $index + 1,
                    'entity_type' => 'media_identity_mismatch_review',
                    'external_id' => $item['external_id'],
                    'payload' => $item['payload'],
                    'normalized_payload' => [
                        'media_id' => $media->id,
                        'expected_catalogue_mpn_normalized' => ProductIdentity::normalize($item['expected_catalogue_mpn']),
                        'observed_visible_mpn_normalized' => ProductIdentity::normalize($item['observed_visible_mpn']),
                        'disposition' => $disposition,
                    ],
                    'status' => $apply ? 'completed' : 'dry_run_validated',
                    'review_note' => $item['verification_note'],
                ]);
            }
        });

        if ($apply) {
            $paths = SiteUrl::query()
                ->where('site_id', $site->id)
                ->where('target_type', 'product')
                ->whereIn('target_id', collect($validated)->pluck('product_id')->all())
                ->pluck('path')
                ->filter(fn (mixed $path): bool => is_string($path) && str_starts_with($path, '/'))
                ->all();
            $this->revalidationPaths = array_values(array_unique([...$paths, '/catalog']));
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
            throw new RuntimeException('Mismatch manifest is not readable.');
        }
        try {
            $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $error) {
            throw new RuntimeException('Mismatch manifest is not valid JSON.', previous: $error);
        }
        if (! is_array($manifest)) {
            throw new RuntimeException('Mismatch manifest must be an object.');
        }

        return $manifest;
    }

    /**
     * @param  array<string,mixed>  $row
     * @param  array<string,true>  $externalIds
     * @param  array<int,true>  $mediaIds
     * @return array<string,mixed>
     */
    private function validateRow(Site $site, array $row, int $index, array &$externalIds, array &$mediaIds): array
    {
        $allowed = [
            'external_id', 'media_id', 'content_sha256', 'storage_path', 'rights_basis',
            'current_verification_status', 'expected_catalogue_mpn', 'observed_visible_mpn',
            'disposition', 'reason', 'reviewed_at', 'reviewer', 'review_evidence_path',
            'review_evidence_sha256',
        ];
        $unknown = array_values(array_diff(array_keys($row), $allowed));
        if ($unknown !== []) {
            throw new RuntimeException("Mismatch row {$index} contains prohibited fields: ".implode(', ', $unknown).'.');
        }
        foreach (['external_id', 'content_sha256', 'storage_path', 'rights_basis', 'current_verification_status', 'expected_catalogue_mpn', 'observed_visible_mpn', 'disposition', 'reason', 'reviewed_at', 'reviewer', 'review_evidence_path', 'review_evidence_sha256'] as $field) {
            if (! is_string($row[$field] ?? null) || blank(trim($row[$field]))) {
                throw new RuntimeException("Mismatch row {$index} requires {$field}.");
            }
        }
        if (! is_int($row['media_id'] ?? null) && ! (is_string($row['media_id'] ?? null) && ctype_digit($row['media_id']))) {
            throw new RuntimeException("Mismatch row {$index} requires an integer media_id.");
        }
        $externalId = trim($row['external_id']);
        $mediaId = (int) $row['media_id'];
        if ($mediaId < 1 || isset($externalIds[$externalId]) || isset($mediaIds[$mediaId])) {
            throw new RuntimeException("Mismatch manifest repeats external_id or media_id at row {$index}.");
        }
        $externalIds[$externalId] = true;
        $mediaIds[$mediaId] = true;
        $hash = strtolower(trim($row['content_sha256']));
        $reviewEvidenceHash = strtolower(trim($row['review_evidence_sha256']));
        if (preg_match('/^[a-f0-9]{64}$/', $hash) !== 1 || preg_match('/^[a-f0-9]{64}$/', $reviewEvidenceHash) !== 1) {
            throw new RuntimeException("Mismatch row {$index} requires lowercase SHA-256 content and review-evidence hashes.");
        }
        $reviewEvidenceName = trim($row['review_evidence_path']);
        if (basename($reviewEvidenceName) !== $reviewEvidenceName) {
            throw new RuntimeException("Mismatch row {$index} review evidence must be a file beside the manifest.");
        }
        $reviewEvidencePath = dirname((string) $this->argument('file')).DIRECTORY_SEPARATOR.$reviewEvidenceName;
        if (! is_file($reviewEvidencePath) || ! is_readable($reviewEvidencePath)
            || ! hash_equals($reviewEvidenceHash, strtolower((string) hash_file('sha256', $reviewEvidencePath)))) {
            throw new RuntimeException("Mismatch row {$index} review evidence file does not match its hash pin.");
        }
        $disposition = trim($row['disposition']);
        if (! in_array($disposition, [self::DISPOSITION_WRONG_PRODUCT, self::DISPOSITION_TRUNCATED_HOLD], true)) {
            throw new RuntimeException("Mismatch row {$index} has an unsupported disposition.");
        }
        $reviewedAt = trim($row['reviewed_at']);
        $date = DateTimeImmutable::createFromFormat('!Y-m-d', $reviewedAt);
        if ($date === false || $date->format('Y-m-d') !== $reviewedAt) {
            throw new RuntimeException("Mismatch row {$index} reviewed_at must be YYYY-MM-DD.");
        }
        $expectedMpn = trim($row['expected_catalogue_mpn']);
        $observedMpn = trim($row['observed_visible_mpn']);
        $expectedNormalized = ProductIdentity::normalize($expectedMpn);
        $observedNormalized = ProductIdentity::normalize($observedMpn);
        if ($expectedNormalized === '' || $observedNormalized === '' || $expectedNormalized === $observedNormalized) {
            throw new RuntimeException("Mismatch row {$index} observed visible MPN must differ from the expected catalogue MPN.");
        }

        $product = Product::query()->where('external_id', $externalId)->first();
        $siteProduct = $product === null ? null : SiteProduct::query()
            ->where('site_id', $site->id)->where('product_id', $product->id)->where('is_published', true)->first();
        if ($product === null || $siteProduct === null) {
            throw new RuntimeException("Mismatch media product {$externalId} is not published for {$site->key}.");
        }
        if (ProductIdentity::normalize($product->mpn) !== ProductIdentity::normalize($expectedMpn)) {
            throw new RuntimeException("Mismatch row {$index} expected catalogue MPN does not match current {$externalId} MPN.");
        }
        if ($disposition === self::DISPOSITION_TRUNCATED_HOLD
            && (! str_starts_with($observedNormalized, $expectedNormalized)
                || strlen($observedNormalized) <= strlen($expectedNormalized)
                || ! ModelCoreIdentityMatcher::nameContains($product->name, $observedMpn))) {
            throw new RuntimeException("Mismatch row {$index} truncated hold is not a strict prefix-compatible identity proven by the product name.");
        }
        $media = ProductMedia::query()->find($mediaId);
        if ($media === null || $media->product_id !== $product->id) {
            throw new RuntimeException("Mismatch row {$index} does not pin media_id {$mediaId} owned by {$externalId}.");
        }
        $currentStatus = trim($row['current_verification_status']);
        if ($media->kind !== 'image'
            || ! $media->is_published
            || $media->verification_status !== $currentStatus
            || ! in_array($currentStatus, [ProductMedia::STATUS_VERIFIED, ProductMedia::STATUS_LEGACY_EXACT_PREVIEW], true)
            || ($currentStatus === ProductMedia::STATUS_VERIFIED && $media->verified_at === null)) {
            throw new RuntimeException("Media {$mediaId} current verification state does not match a published verified/legacy-preview manifest pin.");
        }
        $rightsBasis = trim($row['rights_basis']);
        if ($media->rights_basis !== $rightsBasis || ! str_contains(mb_strtolower($rightsBasis), 'company-owned')) {
            throw new RuntimeException("Media {$mediaId} does not have the pinned company-owned rights basis.");
        }
        $storagePath = trim($row['storage_path']);
        if ($media->storage_path !== $storagePath || $media->content_sha256 !== $hash) {
            throw new RuntimeException("Media {$mediaId} path or hash does not match its manifest pin.");
        }
        $disk = Storage::disk('public');
        $absolutePath = $disk->path($storagePath);
        if (! $disk->exists($storagePath) || ! is_file($absolutePath) || ! hash_equals($hash, strtolower((string) hash_file('sha256', $absolutePath)))) {
            throw new RuntimeException("Media {$mediaId} stored asset hash does not match its manifest pin.");
        }

        $note = sprintf(
            'Media identity review at %s by %s: expected catalogue MPN %s; observed visible MPN %s; disposition %s; evidence %s; reason %s.',
            $reviewedAt, trim($row['reviewer']), $expectedMpn, $observedMpn, $disposition, $reviewEvidenceHash, trim($row['reason']),
        );

        return [
            'product_id' => $product->id, 'media_id' => $media->id, 'external_id' => $externalId,
            'expected_catalogue_mpn' => $expectedMpn, 'expected_normalized' => $expectedNormalized,
            'observed_visible_mpn' => $observedMpn, 'disposition' => $disposition,
            'verification_note' => $note, 'current_status' => $currentStatus,
            'storage_path' => $storagePath, 'content_sha256' => $hash, 'rights_basis' => $rightsBasis,
            'payload' => $row,
        ];
    }
}
