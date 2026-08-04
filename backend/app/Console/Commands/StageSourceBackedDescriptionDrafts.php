<?php

namespace App\Console\Commands;

use App\Domain\Content\DescriptionSourceEvidencePolicy;
use App\Domain\Content\ModelCoreIdentityMatcher;
use App\Domain\Content\ProductDescriptionDrafter;
use App\Domain\Imports\ProductIdentity;
use App\Models\CatalogDraftMaterialization;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/**
 * Stages editorial descriptions from a deliberately small, source-attributed
 * manifest.  This command never changes product fields, publication flags or
 * site URLs: a human still reviews every resulting draft in Filament.
 */
class StageSourceBackedDescriptionDrafts extends Command
{
    protected $signature = 'content:stage-source-backed-description-drafts
                            {site : Site key}
                            {file : JSON manifest produced from verified MPN evidence}
                            {--apply : Persist drafts; otherwise validate inside a rolled-back transaction}
                            {--refresh-existing : Replace only existing draft-status evidence with the manifest after full revalidation}
                            {--refresh-applied : With --refresh-existing, replace an already-applied draft after full revalidation; the product itself changes only in the separate apply command}';

    protected $description = 'Stage source-attributed product description drafts without publishing them';

    public function __construct(private readonly ProductDescriptionDrafter $drafter)
    {
        parent::__construct();
    }

    public function handle(): int
    {
        $site = Site::query()->where('key', $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        $apply = (bool) $this->option('apply');
        $refreshExisting = (bool) $this->option('refresh-existing');
        $refreshApplied = (bool) $this->option('refresh-applied');
        if ($refreshApplied && ! $refreshExisting) {
            throw new RuntimeException('--refresh-applied requires --refresh-existing.');
        }
        $run = ImportRun::create([
            'source' => 'source_backed_description_drafts',
            'source_file' => basename((string) $this->argument('file')),
            'status' => 'running',
            'started_at' => now(),
        ]);

        try {
            $summary = $this->stage($site, (string) $this->argument('file'), $apply, $refreshExisting, $refreshApplied);
            $run->update([
                'status' => $apply ? 'completed' : 'dry_run_complete',
                'total_records' => $summary['records'],
                'processed_records' => $summary['records'],
                'summary' => $summary,
                'finished_at' => now(),
            ]);
            $this->info("Source-backed description run {$run->id}: {$summary['created']} created, {$summary['refreshed']} refreshed, {$summary['unchanged']} unchanged; none were published.");

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

    /** @return array{records: int, created: int, refreshed: int, unchanged: int} */
    private function stage(Site $site, string $file, bool $apply, bool $refreshExisting, bool $refreshApplied): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Description draft manifest is not readable.');
        }

        try {
            $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $error) {
            throw new RuntimeException('Description draft manifest is not valid JSON.', previous: $error);
        }

        if (! is_array($manifest) || ! is_string($manifest['locale'] ?? null) || ! is_array($manifest['products'] ?? null)) {
            throw new RuntimeException('Description draft manifest requires locale and products.');
        }
        if ($manifest['locale'] !== $site->default_locale) {
            throw new RuntimeException('Manifest locale must match the site default locale.');
        }

        $seen = [];
        $seenExactMpns = [];
        $summary = ['records' => count($manifest['products']), 'created' => 0, 'refreshed' => 0, 'unchanged' => 0];

        $process = function () use ($manifest, $site, $refreshExisting, $refreshApplied, &$seen, &$seenExactMpns, &$summary): void {
            foreach ($manifest['products'] as $index => $row) {
                if (! is_array($row)) {
                    throw new RuntimeException("Product row {$index} must be an object.");
                }
                $sourceEvidence = DescriptionSourceEvidencePolicy::fromManifestRow($row, $index);
                $identityScope = $this->identityScope($row, $index);
                $requiredFields = $identityScope === 'model_core'
                    ? ['external_id', 'manufacturer', 'model_core', 'source_url']
                    : ['external_id', 'manufacturer', 'mpn', 'technology', 'source_url'];
                foreach ($requiredFields as $field) {
                    if (! is_string($row[$field] ?? null) || blank($row[$field])) {
                        throw new RuntimeException("Product row {$index} requires {$field}.");
                    }
                }

                $externalId = trim($row['external_id']);
                if (isset($seen[$externalId])) {
                    throw new RuntimeException("Manifest repeats external_id {$externalId}.");
                }
                $seen[$externalId] = true;

                $product = Product::query()->where('external_id', $externalId)->first();
                $siteProduct = $product === null
                    ? null
                    : $product->sites()->where('site_id', $site->id)->first();
                if ($product === null || $siteProduct === null) {
                    throw new RuntimeException("Product {$externalId} is not assigned to site {$site->key}.");
                }
                if ($identityScope === 'model_core') {
                    $this->assertModelCoreIdentityMatches($product, $row, $externalId);
                } else {
                    $this->assertIdentityMatches($product, $row, $externalId);
                }
                if (($sourceEvidence['source_tier'] ?? null) === DescriptionSourceEvidencePolicy::MANUFACTURER_PRIMARY_TIER) {
                    $this->assertBitrixTransferEligibility($product, $siteProduct, $site, $externalId);
                    // Model-core evidence deliberately proves only a bounded name fragment.
                    // It must not enter the exact-MPN duplicate guard.
                    if ($identityScope === 'exact') {
                        $this->assertManufacturerPrimaryIdentityMatches($product, $row, $externalId, $seenExactMpns);
                    }
                }
                if ($identityScope === 'model_core'
                    && ProductIdentity::normalize($product->manufacturer) === null
                    && ! ModelCoreIdentityMatcher::nameContains($product->name, (string) $row['manufacturer'])) {
                    throw new RuntimeException("Product {$externalId} model-core evidence requires the existing catalogue name to contain the manufacturer when canonical manufacturer is blank.");
                }

                $existing = ProductDescriptionDraft::query()
                    ->where('product_id', $product->id)
                    ->where('locale', $manifest['locale'])
                    ->latest('id')
                    ->first();
                if ($existing !== null && ! $refreshExisting) {
                    $summary['unchanged']++;

                    continue;
                }
                $refreshableAppliedStatuses = ['applied', 'legacy_preview_applied'];
                if ($existing !== null && ! in_array($existing->status, ['draft', 'review'], true)
                    && ! ($refreshApplied && in_array($existing->status, $refreshableAppliedStatuses, true))) {
                    throw new RuntimeException("Product {$externalId} has an applied or rejected draft and cannot be refreshed.");
                }

                $verifiedName = $this->displayName($row, $product->name, $externalId);
                if ($identityScope === 'model_core'
                    && ! ModelCoreIdentityMatcher::nameContains($verifiedName, (string) $row['model_core'])) {
                    throw new RuntimeException("Product {$externalId} display_name does not contain model_core with exact boundaries.");
                }
                if ($identityScope === 'exact'
                    && ($sourceEvidence['source_tier'] ?? null) === DescriptionSourceEvidencePolicy::MANUFACTURER_PRIMARY_TIER
                    && (! ModelCoreIdentityMatcher::nameContains($verifiedName, (string) $row['manufacturer'])
                        || ! ModelCoreIdentityMatcher::nameEndsWith($verifiedName, (string) $row['mpn']))) {
                    throw new RuntimeException("Product {$externalId} display_name does not preserve the exact manufacturer and MPN identity.");
                }
                $verifiedFields = [
                    'name' => $verifiedName,
                    'manufacturer' => trim($row['manufacturer']),
                ];
                if ($identityScope === 'model_core') {
                    $verifiedFields['model'] = trim($row['model_core']);
                    if (is_string($row['technology'] ?? null) && filled($row['technology'])) {
                        $verifiedFields['technology'] = trim($row['technology']);
                    }
                } else {
                    $verifiedFields['model'] = trim($row['mpn']);
                    $verifiedFields['mpn'] = trim($row['mpn']);
                    $verifiedFields['technology'] = trim($row['technology']);
                }
                if (array_key_exists('technical_attributes', $row)) {
                    if (! is_array($row['technical_attributes'])
                        || collect($row['technical_attributes'])->contains(static fn (mixed $value): bool => ! is_string($value) || blank($value))) {
                        throw new RuntimeException("Product row {$index} technical_attributes must be a non-empty string map.");
                    }
                    $verifiedFields['technical_attributes'] = $row['technical_attributes'];
                }
                if (is_string($row['technology'] ?? null) && filled($row['technology'])) {
                    $technology = trim($row['technology']);
                    $attributes = $verifiedFields['technical_attributes'] ?? [];
                    if (isset($attributes['Технология']) && trim((string) $attributes['Технология']) !== $technology) {
                        throw new RuntimeException("Product row {$index} technology contradicts technical_attributes.Технология.");
                    }
                    $attributes['Технология'] = $technology;
                    $verifiedFields['technical_attributes'] = $attributes;
                }
                $removedAttributes = $this->removedTechnicalAttributes($row, $index);
                if ($removedAttributes !== []) {
                    if (array_intersect($removedAttributes, array_keys($verifiedFields['technical_attributes'] ?? [])) !== []) {
                        throw new RuntimeException("Product row {$index} cannot verify and remove the same technical attribute.");
                    }
                    $verifiedFields['removed_technical_attributes'] = $removedAttributes;
                }

                $draft = $this->drafter->createDraft(
                    $verifiedFields,
                    [trim($row['source_url'])],
                    $product,
                    null,
                    $manifest['locale'],
                    $sourceEvidence,
                );

                if ($draft->status !== 'draft' || blank($draft->content)) {
                    throw new RuntimeException("Product {$externalId} did not produce a reviewable draft.");
                }
                if ($existing !== null) {
                    $existing->update([
                        'title' => $draft->title,
                        'content' => $draft->content,
                        'verified_fields' => $draft->verified_fields,
                        'source_urls' => $draft->source_urls,
                        'source_kind' => $draft->source_kind,
                        'source_tier' => $draft->source_tier,
                        'source_publisher' => $draft->source_publisher,
                        'manufacturer_primary' => $draft->manufacturer_primary,
                        'identity_scope' => $draft->identity_scope,
                        'source_checked_at' => $draft->source_checked_at,
                        'status' => 'draft',
                        'rejection_reason' => null,
                        'submitted_by' => null,
                        'submitted_at' => null,
                    ]);
                    $draft->delete();
                    $summary['refreshed']++;
                } else {
                    $summary['created']++;
                }
            }
        };

        if ($apply) {
            DB::transaction($process);
        } else {
            DB::beginTransaction();
            try {
                $process();
            } finally {
                DB::rollBack();
            }
        }

        return $summary;
    }

    /** @param array<string, mixed> $row */
    private function assertIdentityMatches(Product $product, array $row, string $externalId): void
    {
        foreach (['manufacturer', 'mpn'] as $field) {
            $catalogueValue = ProductIdentity::normalize((string) $product->getAttribute($field));
            $evidenceValue = ProductIdentity::normalize((string) $row[$field]);

            // A source-backed draft may be the first verified source for a
            // 1C record whose structured manufacturer/MPN fields are blank.
            // Blank is not a contradictory identity claim; a non-blank
            // catalogue value still has to match exactly, so a source can
            // never overwrite or mask a known catalogue identity.
            if ($catalogueValue !== null && $catalogueValue !== $evidenceValue) {
                throw new RuntimeException("Product {$externalId} {$field} does not match the verified evidence.");
            }
        }
    }

    /** @param array<string, mixed> $row */
    private function assertModelCoreIdentityMatches(Product $product, array $row, string $externalId): void
    {
        $catalogueManufacturer = ProductIdentity::normalize($product->manufacturer);
        $evidenceManufacturer = ProductIdentity::normalize($row['manufacturer']);
        if ($catalogueManufacturer !== null && $catalogueManufacturer !== $evidenceManufacturer) {
            throw new RuntimeException("Product {$externalId} manufacturer does not match the verified evidence.");
        }

        if (! ModelCoreIdentityMatcher::nameContains($product->name, (string) $row['model_core'])) {
            throw new RuntimeException("Product {$externalId} name does not contain model_core with exact boundaries.");
        }
    }

    /** @param array<string, mixed> $row @param array<string, string> $seenExactMpns */
    private function assertManufacturerPrimaryIdentityMatches(Product $product, array $row, string $externalId, array &$seenExactMpns): void
    {
        if (! ModelCoreIdentityMatcher::nameContains($product->name, (string) $row['manufacturer'])) {
            throw new RuntimeException("Product {$externalId} manufacturer-primary evidence requires the catalogue name to contain the manufacturer.");
        }
        if (! ModelCoreIdentityMatcher::nameEndsWith($product->name, (string) $row['mpn'])) {
            throw new RuntimeException("Product {$externalId} manufacturer-primary evidence requires the catalogue name to end with the exact MPN.");
        }

        $mpnNormalized = ProductIdentity::normalize($row['mpn']);
        if ($mpnNormalized === null) {
            throw new RuntimeException("Product {$externalId} manufacturer-primary MPN cannot be normalized.");
        }
        if (isset($seenExactMpns[$mpnNormalized]) && $seenExactMpns[$mpnNormalized] !== $externalId) {
            throw new RuntimeException("Products {$seenExactMpns[$mpnNormalized]} and {$externalId} repeat the same exact MPN in the manifest.");
        }
        $seenExactMpns[$mpnNormalized] = $externalId;

        $duplicate = Product::query()
            ->where(function ($query) use ($mpnNormalized): void {
                $query->where('mpn_normalized', $mpnNormalized)
                    ->orWhere('sku_normalized', $mpnNormalized);
            })
            ->where('id', '<>', $product->id)
            ->first();
        if ($duplicate !== null) {
            throw new RuntimeException("Product {$externalId} exact MPN already belongs to {$duplicate->external_id}; duplicate creation was blocked.");
        }
    }

    private function assertBitrixTransferEligibility(Product $product, SiteProduct $siteProduct, Site $site, string $externalId): void
    {
        if (! str_starts_with($externalId, 'bitrix:')) {
            return;
        }

        $materialization = CatalogDraftMaterialization::query()
            ->with(['sourceImportRun', 'stagedImportRecord.importRun'])
            ->where('site_id', $site->id)
            ->where('product_id', $product->id)
            ->where('site_product_id', $siteProduct->id)
            ->where('source_namespace', 'bitrix')
            ->where('source_external_id', $externalId)
            ->where('materialization_kind', CatalogDraftMaterialization::KIND_NAMESPACED_DRAFT)
            ->whereHas('stagedImportRecord', static function ($query) use ($externalId): void {
                $query->where('entity_type', 'bitrix_full_catalog_product_evidence')
                    ->where('external_id', $externalId)
                    ->where('status', 'staged_evidence');
            })
            ->first();
        if ($materialization === null || $materialization->stagedImportRecord === null) {
            throw new RuntimeException("Product {$externalId} has no pinned Bitrix staging lineage; manufacturer-primary enrichment was blocked.");
        }

        $stagedRecord = $materialization->stagedImportRecord;
        $expectedSource = 'bitrix_full_catalog_snapshot:'.$site->key;
        if ((int) $materialization->source_import_run_id !== (int) $stagedRecord->import_run_id
            || $materialization->sourceImportRun?->source !== $expectedSource
            || $stagedRecord->importRun?->source !== $expectedSource) {
            throw new RuntimeException("Product {$externalId} has inconsistent Bitrix source-run lineage; manufacturer-primary enrichment was blocked.");
        }

        $normalizedStatus = data_get($stagedRecord->normalized_payload, 'transfer_status');
        $payloadStatus = data_get($stagedRecord->payload, 'transfer_status');
        if ($normalizedStatus !== 'legacy_only_draft_candidate' || $payloadStatus !== 'legacy_only_draft_candidate') {
            $status = $normalizedStatus ?? $payloadStatus ?? 'missing';
            throw new RuntimeException("Product {$externalId} has blocked Bitrix transfer_status {$status}; manufacturer-primary enrichment was blocked.");
        }
    }

    /** @param array<string, mixed> $row */
    private function identityScope(array $row, int $index): string
    {
        $scope = $row['identity_scope'] ?? 'exact';
        if (! is_string($scope) || ! in_array($scope, ['exact', 'model_core'], true)) {
            throw new RuntimeException("Product row {$index} identity_scope must be exact or model_core.");
        }

        return $scope;
    }

    /** @param array<string, mixed> $row */
    private function displayName(array $row, string $fallback, string $externalId): string
    {
        if (! array_key_exists('display_name', $row)) {
            return $fallback;
        }
        if (! is_string($row['display_name']) || blank($row['display_name']) || mb_strlen(trim($row['display_name'])) > 500) {
            throw new RuntimeException("Product {$externalId} display_name must be a non-empty string up to 500 characters.");
        }

        return trim($row['display_name']);
    }

    /** @param array<string, mixed> $row @return list<string> */
    private function removedTechnicalAttributes(array $row, int $index): array
    {
        $removed = $row['remove_technical_attributes'] ?? [];
        if (! is_array($removed) || ! array_is_list($removed)
            || collect($removed)->contains(fn (mixed $key): bool => ! is_string($key) || blank($key))) {
            throw new RuntimeException("Product row {$index} remove_technical_attributes must be a list of non-empty strings.");
        }
        $removed = array_map(static fn (string $key): string => trim($key), $removed);
        if (count(array_unique($removed)) !== count($removed)) {
            throw new RuntimeException("Product row {$index} remove_technical_attributes contains duplicates.");
        }

        return $removed;
    }
}
