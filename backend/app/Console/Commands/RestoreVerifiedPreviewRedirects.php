<?php

namespace App\Console\Commands;

use App\Events\SiteContentChanged;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteRedirect;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class RestoreVerifiedPreviewRedirects extends Command
{
    protected $signature = 'catalog:restore-verified-preview-redirects
                            {site : Site key}
                            {file : Reviewed JSON registry of exact redirect pairs}
                            {--apply : Persist redirects; default is a dry-run}';

    protected $description = 'Restore reviewed noindex preview redirects without changing catalogue or commercial state';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $summary = $this->restore(
                $site,
                (string) $this->argument('file'),
                (bool) $this->option('apply'),
            );
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /** @return array<string, int|string> */
    private function restore(Site $site, string $file, bool $apply): array
    {
        $rows = $this->manifest($site, $file);
        $validated = [];
        $alreadyRestored = 0;
        $pending = 0;

        foreach ($rows as $index => $row) {
            $validatedRow = $this->validateRow($site, $row, $index);
            $validated[] = $validatedRow;
            if ($validatedRow['existing']) {
                $alreadyRestored++;
            } else {
                $pending++;
            }
        }

        $restored = 0;
        if ($apply && $pending > 0) {
            DB::transaction(function () use ($site, $validated, &$restored): void {
                foreach ($validated as $row) {
                    if ($row['existing']) {
                        continue;
                    }

                    SiteRedirect::withoutEvents(fn (): SiteRedirect => SiteRedirect::query()->create([
                        'site_id' => $site->id,
                        'source_path' => $row['source_path'],
                        'target_path' => $row['target_path'],
                        'status_code' => 301,
                        'purpose' => SiteRedirect::PURPOSE_PREVIEW,
                        'is_active' => true,
                    ]));
                    $restored++;
                }

                if ($restored > 0) {
                    $paths = ['/catalog', '/sitemap.xml'];
                    foreach ($validated as $row) {
                        if (! $row['existing']) {
                            $paths[] = $row['source_path'];
                            $paths[] = $row['target_path'];
                        }
                    }
                    SiteContentChanged::dispatch($site, array_values(array_unique($paths)));
                }
            });
        }

        return [
            'mode' => $apply ? 'apply' : 'dry_run',
            'requested_redirects' => count($validated),
            'pending_redirects' => $pending,
            'already_restored' => $alreadyRestored,
            'restored_redirects' => $restored,
            'product_mutations' => 0,
            'price_mutations' => 0,
            'availability_mutations' => 0,
            'indexable_urls_created' => 0,
        ];
    }

    /** @return list<array<string, mixed>> */
    private function manifest(Site $site, string $file): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Redirect registry is not readable.');
        }

        $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest)
            || ($manifest['schema_version'] ?? null) !== 1
            || ($manifest['site_key'] ?? null) !== $site->key
            || ! is_array($manifest['redirects'] ?? null)
            || ! is_int($manifest['expected_redirects'] ?? null)
            || $manifest['expected_redirects'] !== count($manifest['redirects'])) {
            throw new RuntimeException('Redirect registry contract or expected_redirects is invalid.');
        }

        $sourcePaths = [];
        foreach ($manifest['redirects'] as $index => $row) {
            if (! is_array($row)) {
                throw new RuntimeException("Redirect row {$index} must be an object.");
            }
            $source = $this->safePath($row['source_path'] ?? null, "row {$index} source_path");
            if (isset($sourcePaths[$source])) {
                throw new RuntimeException("Redirect registry repeats source path {$source}.");
            }
            $sourcePaths[$source] = true;
        }

        foreach ($manifest['redirects'] as $index => $row) {
            $source = $this->safePath($row['source_path'] ?? null, "row {$index} source_path");
            $target = $this->safePath($row['target_path'] ?? null, "row {$index} target_path");
            if ($source === $target) {
                throw new RuntimeException("Redirect {$source} points to itself.");
            }
            if (isset($sourcePaths[$target])) {
                throw new RuntimeException("Redirect registry would create a chain through {$target}.");
            }
        }

        return array_values($manifest['redirects']);
    }

    /** @return array{source_path: string, target_path: string, existing: bool} */
    private function validateRow(Site $site, array $row, int $index): array
    {
        $source = $this->safePath($row['source_path'] ?? null, "row {$index} source_path");
        $target = $this->safePath($row['target_path'] ?? null, "row {$index} target_path");
        $externalId = is_string($row['target_external_id'] ?? null) ? trim($row['target_external_id']) : '';
        $evidence = is_string($row['evidence'] ?? null) ? trim($row['evidence']) : '';
        if ($externalId === '' || $evidence === '') {
            throw new RuntimeException("Redirect row {$index} requires target_external_id and evidence.");
        }

        if (SiteUrl::query()->where('site_id', $site->id)->where('path', $source)->exists()) {
            throw new RuntimeException("Redirect source {$source} is still an active site URL.");
        }

        $existing = SiteRedirect::query()
            ->where('site_id', $site->id)
            ->where('source_path', $source)
            ->first();
        if ($existing !== null && (
            $existing->target_path !== $target
            || (int) $existing->status_code !== 301
            || $existing->purpose !== SiteRedirect::PURPOSE_PREVIEW
            || ! $existing->is_active
        )) {
            throw new RuntimeException("Redirect source {$source} conflicts with the reviewed registry.");
        }

        if (SiteRedirect::query()->where('site_id', $site->id)->where('source_path', $target)->where('is_active', true)->exists()) {
            throw new RuntimeException("Redirect target {$target} is itself an active redirect source.");
        }

        $targetUrls = SiteUrl::query()
            ->where('site_id', $site->id)
            ->where('path', $target)
            ->get();
        if ($targetUrls->count() !== 1) {
            throw new RuntimeException("Redirect target {$target} must resolve to exactly one site URL.");
        }

        $targetUrl = $targetUrls->first();
        if ($targetUrl->target_type !== 'product' || $targetUrl->is_indexable) {
            throw new RuntimeException("Redirect target {$target} must be a noindex product URL.");
        }

        $siteProduct = SiteProduct::query()
            ->whereKey($targetUrl->target_id)
            ->where('site_id', $site->id)
            ->where('is_published', true)
            ->first();
        if ($siteProduct === null) {
            throw new RuntimeException("Redirect target {$target} has no published site product.");
        }

        $product = Product::query()->find($siteProduct->product_id);
        if ($product === null || $product->external_id !== $externalId) {
            throw new RuntimeException("Redirect target {$target} external identity does not match {$externalId}.");
        }

        $seoRows = SiteSeo::query()
            ->where('site_id', $site->id)
            ->where('resource_type', 'product')
            ->where('resource_id', $siteProduct->id)
            ->get();
        if ($seoRows->isEmpty()
            || ! $seoRows->contains(fn (SiteSeo $seo): bool => $seo->locale === $site->default_locale && $seo->canonical_path === $target)
            || $seoRows->contains(fn (SiteSeo $seo): bool => $seo->is_indexable || $seo->schema !== null)) {
            throw new RuntimeException("Redirect target {$target} must have only noindex SEO without schema and an exact canonical path.");
        }

        return [
            'source_path' => $source,
            'target_path' => $target,
            'existing' => $existing !== null,
        ];
    }

    private function safePath(mixed $value, string $field): string
    {
        if (! is_string($value)
            || $value === ''
            || $value === '/'
            || ! str_starts_with($value, '/')
            || str_starts_with($value, '//')
            || str_contains($value, '?')
            || str_contains($value, '#')
            || str_contains($value, '\\')
            || preg_match('/[\x00-\x1F\x7F]/', $value) === 1) {
            throw new RuntimeException("Unsafe {$field}.");
        }

        return $value;
    }
}
