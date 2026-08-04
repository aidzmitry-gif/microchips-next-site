<?php

namespace App\Console\Commands;

use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/** Imports market-specific category introductions without changing indexability. */
class ImportSiteCategoryContent extends Command
{
    protected $signature = 'content:import-site-category-content
                            {site : Site key}
                            {file : JSON reviewed category-content manifest}
                            {--apply : Persist reviewed title and description; default is dry-run}';

    protected $description = 'Import reviewed local category titles and introductions while keeping preview URLs noindex';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $summary = $this->import($site, (string) $this->argument('file'), (bool) $this->option('apply'));
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /** @return array{mode: string, records: int, updated: int, unchanged: int, indexability_changes: int} */
    private function import(Site $site, string $file, bool $apply): array
    {
        if (! is_readable($file)) {
            throw new RuntimeException('Category content manifest is not readable.');
        }

        $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest)
            || ($manifest['locale'] ?? null) !== $site->default_locale
            || ! is_array($manifest['categories'] ?? null)
            || $manifest['categories'] === []) {
            throw new RuntimeException('Manifest must match the site locale and contain categories.');
        }

        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'records' => count($manifest['categories']),
            'updated' => 0,
            'unchanged' => 0,
            'indexability_changes' => 0,
        ];
        $seen = [];

        $work = function () use ($site, $manifest, &$summary, &$seen): void {
            foreach ($manifest['categories'] as $index => $row) {
                if (! is_array($row)) {
                    throw new RuntimeException("Category row {$index} must be an object.");
                }
                foreach (['external_id', 'title', 'description'] as $field) {
                    if (! is_string($row[$field] ?? null) || blank(trim($row[$field]))) {
                        throw new RuntimeException("Category row {$index} requires {$field}.");
                    }
                }

                $externalId = trim($row['external_id']);
                if (isset($seen[$externalId])) {
                    throw new RuntimeException("Manifest repeats category {$externalId}.");
                }
                $seen[$externalId] = true;

                $title = trim($row['title']);
                $description = trim($row['description']);
                if (mb_strlen($title) < 15 || mb_strlen($title) > 120) {
                    throw new RuntimeException("Category {$externalId} title must contain 15 to 120 characters.");
                }
                if (mb_strlen($description) < 100 || mb_strlen($description) > 1200) {
                    throw new RuntimeException("Category {$externalId} description must contain 100 to 1200 characters.");
                }

                $category = SiteCategory::query()
                    ->where('site_id', $site->id)
                    ->where('external_id', $externalId)
                    ->where('is_published', true)
                    ->first();
                if ($category === null) {
                    throw new RuntimeException("Published category {$externalId} was not found for {$site->key}.");
                }

                $url = SiteUrl::query()
                    ->where('site_id', $site->id)
                    ->where('locale', $site->default_locale)
                    ->where('target_type', 'category')
                    ->where('target_id', $category->id)
                    ->first();
                $seo = SiteSeo::query()
                    ->where('site_id', $site->id)
                    ->where('locale', $site->default_locale)
                    ->where('resource_type', 'category')
                    ->where('resource_id', $category->id)
                    ->first();
                if ($url === null || $seo === null || $url->is_indexable || $seo->is_indexable) {
                    throw new RuntimeException("Category {$externalId} must have an existing noindex URL and SEO record.");
                }
                if ($seo->canonical_path !== $url->path) {
                    throw new RuntimeException("Category {$externalId} canonical path does not match its URL.");
                }

                if ($seo->title === $title && $seo->description === $description) {
                    $summary['unchanged']++;

                    continue;
                }

                $seo->update(['title' => $title, 'description' => $description]);
                $summary['updated']++;
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
}
