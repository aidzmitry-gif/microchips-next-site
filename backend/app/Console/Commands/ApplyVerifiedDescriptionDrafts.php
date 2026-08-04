<?php

namespace App\Console\Commands;

use App\Domain\Content\DescriptionSourceEvidencePolicy;
use App\Domain\Content\ModelCoreIdentityMatcher;
use App\Domain\Imports\ProductIdentity;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/** Applies explicit source-backed editorial drafts without publishing products. */
class ApplyVerifiedDescriptionDrafts extends Command
{
    protected $signature = 'content:apply-verified-description-drafts
                            {site : Site key}
                            {file : JSON source-backed manifest used to create drafts}
                            {--apply : Persist product description and verified attributes; default is dry-run}';

    protected $description = 'Apply only source-backed editorial drafts to canonical product content; never publish or alter commercial data';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }
        $apply = (bool) $this->option('apply');
        $run = ImportRun::create(['source' => 'apply_verified_description_drafts', 'source_file' => basename((string) $this->argument('file')), 'status' => 'running', 'started_at' => now()]);

        try {
            $summary = $this->apply($site, (string) $this->argument('file'), $apply);
            $run->update([
                'status' => $apply ? 'completed' : 'dry_run_complete',
                'total_records' => $summary['records'],
                'processed_records' => $apply ? $summary['applied'] : 0,
                'summary' => $summary,
                'finished_at' => now(),
            ]);
            $this->info(sprintf('%s %d source-backed description(s); %d unchanged. No products were published or given commercial data.', $apply ? 'Applied' : 'Validated', $summary['applied'], $summary['unchanged']));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $run->update(['status' => 'failed', 'summary' => ['mode' => $apply ? 'apply' : 'dry_run', 'error' => $error->getMessage()], 'finished_at' => now()]);
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /** @return array{records: int, applied: int, unchanged: int, publications_changed: int, commercial_fields_changed: int} */
    private function apply(Site $site, string $file, bool $apply): array
    {
        $manifest = $this->manifest($file);
        if (($manifest['locale'] ?? null) !== $site->default_locale || ! is_array($manifest['products'] ?? null)) {
            throw new RuntimeException('Manifest locale must match the site default locale and contain products.');
        }
        $summary = ['records' => count($manifest['products']), 'applied' => 0, 'unchanged' => 0, 'publications_changed' => 0, 'commercial_fields_changed' => 0];
        $work = function () use ($site, $manifest, &$summary): void {
            foreach ($manifest['products'] as $index => $evidence) {
                if (! is_array($evidence) || ! is_string($evidence['external_id'] ?? null) || ! is_string($evidence['source_url'] ?? null)) {
                    throw new RuntimeException("Manifest row {$index} requires external_id and source_url.");
                }
                $sourceEvidence = DescriptionSourceEvidencePolicy::fromManifestRow($evidence, $index);
                $identityScope = $this->identityScope($evidence, $index);
                $externalId = trim($evidence['external_id']);
                $draft = ProductDescriptionDraft::query()
                    ->with('product')
                    ->where('locale', $site->default_locale)
                    ->whereHas('product', fn ($query) => $query->where('external_id', $externalId))
                    ->latest('id')
                    ->first();
                if ($draft === null || $draft->product === null || blank($draft->content) || ! in_array($draft->status, ['draft', 'review'], true)) {
                    throw new RuntimeException("Product {$externalId} has no applicable source-backed editorial draft.");
                }
                $this->assertSourceEvidenceMatches($draft, $sourceEvidence, $externalId);
                if (! in_array(trim($evidence['source_url']), $draft->source_urls ?? [], true)) {
                    throw new RuntimeException("Product {$externalId} draft source does not match the manifest.");
                }
                if (! $draft->product->sites()->where('site_id', $site->id)->exists()) {
                    throw new RuntimeException("Product {$externalId} is not assigned to site {$site->key}.");
                }

                $currentAttributes = $draft->product->technical_attributes ?? [];
                $attributes = $currentAttributes;
                $verifiedAttributes = $draft->verified_fields['technical_attributes'] ?? [];
                if (! is_array($verifiedAttributes) || collect($verifiedAttributes)->contains(static fn (mixed $value): bool => ! is_string($value) || blank($value))) {
                    throw new RuntimeException("Product {$externalId} has no valid verified technical attributes.");
                }
                $dealerBacked = ($sourceEvidence['source_tier'] ?? null) === DescriptionSourceEvidencePolicy::DEALER_TIER;
                if ($dealerBacked) {
                    foreach ($verifiedAttributes as $key => $value) {
                        if (array_key_exists($key, $attributes) && $attributes[$key] !== $value) {
                            throw new RuntimeException("Product {$externalId} dealer-backed evidence conflicts with canonical attribute {$key}.");
                        }
                    }
                }
                $removedAttributes = $this->removedTechnicalAttributes($evidence, $index);
                if (($draft->verified_fields['removed_technical_attributes'] ?? []) !== $removedAttributes) {
                    throw new RuntimeException("Product {$externalId} removed technical attributes do not match the reviewed manifest.");
                }
                foreach ($removedAttributes as $key) {
                    unset($attributes[$key]);
                }
                $nextAttributes = [...$attributes, ...$verifiedAttributes];
                $verifiedName = $draft->verified_fields['name'] ?? null;
                if (! is_string($verifiedName) || blank($verifiedName)) {
                    throw new RuntimeException("Product {$externalId} draft has no valid verified display name.");
                }
                $nextName = trim($verifiedName);
                // A source-backed draft was staged only after its identity
                // matched the existing catalogue value (or that value was
                // blank). Therefore it may fill an absent manufacturer/MPN,
                // but it must never replace a populated canonical identity.
                $verifiedManufacturer = $draft->verified_fields['manufacturer'] ?? null;
                $verifiedMpn = $draft->verified_fields['mpn'] ?? null;
                if (! is_string($verifiedManufacturer) || blank($verifiedManufacturer)) {
                    throw new RuntimeException("Product {$externalId} draft has no valid verified identity.");
                }
                if ($identityScope === 'model_core') {
                    $this->assertModelCoreIdentityMatches($draft->product, $draft->verified_fields, $evidence, $externalId);
                    if (! ModelCoreIdentityMatcher::nameContains($nextName, (string) $evidence['model_core'])) {
                        throw new RuntimeException("Product {$externalId} draft display name does not contain model_core with exact boundaries.");
                    }
                } elseif (! is_string($verifiedMpn) || blank($verifiedMpn)) {
                    throw new RuntimeException("Product {$externalId} draft has no valid verified identity.");
                }
                $nextName = $dealerBacked ? $draft->product->name : $nextName;
                $nextManufacturer = $dealerBacked
                    ? $draft->product->manufacturer
                    : (blank($draft->product->manufacturer)
                    ? trim($verifiedManufacturer)
                    : $draft->product->manufacturer);
                $nextMpn = $dealerBacked || $identityScope === 'model_core'
                    ? $draft->product->mpn
                    : (blank($draft->product->mpn)
                    ? trim($verifiedMpn)
                    : $draft->product->mpn);
                $changed = $draft->product->name !== $nextName
                    || $draft->product->short_description !== $draft->content
                    || $currentAttributes !== $nextAttributes
                    || $draft->product->manufacturer !== $nextManufacturer
                    || $draft->product->mpn !== $nextMpn;
                if (! $changed) {
                    // A refresh can regenerate an editorial draft whose
                    // source-backed facts are already present on the product.
                    // Leaving that draft in `draft` would make the next run
                    // look unresolved even though it has been fully checked.
                    // Marking it applied records the verification result but
                    // does not touch product, publication or commercial data.
                    if ($draft->status !== 'applied') {
                        $draft->update(['status' => 'applied']);
                    }
                    $this->synchroniseNoindexPreviewSeo($site, $draft->product);
                    $summary['unchanged']++;

                    continue;
                }
                $draft->product->update([
                    'name' => $nextName,
                    'short_description' => $draft->content,
                    'technical_attributes' => $nextAttributes,
                    'manufacturer' => $nextManufacturer,
                    'mpn' => $nextMpn,
                ]);
                $draft->update(['status' => 'applied']);
                $this->synchroniseNoindexPreviewSeo($site, $draft->product->refresh());
                $summary['applied']++;
            }
        };
        if ($apply) {
            DB::transaction($work);
        } else {
            DB::beginTransaction();
            try {
                $work();
            } finally {
                DB::rollBack();
            }
        }

        return $summary;
    }

    /** @return array<string, mixed> */
    private function manifest(string $file): array
    {
        if (! is_readable($file)) {
            throw new RuntimeException('Source-backed manifest is not readable.');
        }
        try {
            $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $error) {
            throw new RuntimeException('Source-backed manifest is not valid JSON.', previous: $error);
        }
        if (! is_array($manifest)) {
            throw new RuntimeException('Source-backed manifest must be an object.');
        }

        return $manifest;
    }

    /** @param array<string, mixed> $row */
    private function identityScope(array $row, int $index): string
    {
        $scope = $row['identity_scope'] ?? 'exact';
        if (! is_string($scope) || ! in_array($scope, ['exact', 'model_core'], true)) {
            throw new RuntimeException("Manifest row {$index} identity_scope must be exact or model_core.");
        }

        return $scope;
    }

    /** @param array<string, mixed> $row @return list<string> */
    private function removedTechnicalAttributes(array $row, int $index): array
    {
        $removed = $row['remove_technical_attributes'] ?? [];
        if (! is_array($removed) || ! array_is_list($removed)
            || collect($removed)->contains(fn (mixed $key): bool => ! is_string($key) || blank($key))) {
            throw new RuntimeException("Manifest row {$index} remove_technical_attributes must be a list of non-empty strings.");
        }
        $removed = array_map(static fn (string $key): string => trim($key), $removed);
        if (count(array_unique($removed)) !== count($removed)) {
            throw new RuntimeException("Manifest row {$index} remove_technical_attributes contains duplicates.");
        }

        return $removed;
    }

    /** @param array<string, mixed>|null $expected */
    private function assertSourceEvidenceMatches(ProductDescriptionDraft $draft, ?array $expected, string $externalId): void
    {
        if ($expected === null) {
            if ($draft->source_tier !== null || $draft->source_kind !== null) {
                throw new RuntimeException("Product {$externalId} manifest omits persisted source provenance.");
            }

            return;
        }

        $actual = [
            'source_kind' => $draft->source_kind,
            'source_tier' => $draft->source_tier,
            'source_publisher' => $draft->source_publisher,
            'manufacturer_primary' => $draft->manufacturer_primary,
            'identity_scope' => $draft->identity_scope,
            'checked_at' => $draft->source_checked_at?->format('Y-m-d'),
        ];
        if ($actual !== $expected || ($draft->verified_fields['source_evidence'] ?? null) !== $expected) {
            throw new RuntimeException("Product {$externalId} draft source provenance does not match the manifest.");
        }
    }

    /**
     * @param  array<string, mixed>  $verifiedFields
     * @param  array<string, mixed>  $evidence
     */
    private function assertModelCoreIdentityMatches(Product $product, array $verifiedFields, array $evidence, string $externalId): void
    {
        if (! is_string($evidence['model_core'] ?? null) || blank($evidence['model_core'])) {
            throw new RuntimeException("Product {$externalId} model_core evidence is required.");
        }
        $verifiedModel = $verifiedFields['model'] ?? null;
        if (! is_string($verifiedModel)
            || ProductIdentity::normalize($verifiedModel) !== ProductIdentity::normalize($evidence['model_core'])) {
            throw new RuntimeException("Product {$externalId} draft model_core does not match the manifest.");
        }

        $verifiedManufacturer = $verifiedFields['manufacturer'] ?? null;
        if (! is_string($verifiedManufacturer)
            || ProductIdentity::normalize($verifiedManufacturer) !== ProductIdentity::normalize($evidence['manufacturer'] ?? null)) {
            throw new RuntimeException("Product {$externalId} draft manufacturer does not match the manifest.");
        }
        $catalogueManufacturer = ProductIdentity::normalize($product->manufacturer);
        if ($catalogueManufacturer !== null
            && $catalogueManufacturer !== ProductIdentity::normalize($verifiedManufacturer)) {
            throw new RuntimeException("Product {$externalId} manufacturer conflicts with the verified evidence.");
        }
        if (! ModelCoreIdentityMatcher::nameContains($product->name, (string) $evidence['model_core'])) {
            throw new RuntimeException("Product {$externalId} name does not contain model_core with exact boundaries.");
        }
    }

    /**
     * A noindex preview SEO record is generated from the product snapshot at
     * preview-publication time. If later evidence corrects its source-backed
     * display name or description, that record must move with the product;
     * otherwise the H1, title and meta description silently diverge. Only
     * non-indexable preview records are touched, so authored SEO records are
     * never overwritten.
     */
    private function synchroniseNoindexPreviewSeo(Site $site, Product $product): void
    {
        $siteProduct = SiteProduct::query()
            ->where('site_id', $site->id)
            ->where('product_id', $product->id)
            ->first();
        if ($siteProduct === null) {
            return;
        }

        $seo = SiteSeo::query()
            ->where('site_id', $site->id)
            ->where('locale', $site->default_locale)
            ->where('resource_type', 'product')
            ->where('resource_id', $siteProduct->id)
            ->where('is_indexable', false)
            ->first();
        if ($seo === null) {
            return;
        }

        $seo->update([
            'title' => $product->name,
            'description' => $product->short_description,
        ]);
    }
}
