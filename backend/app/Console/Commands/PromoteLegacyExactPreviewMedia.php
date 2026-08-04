<?php

namespace App\Console\Commands;

use App\Domain\Content\ModelCoreIdentityMatcher;
use App\Domain\Imports\ProductIdentity;
use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use DateTimeImmutable;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use Throwable;

/** Promote only visually reviewed, company-owned exact Bitrix preview media. */
class PromoteLegacyExactPreviewMedia extends Command
{
    private const SOURCE_KIND = 'legacy_bitrix_exact_element_preview';

    private const EVIDENCE_VISIBLE_EXACT_MPN = 'visible_exact_mpn';

    private const EVIDENCE_VISIBLE_EXACT_MODEL_CORE = 'visible_exact_model_core';

    protected $signature = 'media:promote-legacy-exact-preview-media
                            {site : Site key}
                            {file : JSON manifest pinning existing preview media}
                            {--apply : Promote reviewed preview media; default is dry-run}';

    protected $description = 'Promote an existing company-owned legacy_exact_preview media row after exact visual identity review';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $summary = $this->promote($site, (string) $this->argument('file'), (bool) $this->option('apply'));
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /** @return array{mode: string, records: int, promoted: int, site_products_touched: int, publication_changes: int, commercial_changes: int} */
    private function promote(Site $site, string $file, bool $apply): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Legacy preview promotion manifest is not readable.');
        }
        $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest)
            || ($manifest['locale'] ?? null) !== $site->default_locale
            || ! is_array($manifest['images'] ?? null)
            || $manifest['images'] === []) {
            throw new RuntimeException('Legacy preview promotion manifest must match the site locale and contain images.');
        }

        $validated = [];
        $externalIds = [];
        $mediaIds = [];
        foreach ($manifest['images'] as $index => $row) {
            if (! is_array($row)) {
                throw new RuntimeException("Media row {$index} must be an object.");
            }
            $validated[] = $this->validateRow($site, $row, $index, $externalIds, $mediaIds);
        }

        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'records' => count($validated),
            'promoted' => 0,
            'site_products_touched' => 0,
            'publication_changes' => 0,
            'commercial_changes' => 0,
        ];
        if (! $apply) {
            return $summary;
        }

        DB::transaction(function () use ($validated, $site, &$summary): void {
            foreach ($validated as $item) {
                /** @var ProductMedia $media */
                $media = $item['media'];
                $media->forceFill([
                    'verification_status' => ProductMedia::STATUS_VERIFIED,
                    'verification_note' => $item['verification_note'],
                    'verified_at' => now(),
                    'is_published' => true,
                ])->save();

                SiteProduct::query()
                    ->where('site_id', $site->id)
                    ->where('product_id', $media->product_id)
                    ->each(static function (SiteProduct $siteProduct) use (&$summary): bool {
                        $siteProduct->touch();
                        $summary['site_products_touched']++;

                        return true;
                    });
                $summary['promoted']++;
            }
        });

        return $summary;
    }

    /**
     * @param  array<string, mixed>  $row
     * @param  array<string, true>  $externalIds
     * @param  array<int, true>  $mediaIds
     * @return array{media: ProductMedia, verification_note: string}
     */
    private function validateRow(Site $site, array $row, int $index, array &$externalIds, array &$mediaIds): array
    {
        $allowed = [
            'external_id', 'media_id', 'content_sha256', 'storage_path', 'rights_basis',
            'identity_scope', 'mpn', 'model_core', 'manufacturer', 'identity_evidence_level',
            'visual_verification_note', 'reviewed_at',
        ];
        $unknown = array_values(array_diff(array_keys($row), $allowed));
        if ($unknown !== []) {
            throw new RuntimeException("Media row {$index} contains prohibited fields: ".implode(', ', $unknown).'.');
        }
        foreach (['external_id', 'content_sha256', 'storage_path', 'rights_basis', 'visual_verification_note', 'reviewed_at'] as $field) {
            if (! is_string($row[$field] ?? null) || blank(trim($row[$field]))) {
                throw new RuntimeException("Media row {$index} requires {$field}.");
            }
        }
        if (! is_int($row['media_id'] ?? null) && ! (is_string($row['media_id'] ?? null) && ctype_digit($row['media_id']))) {
            throw new RuntimeException("Media row {$index} requires an integer media_id.");
        }

        $externalId = trim($row['external_id']);
        $mediaId = (int) $row['media_id'];
        if ($mediaId < 1 || isset($externalIds[$externalId]) || isset($mediaIds[$mediaId])) {
            throw new RuntimeException("Media manifest repeats external_id or media_id at row {$index}.");
        }
        $externalIds[$externalId] = true;
        $mediaIds[$mediaId] = true;
        $hash = strtolower(trim($row['content_sha256']));
        if (preg_match('/^[a-f0-9]{64}$/', $hash) !== 1) {
            throw new RuntimeException("Media row {$index} requires a lowercase SHA-256 content hash.");
        }

        $identityScope = $row['identity_scope'] ?? null;
        if (! is_string($identityScope) || ! in_array($identityScope, ['exact', 'model_core'], true)) {
            throw new RuntimeException("Media row {$index} identity_scope must be exact or model_core.");
        }
        $evidenceLevel = $row['identity_evidence_level'] ?? null;
        $expectedEvidence = $identityScope === 'exact'
            ? self::EVIDENCE_VISIBLE_EXACT_MPN
            : self::EVIDENCE_VISIBLE_EXACT_MODEL_CORE;
        if ($evidenceLevel !== $expectedEvidence) {
            throw new RuntimeException("Media row {$index} requires {$expectedEvidence} evidence.");
        }
        $reviewedAt = trim($row['reviewed_at']);
        $reviewedDate = DateTimeImmutable::createFromFormat('!Y-m-d', $reviewedAt);
        if ($reviewedDate === false || $reviewedDate->format('Y-m-d') !== $reviewedAt) {
            throw new RuntimeException("Media row {$index} reviewed_at must be YYYY-MM-DD.");
        }

        $product = Product::query()->where('external_id', $externalId)->first();
        $siteProduct = $product === null ? null : SiteProduct::query()
            ->where('site_id', $site->id)
            ->where('product_id', $product->id)
            ->where('is_published', true)
            ->first();
        if ($product === null || $siteProduct === null) {
            throw new RuntimeException("Media product {$externalId} is not published for {$site->key}.");
        }

        $media = ProductMedia::query()->find($mediaId);
        if ($media === null || $media->product_id !== $product->id) {
            throw new RuntimeException("Media row {$index} does not pin media_id {$mediaId} owned by {$externalId}.");
        }
        if ($media->kind !== 'image'
            || $media->source_kind !== self::SOURCE_KIND
            || $media->verification_status !== ProductMedia::STATUS_LEGACY_EXACT_PREVIEW
            || ! $media->is_published) {
            throw new RuntimeException("Media {$mediaId} is not a published legacy_exact_preview image.");
        }
        $rightsBasis = trim($row['rights_basis']);
        if ($media->rights_basis !== $rightsBasis || ! str_contains(mb_strtolower($rightsBasis), 'company-owned')) {
            throw new RuntimeException("Media {$mediaId} does not have the pinned company-owned rights basis.");
        }
        $storagePath = trim($row['storage_path']);
        if ($media->storage_path !== $storagePath || $media->content_sha256 !== $hash) {
            throw new RuntimeException("Media {$mediaId} path or hash does not match its manifest pin.");
        }
        $absolutePath = Storage::disk('public')->path($storagePath);
        if (! Storage::disk('public')->exists($storagePath) || ! is_file($absolutePath) || ! hash_equals($hash, strtolower((string) hash_file('sha256', $absolutePath)))) {
            throw new RuntimeException("Media {$mediaId} stored asset hash does not match its manifest pin.");
        }

        if ($identityScope === 'exact') {
            if (! is_string($row['mpn'] ?? null) || blank(trim($row['mpn']))
                || array_key_exists('model_core', $row)
                || array_key_exists('manufacturer', $row)
                || ProductIdentity::normalize($product->mpn) !== ProductIdentity::normalize(trim($row['mpn']))
                || ! ModelCoreIdentityMatcher::nameContains($product->name, trim($row['mpn']))) {
                throw new RuntimeException("Media {$mediaId} exact MPN identity does not match {$externalId} with exact boundaries.");
            }
        } else {
            if (! is_string($row['model_core'] ?? null) || blank(trim($row['model_core']))
                || ! is_string($row['manufacturer'] ?? null) || blank(trim($row['manufacturer']))
                || array_key_exists('mpn', $row)
                || ! ModelCoreIdentityMatcher::nameContains($product->name, trim($row['model_core']))) {
                throw new RuntimeException("Media {$mediaId} model_core identity does not match {$externalId} with exact boundaries.");
            }
            $manufacturer = trim($row['manufacturer']);
            if (filled($product->manufacturer)) {
                if (ProductIdentity::normalize($product->manufacturer) !== ProductIdentity::normalize($manufacturer)) {
                    throw new RuntimeException("Media {$mediaId} manufacturer does not match {$externalId}.");
                }
            } elseif (! ModelCoreIdentityMatcher::nameContains($product->name, $manufacturer)) {
                throw new RuntimeException("Media {$mediaId} manufacturer is not present in {$externalId} name with exact boundaries.");
            }
        }

        return [
            'media' => $media,
            'verification_note' => 'Identity evidence: '.$evidenceLevel.'. Reviewed at: '.$reviewedAt.'. '.trim($row['visual_verification_note']),
        ];
    }
}
