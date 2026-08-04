<?php

namespace App\Console\Commands;

use App\Domain\Imports\ProductIdentity;
use App\Domain\Sites\SiteResolver;
use App\Events\SiteContentChanged;
use App\Models\Product;
use App\Models\ProductDescriptionDraft;
use App\Models\ProductFamily;
use App\Models\ProductVariant;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class ImportProductFamilies extends Command
{
    protected $signature = 'catalog:import-product-families
                            {site : Site key}
                            {file : Reviewed JSON family manifest}
                            {--apply : Persist verified family relationships; default is dry-run}';

    protected $description = 'Import explicitly reviewed product families without creating variant URLs or SEO duplicates';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $manifest = $this->manifest((string) $this->argument('file'));
            $summary = $this->import($site, $manifest, (bool) $this->option('apply'));
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /** @param array<string, mixed> $manifest
     * @return array{mode:string,families:int,variants:int,variant_urls_retired:int,redirects_created:int,variant_urls_created:int,indexable_resources_created:int}
     */
    private function import(Site $site, array $manifest, bool $apply): array
    {
        if (($manifest['schema_version'] ?? null) !== 1 || ($manifest['site_key'] ?? null) !== $site->key) {
            throw new RuntimeException('Family manifest schema_version/site_key does not match the selected site.');
        }
        $families = $manifest['families'] ?? null;
        if (! is_array($families) || $families === []) {
            throw new RuntimeException('Family manifest must contain at least one family.');
        }

        $seenFamilies = [];
        $seenProducts = [];
        $variantCount = 0;
        $retiredUrls = 0;
        $redirectsCreated = 0;
        foreach ($families as $index => $family) {
            if (! is_array($family)) {
                throw new RuntimeException("Family row {$index} must be an object.");
            }
            $this->preflightFamily($site, $family, $seenFamilies, $seenProducts);
            $variantCount += count($family['variants']);
        }

        $work = function () use ($site, $families, &$retiredUrls, &$redirectsCreated): void {
            foreach ($families as $family) {
                $this->persistFamily($site, $family, $retiredUrls, $redirectsCreated);
            }
        };
        if ($apply) {
            DB::transaction($work);
            $canonicalProductIds = collect($families)
                ->map(fn (array $family): int => $this->siteProduct($site, trim($family['canonical_external_id']))->id)
                ->all();
            $paths = SiteUrl::query()
                ->where('site_id', $site->id)
                ->where('target_type', 'product')
                ->whereIn('target_id', $canonicalProductIds)
                ->pluck('path')
                ->all();
            SiteContentChanged::dispatch($site, array_values(array_unique([...$paths, '/catalog', '/sitemap.xml'])));
        } else {
            DB::beginTransaction();
            try {
                $work();
            } finally {
                DB::rollBack();
            }
        }

        return [
            'mode' => $apply ? 'apply' : 'dry_run',
            'families' => count($families),
            'variants' => $variantCount,
            'variant_urls_retired' => $retiredUrls,
            'redirects_created' => $redirectsCreated,
            'variant_urls_created' => 0,
            'indexable_resources_created' => 0,
        ];
    }

    /** @param array<string, mixed> $family @param array<string, bool> $seenFamilies @param array<string, bool> $seenProducts */
    private function preflightFamily(Site $site, array $family, array &$seenFamilies, array &$seenProducts): void
    {
        foreach (['family_key', 'name', 'canonical_external_id', 'manufacturer', 'model_core', 'selector_label', 'canonical_label', 'source_url'] as $field) {
            if (! is_string($family[$field] ?? null) || blank(trim($family[$field]))) {
                throw new RuntimeException("Family requires a non-empty {$field}.");
            }
        }
        $familyKey = trim($family['family_key']);
        $canonicalExternalId = trim($family['canonical_external_id']);
        $this->assertSafeKey($familyKey, 'family_key');
        $this->assertHttpsUrl(trim($family['source_url']), "family {$familyKey}");
        $this->assertStringMap($family['shared_attributes'] ?? [], "family {$familyKey} shared_attributes");
        $this->assertStringMap($family['canonical_attributes'] ?? [], "family {$familyKey} canonical_attributes");
        if (isset($seenFamilies[$familyKey])) {
            throw new RuntimeException("Family manifest repeats family_key {$familyKey}.");
        }
        if (isset($seenProducts[$canonicalExternalId])) {
            throw new RuntimeException("Product {$canonicalExternalId} occurs in more than one family role.");
        }
        $seenFamilies[$familyKey] = true;
        $seenProducts[$canonicalExternalId] = true;

        $canonical = $this->siteProduct($site, $canonicalExternalId);
        if (! $canonical->is_published) {
            throw new RuntimeException("Canonical product {$canonicalExternalId} must already be a published noindex preview.");
        }
        if ($canonical->product->familyVariants()->whereHas('family', fn ($query) => $query->where('site_id', $site->id))->exists()) {
            throw new RuntimeException("Canonical product {$canonicalExternalId} is already a child variant.");
        }
        $existingFamily = ProductFamily::query()->where('site_id', $site->id)->where('family_key', $familyKey)->first();
        if ($existingFamily !== null && $existingFamily->canonical_product_id !== $canonical->product_id) {
            throw new RuntimeException("Family key {$familyKey} belongs to another canonical product.");
        }
        $otherFamily = ProductFamily::query()->where('site_id', $site->id)->where('canonical_product_id', $canonical->product_id)->first();
        if ($otherFamily !== null && $otherFamily->family_key !== $familyKey) {
            throw new RuntimeException("Canonical product {$canonicalExternalId} already owns another family.");
        }
        $this->assertCanonicalUrl($site, $canonical);
        $this->assertIdentity($canonical->product, trim($family['manufacturer']), trim($family['model_core']), $canonicalExternalId);
        $this->assertAppliedOfficialEvidence(
            $canonical->product,
            $site->default_locale,
            trim($family['source_url']),
            $canonicalExternalId,
            [...($family['shared_attributes'] ?? []), ...($family['canonical_attributes'] ?? [])],
        );

        $variants = $family['variants'] ?? null;
        if (! is_array($variants) || $variants === []) {
            throw new RuntimeException("Family {$familyKey} must contain at least one reviewed variant.");
        }
        $seenVariantKeys = [];
        $manifestVariantProductIds = [];
        foreach ($variants as $variantIndex => $variant) {
            if (! is_array($variant)) {
                throw new RuntimeException("Family {$familyKey} variant {$variantIndex} must be an object.");
            }
            foreach (['external_id', 'variant_key', 'label', 'source_url'] as $field) {
                if (! is_string($variant[$field] ?? null) || blank(trim($variant[$field]))) {
                    throw new RuntimeException("Family {$familyKey} variant requires a non-empty {$field}.");
                }
            }
            $externalId = trim($variant['external_id']);
            $variantKey = trim($variant['variant_key']);
            $this->assertSafeKey($variantKey, "family {$familyKey} variant_key");
            $this->assertHttpsUrl(trim($variant['source_url']), "variant {$externalId}");
            $this->assertStringMap($variant['attributes'] ?? [], "variant {$externalId} attributes");
            if (isset($seenVariantKeys[$variantKey])) {
                throw new RuntimeException("Family {$familyKey} repeats variant_key {$variantKey}.");
            }
            if (isset($seenProducts[$externalId])) {
                throw new RuntimeException("Product {$externalId} occurs in more than one family role.");
            }
            $seenVariantKeys[$variantKey] = true;
            $seenProducts[$externalId] = true;
            $siteProduct = $this->siteProduct($site, $externalId);
            $manifestVariantProductIds[] = $siteProduct->product_id;
            if ($siteProduct->product_id === $canonical->product_id || ProductFamily::query()->where('site_id', $site->id)->where('canonical_product_id', $siteProduct->product_id)->exists()) {
                throw new RuntimeException("Variant {$externalId} is also a canonical family product.");
            }
            $existingVariant = ProductVariant::query()
                ->where('product_id', $siteProduct->product_id)
                ->whereHas('family', fn ($query) => $query->where('site_id', $site->id))
                ->first();
            if ($existingVariant !== null && ($existingFamily === null || $existingVariant->product_family_id !== $existingFamily->id)) {
                throw new RuntimeException("Variant {$externalId} already belongs to another family.");
            }
            $this->assertVariantUrlPlan($site, $siteProduct, $canonical, $variant);
            if (SiteSeo::query()->where('site_id', $site->id)->where('resource_type', 'product')->where('resource_id', $siteProduct->id)->where('is_indexable', true)->exists()) {
                throw new RuntimeException("Variant {$externalId} has indexable SEO state.");
            }
            $this->assertIdentity($siteProduct->product, trim($family['manufacturer']), trim($family['model_core']), $externalId);
            $this->assertAppliedOfficialEvidence(
                $siteProduct->product,
                $site->default_locale,
                trim($variant['source_url']),
                $externalId,
                [...($family['shared_attributes'] ?? []), ...($variant['attributes'] ?? [])],
            );
        }
        if ($existingFamily !== null && $existingFamily->variants()->active()->whereNotIn('product_id', $manifestVariantProductIds)->exists()) {
            throw new RuntimeException("Family {$familyKey} cannot silently remove an active variant; use an explicit retirement workflow.");
        }
    }

    /** @param array<string, mixed> $family */
    private function persistFamily(Site $site, array $family, int &$retiredUrls, int &$redirectsCreated): void
    {
        $canonical = $this->siteProduct($site, trim($family['canonical_external_id']));
        $record = ProductFamily::query()->updateOrCreate(
            ['site_id' => $site->id, 'family_key' => trim($family['family_key'])],
            [
                'canonical_product_id' => $canonical->product_id,
                'name' => trim($family['name']),
                'manufacturer' => trim($family['manufacturer']),
                'model_core' => trim($family['model_core']),
                'selector_label' => trim($family['selector_label']),
                'canonical_label' => trim($family['canonical_label']),
                'canonical_attributes' => $family['canonical_attributes'] ?? [],
                'shared_attributes' => $family['shared_attributes'] ?? [],
                'source_url' => trim($family['source_url']),
                'status' => ProductFamily::STATUS_VERIFIED,
            ],
        );
        $canonicalCategoryIds = $canonical->categories()->pluck('site_categories.id')->all();
        if ($canonicalCategoryIds === []) {
            throw new RuntimeException("Canonical product {$canonical->product->external_id} has no site category.");
        }
        $canonicalPath = SiteUrl::query()
            ->where('site_id', $site->id)
            ->where('target_type', 'product')
            ->where('target_id', $canonical->id)
            ->sole()
            ->path;

        foreach ($family['variants'] as $variant) {
            $siteProduct = $this->siteProduct($site, trim($variant['external_id']));
            foreach ($variant['retire_paths'] ?? [] as $path) {
                $deleted = SiteUrl::query()
                    ->where('site_id', $site->id)
                    ->where('path', $path)
                    ->where('target_type', 'product')
                    ->where('target_id', $siteProduct->id)
                    ->delete();
                $redirectExists = SiteRedirect::query()
                    ->where('site_id', $site->id)
                    ->where('source_path', $path)
                    ->exists();
                SiteRedirect::query()->updateOrCreate(
                    ['site_id' => $site->id, 'source_path' => $path],
                    [
                        'target_path' => $canonicalPath,
                        'status_code' => 301,
                        'purpose' => SiteRedirect::PURPOSE_PREVIEW,
                        'is_active' => true,
                    ],
                );
                $retiredUrls += $deleted;
                if (! $redirectExists) {
                    $redirectsCreated++;
                }
            }
            if (($variant['retire_paths'] ?? []) !== []) {
                SiteSeo::query()
                    ->where('site_id', $site->id)
                    ->where('resource_type', 'product')
                    ->where('resource_id', $siteProduct->id)
                    ->delete();
            }
            ProductVariant::query()->updateOrCreate(
                ['product_family_id' => $record->id, 'product_id' => $siteProduct->product_id],
                [
                    'variant_key' => trim($variant['variant_key']),
                    'label' => trim($variant['label']),
                    'attributes' => $variant['attributes'] ?? [],
                    'source_url' => trim($variant['source_url']),
                    'is_active' => true,
                ],
            );
            $siteProduct->categories()->sync($canonicalCategoryIds);
            $siteProduct->update(['is_published' => true]);
        }
    }

    /** @param array<string, mixed> $variant */
    private function assertVariantUrlPlan(
        Site $site,
        SiteProduct $siteProduct,
        SiteProduct $canonicalSiteProduct,
        array $variant,
    ): void {
        $externalId = (string) $siteProduct->product->external_id;
        $retirePaths = $variant['retire_paths'] ?? [];
        if (! is_array($retirePaths) || collect($retirePaths)->contains(
            fn (mixed $path): bool => ! is_string($path) || ! $this->isSafeLocalPath($path),
        )) {
            throw new RuntimeException("Variant {$externalId} retire_paths must contain safe local paths.");
        }
        if (count(array_unique($retirePaths)) !== count($retirePaths)) {
            throw new RuntimeException("Variant {$externalId} retire_paths contains duplicates.");
        }

        $urls = SiteUrl::query()
            ->where('site_id', $site->id)
            ->where('target_type', 'product')
            ->where('target_id', $siteProduct->id)
            ->get();
        $actual = $urls->pluck('path')->sort()->values()->all();
        $expected = collect($retirePaths)->sort()->values()->all();
        $canonicalPath = SiteUrl::query()
            ->where('site_id', $site->id)
            ->where('target_type', 'product')
            ->where('target_id', $canonicalSiteProduct->id)
            ->sole()
            ->path;
        $alreadyRetired = $actual === [] && $expected !== [] && collect($expected)->every(
            fn (string $path): bool => SiteRedirect::query()
                ->where('site_id', $site->id)
                ->where('source_path', $path)
                ->where('target_path', $canonicalPath)
                ->where('status_code', 301)
                ->where('is_active', true)
                ->exists(),
        );
        if ($actual !== $expected && ! $alreadyRetired) {
            throw new RuntimeException("Variant {$externalId} URL set does not exactly match retire_paths.");
        }
        if ($urls->contains(fn (SiteUrl $url): bool => $url->is_indexable)) {
            throw new RuntimeException("Variant {$externalId} has an indexable URL and cannot be auto-retired.");
        }
        foreach ($retirePaths as $path) {
            $redirect = SiteRedirect::query()->where('site_id', $site->id)->where('source_path', $path)->first();
            if ($redirect !== null && ! $alreadyRetired) {
                throw new RuntimeException("Variant {$externalId} retire path {$path} already has a redirect.");
            }
        }
    }

    private function isSafeLocalPath(string $path): bool
    {
        return app(SiteResolver::class)->isSafeLocalPath($path);
    }

    private function siteProduct(Site $site, string $externalId): SiteProduct
    {
        return SiteProduct::query()
            ->with('product')
            ->where('site_id', $site->id)
            ->whereHas('product', fn ($query) => $query->where('external_id', $externalId))
            ->sole();
    }

    private function assertCanonicalUrl(Site $site, SiteProduct $siteProduct): void
    {
        $urls = SiteUrl::query()
            ->where('site_id', $site->id)
            ->where('target_type', 'product')
            ->where('target_id', $siteProduct->id)
            ->get();
        if ($urls->count() !== 1 || $urls->first()->is_indexable) {
            throw new RuntimeException("Canonical product {$siteProduct->product->external_id} requires exactly one noindex URL.");
        }
    }

    private function assertIdentity(Product $product, string $manufacturer, string $modelCore, string $externalId): void
    {
        if (ProductIdentity::normalize($product->manufacturer) !== ProductIdentity::normalize($manufacturer)) {
            throw new RuntimeException("Canonical product {$externalId} manufacturer conflicts with the family manifest.");
        }
        $normalizedName = ProductIdentity::normalize($product->name) ?? '';
        $normalizedCore = ProductIdentity::normalize($modelCore) ?? '';
        if ($normalizedCore === '' || ! str_contains($normalizedName, $normalizedCore)) {
            throw new RuntimeException("Canonical product {$externalId} name does not contain the reviewed model core.");
        }
    }

    /** @param array<string, string> $requiredAttributes */
    private function assertAppliedOfficialEvidence(
        Product $product,
        string $locale,
        string $sourceUrl,
        string $externalId,
        array $requiredAttributes,
    ): void {
        $draft = ProductDescriptionDraft::query()
            ->where('product_id', $product->id)
            ->where('locale', $locale)
            ->where('status', 'applied')
            ->whereJsonContains('source_urls', $sourceUrl)
            ->latest('id')
            ->first();
        // Older primary-manufacturer drafts predate the explicit provenance
        // columns and legitimately store NULL. Exact source URL equality is
        // still required; an explicit dealer/non-primary marker always blocks.
        if ($draft === null || $draft->manufacturer_primary === false || $draft->source_tier === 'dealer_backed') {
            throw new RuntimeException("Product {$externalId} lacks applied primary-manufacturer evidence for {$sourceUrl}.");
        }
        $verifiedAttributes = $draft->verified_fields['technical_attributes'] ?? [];
        foreach ($requiredAttributes as $key => $value) {
            if (! is_array($verifiedAttributes) || ($verifiedAttributes[$key] ?? null) !== $value) {
                throw new RuntimeException("Product {$externalId} family fact {$key} is not present in the applied source evidence.");
            }
        }
    }

    private function assertStringMap(mixed $attributes, string $label): void
    {
        if (! is_array($attributes) || ($attributes !== [] && array_is_list($attributes))) {
            throw new RuntimeException("{$label} must be an object of verified string facts.");
        }
        foreach ($attributes as $key => $value) {
            if (! is_string($key) || blank($key) || ! is_string($value) || blank($value)) {
                throw new RuntimeException("{$label} contains a blank or non-string fact.");
            }
        }
    }

    private function assertSafeKey(string $key, string $label): void
    {
        if (! preg_match('/^[a-z0-9]+(?:-[a-z0-9]+)*$/', $key)) {
            throw new RuntimeException("{$label} must use lowercase ASCII kebab-case.");
        }
    }

    private function assertHttpsUrl(string $url, string $label): void
    {
        $parts = parse_url($url);
        if ($parts === false || ($parts['scheme'] ?? null) !== 'https' || blank($parts['host'] ?? null)) {
            throw new RuntimeException("{$label} requires an absolute HTTPS source URL.");
        }
    }

    /** @return array<string, mixed> */
    private function manifest(string $file): array
    {
        if (! is_readable($file)) {
            throw new RuntimeException('Family manifest is not readable.');
        }
        try {
            $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $error) {
            throw new RuntimeException('Family manifest is not valid JSON.', previous: $error);
        }
        if (! is_array($manifest)) {
            throw new RuntimeException('Family manifest must be an object.');
        }

        return $manifest;
    }
}
