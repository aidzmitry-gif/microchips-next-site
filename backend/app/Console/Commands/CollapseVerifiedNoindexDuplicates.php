<?php

namespace App\Console\Commands;

use App\Domain\Content\ModelCoreIdentityMatcher;
use App\Domain\Imports\ProductIdentity;
use App\Events\SiteContentChanged;
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

/** Collapse only explicitly evidenced published noindex duplicates, site by site. */
class CollapseVerifiedNoindexDuplicates extends Command
{
    protected $signature = 'catalog:collapse-verified-noindex-duplicates
                            {site}
                            {file}
                            {--apply}
                            {--evidence-root= : Root used to resolve repository-relative evidence paths}';

    protected $description = '301 reviewed noindex duplicates to a survivor without deleting canonical products or other markets';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }
        try {
            $summary = $this->collapse($site, $this->manifest((string) $this->argument('file')), (bool) $this->option('apply'));
        } catch (Throwable $e) {
            $this->error($e->getMessage());

            return self::FAILURE;
        }
        $this->line(json_encode($summary, JSON_UNESCAPED_UNICODE | JSON_PRETTY_PRINT));

        return self::SUCCESS;
    }

    /** @param list<array<string,mixed>> $rows @return array<string,int|string> */
    private function collapse(Site $site, array $rows, bool $apply): array
    {
        $plans = [];
        $seenDuplicates = [];
        $allSurvivors = [];
        $allDuplicates = [];
        $purposeRepairs = [];

        foreach ($rows as $index => $row) {
            foreach (['survivor_external_id', 'duplicate_external_id', 'survivor_name', 'duplicate_name', 'survivor_path', 'duplicate_path', 'model_core', 'voltage', 'capacity', 'availability'] as $field) {
                if (! is_string($row[$field] ?? null) || blank($row[$field])) {
                    throw new RuntimeException("Row {$index} requires {$field}.");
                }
            }
            $key = trim($row['duplicate_external_id']);
            $survivorKey = trim($row['survivor_external_id']);
            if (isset($seenDuplicates[$key])) {
                throw new RuntimeException("Manifest repeats duplicate {$key}.");
            }
            $seenDuplicates[$key] = true;
            $allDuplicates[] = $key;
            $allSurvivors[] = $survivorKey;
            if ($key === $survivorKey) {
                throw new RuntimeException("Row {$index} duplicate equals survivor.");
            }
            $this->assertLocalPath((string) $row['survivor_path'], "Row {$index} survivor_path");
            $this->assertLocalPath((string) $row['duplicate_path'], "Row {$index} duplicate_path");
            if (trim($row['survivor_path']) === trim($row['duplicate_path'])) {
                throw new RuntimeException("Row {$index} duplicate path equals survivor path.");
            }
            $expectedCategories = $row['category_external_ids'] ?? null;
            if (! is_array($expectedCategories) || $expectedCategories === [] || array_is_list($expectedCategories) === false) {
                throw new RuntimeException("Row {$index} category_external_ids must be a non-empty list.");
            }
            $expectedCategories = array_values(array_map('trim', $expectedCategories));
            if (in_array('', $expectedCategories, true) || count(array_unique($expectedCategories)) !== count($expectedCategories)) {
                throw new RuntimeException("Row {$index} category_external_ids must contain unique non-empty strings.");
            }
            sort($expectedCategories);
            $duplicateExpectedCategories = $row['duplicate_category_external_ids'] ?? $expectedCategories;
            if (! is_array($duplicateExpectedCategories) || $duplicateExpectedCategories === [] || array_is_list($duplicateExpectedCategories) === false) {
                throw new RuntimeException("Row {$index} duplicate_category_external_ids must be a non-empty list when supplied.");
            }
            $duplicateExpectedCategories = array_values(array_map('trim', $duplicateExpectedCategories));
            if (in_array('', $duplicateExpectedCategories, true) || count(array_unique($duplicateExpectedCategories)) !== count($duplicateExpectedCategories)) {
                throw new RuntimeException("Row {$index} duplicate_category_external_ids must contain unique non-empty strings.");
            }
            sort($duplicateExpectedCategories);

            foreach (['survivor', 'duplicate'] as $side) {
                if (! ModelCoreIdentityMatcher::nameContains((string) $row[$side.'_name'], (string) $row['model_core'])) {
                    throw new RuntimeException("Row {$index} {$side} name lacks bounded model_core.");
                }
            }
            $survivor = $this->siteProduct($site, $survivorKey);
            $duplicate = SiteProduct::query()->with('product')->where('site_id', $site->id)
                ->whereHas('product', fn ($q) => $q->where('external_id', $key))->first();
            if ($duplicate === null) {
                $redirect = SiteRedirect::query()->where('site_id', $site->id)
                    ->where('source_path', trim($row['duplicate_path']))
                    ->where('target_path', trim($row['survivor_path']))
                    ->where('status_code', 301)
                    ->where('is_active', true)
                    ->first();
                if ($redirect?->purpose === SiteRedirect::PURPOSE_PREVIEW) {
                    continue;
                }
                if ($redirect?->purpose === SiteRedirect::PURPOSE_SEO) {
                    $purposeRepairs[] = $redirect;

                    continue;
                }
                throw new RuntimeException("Row {$index} duplicate no longer has a site product or matching redirect.");
            }
            if ($survivor->product_id === $duplicate->product_id) {
                throw new RuntimeException("Row {$index} shares canonical product.");
            }
            if (SiteRedirect::query()->where('site_id', $site->id)->where('source_path', trim($row['duplicate_path']))->exists()) {
                throw new RuntimeException("Row {$index} duplicate path already has a redirect.");
            }
            $survivorNameHasFacts = $this->nameContainsFact((string) $row['survivor_name'], (string) $row['voltage'])
                && $this->nameContainsFact((string) $row['survivor_name'], (string) $row['capacity']);
            $duplicateNameHasFacts = $this->nameContainsFact((string) $row['duplicate_name'], (string) $row['voltage'])
                && $this->nameContainsFact((string) $row['duplicate_name'], (string) $row['capacity']);
            if (! $survivorNameHasFacts || ! $duplicateNameHasFacts) {
                $this->assertEvidenceBackedSurvivor($survivor, $row, $index);
            }
            $this->assertSurvivorSafe($site, $survivor, trim($row['survivor_name']), trim($row['survivor_path']), trim($row['availability']), $expectedCategories);
            $this->assertDuplicateSafe($site, $duplicate, trim($row['duplicate_name']), trim($row['duplicate_path']), trim($row['availability']), $duplicateExpectedCategories);
            $plans[] = compact('survivor', 'duplicate', 'row');
        }

        if (array_intersect($allDuplicates, $allSurvivors) !== []) {
            throw new RuntimeException('Manifest cannot contain duplicate-collapse chains.');
        }

        $work = function () use ($site, $plans, $purposeRepairs): void {
            foreach ($purposeRepairs as $redirect) {
                $redirect->update(['purpose' => SiteRedirect::PURPOSE_PREVIEW]);
            }
            foreach ($plans as $plan) {
                $duplicatePath = trim($plan['row']['duplicate_path']);
                $survivorPath = trim($plan['row']['survivor_path']);
                SiteRedirect::query()->create([
                    'site_id' => $site->id,
                    'source_path' => $duplicatePath,
                    'target_path' => $survivorPath,
                    'status_code' => 301,
                    'purpose' => SiteRedirect::PURPOSE_PREVIEW,
                    'is_active' => true,
                ]);
                SiteUrl::query()->where('site_id', $site->id)->where('target_type', 'product')->where('target_id', $plan['duplicate']->id)->delete();
                SiteSeo::query()->where('site_id', $site->id)->where('resource_type', 'product')->where('resource_id', $plan['duplicate']->id)->delete();
                $plan['duplicate']->delete();
            }
        };
        if ($apply) {
            DB::transaction($work);
            SiteContentChanged::dispatch($site, array_values(array_unique([
                ...array_map(fn ($plan): string => trim($plan['row']['duplicate_path']), $plans),
                ...array_map(fn ($plan): string => trim($plan['row']['survivor_path']), $plans),
                ...array_map(fn (SiteRedirect $redirect): string => $redirect->source_path, $purposeRepairs),
                ...array_map(fn (SiteRedirect $redirect): string => $redirect->target_path, $purposeRepairs),
                '/catalog',
                '/sitemap.xml',
            ])));
        }

        return [
            'mode' => $apply ? 'apply' : 'dry_run',
            'requested' => count($rows),
            'collapsed' => count($plans),
            'already_collapsed' => count($rows) - count($plans),
            'redirect_purposes_repaired' => $apply ? count($purposeRepairs) : 0,
            'redirect_purpose_repairs_pending' => $apply ? 0 : count($purposeRepairs),
            'site_products_deleted' => $apply ? count($plans) : 0,
            'canonical_products_deleted' => 0,
        ];
    }

    /** @param list<string> $expectedCategories */
    private function assertSurvivorSafe(Site $site, SiteProduct $sp, string $name, string $path, string $availability, array $expectedCategories): void
    {
        if (! $sp->is_published || $sp->product->name !== $name || $sp->availability !== $availability) {
            throw new RuntimeException("Site product {$sp->id} is not a safe survivor.");
        }
        $currentEvidence = $sp->priceEvidences()->where('is_current', true)->get();
        if ($sp->price === null) {
            if ($currentEvidence->isNotEmpty()) {
                throw new RuntimeException("Site product {$sp->id} has current price evidence without a price.");
            }
        } elseif ($currentEvidence->count() !== 1
            || (string) $currentEvidence->sole()->calculated_price !== (string) $sp->price
            || $currentEvidence->sole()->currency !== $site->currency_code) {
            throw new RuntimeException("Site product {$sp->id} has no exact current price evidence for its published price.");
        }
        $this->assertNoindexState($site, $sp, $path, $expectedCategories, 'survivor');
    }

    /** @param list<string> $expectedCategories */
    private function assertDuplicateSafe(Site $site, SiteProduct $sp, string $name, string $path, string $availability, array $expectedCategories): void
    {
        if (! $sp->is_published || $sp->product->name !== $name || $sp->availability !== $availability || $sp->price !== null || $sp->priceEvidences()->exists()) {
            throw new RuntimeException("Site product {$sp->id} is not a safe noindex duplicate.");
        }
        if (ProductFamily::query()->where('site_id', $site->id)->where('canonical_product_id', $sp->product_id)->exists() || ProductVariant::query()->where('product_id', $sp->product_id)->whereHas('family', fn ($q) => $q->where('site_id', $site->id))->exists()) {
            throw new RuntimeException("Site product {$sp->id} has family role.");
        }
        if ($sp->product->media()->where('verification_status', 'verified')->where('is_published', true)->exists()) {
            throw new RuntimeException("Site product {$sp->id} has verified published media.");
        }
        $this->assertNoindexState($site, $sp, $path, $expectedCategories, 'duplicate');
    }

    /** @param list<string> $expectedCategories */
    private function assertNoindexState(Site $site, SiteProduct $sp, string $path, array $expectedCategories, string $role): void
    {
        $categories = $sp->categories()->pluck('site_categories.external_id')->filter()->sort()->values()->all();
        if ($categories !== $expectedCategories) {
            throw new RuntimeException("Site product {$sp->id} {$role} categories differ from manifest.");
        }
        $urls = SiteUrl::query()->where('site_id', $site->id)->where('target_type', 'product')->where('target_id', $sp->id)->get();
        if ($urls->count() !== 1 || $urls->sole()->path !== $path || $urls->sole()->is_indexable) {
            throw new RuntimeException("Site product {$sp->id} {$role} lacks one exact noindex URL.");
        }
        $seoRows = SiteSeo::query()->where('site_id', $site->id)->where('resource_type', 'product')->where('resource_id', $sp->id)->get();
        if ($seoRows->isEmpty() || $seoRows->contains(fn (SiteSeo $seo): bool => $seo->is_indexable || $seo->schema !== null)) {
            throw new RuntimeException("Site product {$sp->id} {$role} has indexable or schema SEO.");
        }
    }

    /** @param array<string,mixed> $row */
    private function assertEvidenceBackedSurvivor(SiteProduct $survivor, array $row, int $index): void
    {
        foreach (['manufacturer', 'survivor_mpn', 'source_url', 'source_evidence_path', 'source_evidence_sha256', 'source_snapshot_path', 'source_snapshot_sha256'] as $field) {
            if (! is_string($row[$field] ?? null) || blank($row[$field])) {
                throw new RuntimeException("Row {$index} evidence-backed survivor requires {$field}.");
            }
        }
        if (! str_starts_with((string) $row['source_url'], 'https://')) {
            throw new RuntimeException("Row {$index} source_url must be HTTPS.");
        }
        if (ProductIdentity::normalize((string) $survivor->product->manufacturer) !== ProductIdentity::normalize((string) $row['manufacturer'])
            || ProductIdentity::normalize((string) $survivor->product->mpn) !== ProductIdentity::normalize((string) $row['survivor_mpn'])
            || ProductIdentity::normalize((string) $row['survivor_mpn']) !== ProductIdentity::normalize((string) $row['model_core'])) {
            throw new RuntimeException("Row {$index} survivor manufacturer/MPN does not prove the exact model_core.");
        }
        foreach (['source_evidence', 'source_snapshot'] as $prefix) {
            $path = $this->evidencePath((string) $row[$prefix.'_path']);
            $expected = strtolower((string) $row[$prefix.'_sha256']);
            if (preg_match('/^[a-f0-9]{64}$/', $expected) !== 1 || ! is_file($path) || ! is_readable($path)
                || hash_file('sha256', $path) !== $expected) {
                throw new RuntimeException("Row {$index} {$prefix} is missing or has SHA-256 drift.");
            }
        }
    }

    private function nameContainsFact(string $name, string $fact): bool
    {
        return preg_match('/(?<![A-Za-z0-9])'.preg_quote($fact, '/').'(?![A-Za-z0-9])/i', $name) === 1;
    }

    private function evidencePath(string $path): string
    {
        if (preg_match('/^(?:[A-Za-z]:[\\\\\/]|\/)/', $path) === 1) {
            return $path;
        }
        $root = trim((string) $this->option('evidence-root'));
        if ($root === '') {
            $root = base_path('..');
        }

        return rtrim($root, '\\/').DIRECTORY_SEPARATOR.str_replace(['/', '\\'], DIRECTORY_SEPARATOR, $path);
    }

    private function assertLocalPath(string $path, string $label): void
    {
        $path = trim($path);
        if (! str_starts_with($path, '/') || str_starts_with($path, '//') || str_contains($path, '?') || str_contains($path, '#')) {
            throw new RuntimeException("{$label} must be a safe local path.");
        }
    }

    private function siteProduct(Site $site, string $externalId): SiteProduct
    {
        return SiteProduct::query()->with('product')->where('site_id', $site->id)->whereHas('product', fn ($q) => $q->where('external_id', $externalId))->sole();
    }

    /** @return list<array<string,mixed>> */
    private function manifest(string $file): array
    {
        if (! is_readable($file)) {
            throw new RuntimeException('Manifest is not readable.');
        }
        $data = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($data) || ($data['schema_version'] ?? null) !== 1 || ! is_array($data['duplicates'] ?? null) || $data['duplicates'] === []) {
            throw new RuntimeException('Manifest requires schema_version=1 and non-empty duplicates.');
        }

        return $data['duplicates'];
    }
}
