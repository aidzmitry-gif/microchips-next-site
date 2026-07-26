<?php

namespace App\Domain\Imports;

use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/**
 * Imports launch-page drafts without creating a route which can be served or
 * indexed.  This is deliberately a separate importer from normal pages: a
 * launch brief is useful to review in Filament, but it is not permission to
 * publish regional legal or commercial claims.
 */
final class SiteLaunchPageDraftImporter
{
    /** @return array<string, mixed> */
    public function import(Site $site, string $file, bool $apply): array
    {
        $drafts = $this->read($file, $site);
        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'site_key' => $site->key,
            'drafts' => count($drafts),
            'created' => 0,
            'updated' => 0,
            'unchanged' => 0,
            'publication_status' => 'all_pages_unpublished_all_urls_noindex',
        ];

        DB::beginTransaction();
        try {
            foreach ($drafts as $draft) {
                $page = SitePage::query()
                    ->where('site_id', $site->id)
                    ->where('locale', $draft['locale'])
                    ->where('slug', $draft['slug'])
                    ->first();

                if ($page !== null && $page->is_published) {
                    throw new RuntimeException("Refusing to overwrite published page draft: {$draft['slug']}.");
                }

                if ($page === null) {
                    $page = SitePage::create([
                        'site_id' => $site->id,
                        ...$this->pageValues($draft),
                        'is_published' => false,
                    ]);
                    $summary['created']++;
                } else {
                    $page->fill([...$this->pageValues($draft), 'is_published' => false]);
                    if ($page->isDirty()) {
                        $page->save();
                        $summary['updated']++;
                    } else {
                        $summary['unchanged']++;
                    }
                }

                $this->upsertNoindexUrl($site, $page, $draft);
                $this->upsertNoindexSeo($site, $page, $draft);
            }

            if ($apply) {
                DB::commit();
            } else {
                DB::rollBack();
            }
        } catch (Throwable $error) {
            if (DB::transactionLevel() > 0) {
                DB::rollBack();
            }

            throw $error;
        }

        return $summary;
    }

    /** @return list<array{locale:string,slug:string,path:string,title:string,h1:string,content:string,description:string}> */
    private function read(string $file, Site $site): array
    {
        if (! is_file($file)) {
            throw new RuntimeException('Draft manifest was not found.');
        }
        $raw = file_get_contents($file);
        if ($raw === false) {
            throw new RuntimeException('Unable to read draft manifest.');
        }
        try {
            $manifest = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException) {
            throw new RuntimeException('Draft manifest is not valid JSON.');
        }
        if (! is_array($manifest) || ($manifest['schema_version'] ?? null) !== 1 || ! is_array($manifest['pages'] ?? null)) {
            throw new RuntimeException('Draft manifest must contain schema_version 1 and pages.');
        }

        $drafts = [];
        $seenSlugs = [];
        foreach ($manifest['pages'] as $index => $draft) {
            if (! is_array($draft)) {
                throw new RuntimeException("Draft #{$index} must be an object.");
            }
            foreach (['locale', 'slug', 'path', 'title', 'h1', 'content', 'description'] as $field) {
                if (! is_string($draft[$field] ?? null) || trim($draft[$field]) === '') {
                    throw new RuntimeException("Draft #{$index} has invalid {$field}.");
                }
            }
            if (($draft['is_published'] ?? null) !== false || ($draft['is_indexable'] ?? null) !== false) {
                throw new RuntimeException("Draft #{$index} must explicitly be unpublished and noindex.");
            }
            if ($draft['locale'] !== $site->default_locale) {
                throw new RuntimeException("Draft #{$index} locale is not enabled as the site's default locale.");
            }
            if (! preg_match('/^[a-z0-9-]{1,120}$/', $draft['slug'])
                || ! preg_match('#^/[a-z0-9/-]{1,240}$#', $draft['path'])
                || str_ends_with($draft['path'], '/')) {
                throw new RuntimeException("Draft #{$index} has an unsafe slug or path.");
            }
            if (isset($seenSlugs[$draft['slug']])) {
                throw new RuntimeException("Draft #{$index} has a duplicate slug.");
            }
            $seenSlugs[$draft['slug']] = true;
            $drafts[] = array_map(static fn (mixed $value): string => trim((string) $value), $draft);
        }

        if ($drafts === []) {
            throw new RuntimeException('Draft manifest contains no pages.');
        }

        return $drafts;
    }

    /** @param array{locale:string,slug:string,path:string,title:string,h1:string,content:string,description:string} $draft
     * @return array<string, string> */
    private function pageValues(array $draft): array
    {
        return array_intersect_key($draft, array_flip(['locale', 'slug', 'title', 'h1', 'content']));
    }

    /** @param array{locale:string,path:string} $draft */
    private function upsertNoindexUrl(Site $site, SitePage $page, array $draft): void
    {
        $url = SiteUrl::query()->where('site_id', $site->id)->where('path', $draft['path'])->first();
        if ($url !== null && ($url->target_type !== 'page' || $url->target_id !== $page->id || $url->is_indexable)) {
            throw new RuntimeException("Refusing to overwrite existing public or foreign route: {$draft['path']}.");
        }
        SiteUrl::updateOrCreate(
            ['site_id' => $site->id, 'path' => $draft['path']],
            ['locale' => $draft['locale'], 'target_type' => 'page', 'target_id' => $page->id, 'is_indexable' => false],
        );
    }

    /** @param array{locale:string,path:string,title:string,description:string} $draft */
    private function upsertNoindexSeo(Site $site, SitePage $page, array $draft): void
    {
        SiteSeo::updateOrCreate(
            ['site_id' => $site->id, 'locale' => $draft['locale'], 'resource_type' => 'page', 'resource_id' => $page->id],
            ['canonical_path' => $draft['path'], 'title' => $draft['title'], 'description' => $draft['description'], 'is_indexable' => false, 'schema' => null],
        );
    }
}
