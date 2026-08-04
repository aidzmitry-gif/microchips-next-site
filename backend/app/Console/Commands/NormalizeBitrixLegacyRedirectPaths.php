<?php

namespace App\Console\Commands;

use App\Events\SiteContentChanged;
use App\Models\Site;
use App\Models\SiteRedirect;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class NormalizeBitrixLegacyRedirectPaths extends Command
{
    protected $signature = 'catalog:normalize-bitrix-legacy-redirect-paths
                            {site : Site key}
                            {--expected-redirects=16894 : Exact number of active original Bitrix redirects}
                            {--apply : Persist the normalized source paths; default is a dry-run}';

    protected $description = 'Remove the single trailing slash from guarded original Bitrix redirect source paths';

    public function handle(): int
    {
        try {
            $site = Site::query()->where('key', trim((string) $this->argument('site')))->sole();
            $this->assertExactSite($site);
            $expected = $this->expectedRedirects();
            $apply = (bool) $this->option('apply');

            $plan = $this->buildPlan($site, $expected, false);
            $normalized = 0;

            if ($apply && $plan['pending']->isNotEmpty()) {
                DB::transaction(function () use ($site, $expected, &$plan, &$normalized): void {
                    if (DB::getDriverName() === 'pgsql') {
                        DB::select('select pg_advisory_xact_lock(hashtext(?))', [
                            'normalize-bitrix-legacy-redirect-paths:'.$site->key,
                        ]);
                    }

                    $plan = $this->buildPlan($site, $expected, true);
                    $plan['pending']->pluck('id')->chunk(500)->each(function (Collection $ids): void {
                        DB::table('site_redirects')
                            ->whereIn('id', $ids->all())
                            ->update([
                                'source_path' => DB::raw('substr(source_path, 1, length(source_path) - 1)'),
                                'updated_at' => now(),
                            ]);
                    });
                    $normalized = $plan['pending']->count();

                    SiteContentChanged::dispatch($site, ['/catalog', '/sitemap.xml']);
                });
            }

            $this->line(json_encode([
                'mode' => $apply ? 'apply' : 'dry_run',
                'site' => $site->key,
                'expected_redirects' => $expected,
                'selected_redirects' => $plan['selected_count'],
                'pending_before' => $plan['pending']->count(),
                'normalized' => $normalized,
                'unchanged' => $plan['unchanged_count'],
                'remaining_after' => $plan['pending']->count() - $normalized,
            ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    private function assertExactSite(Site $site): void
    {
        if ($site->key !== 'microchips-by' || $site->domain !== 'microchips.by') {
            throw new RuntimeException('This normalization requires the exact microchips-by site on microchips.by.');
        }
    }

    private function expectedRedirects(): int
    {
        $value = trim((string) $this->option('expected-redirects'));
        if (! ctype_digit($value) || (int) $value < 1) {
            throw new RuntimeException('Expected redirects must be a positive integer.');
        }

        return (int) $value;
    }

    /**
     * @return array{
     *     selected_count:int,
     *     pending:Collection<int,SiteRedirect>,
     *     unchanged_count:int
     * }
     */
    private function buildPlan(Site $site, int $expected, bool $lock): array
    {
        $redirectQuery = SiteRedirect::query()
            ->where('site_id', $site->id)
            ->orderBy('id');
        if ($lock) {
            $redirectQuery->lockForUpdate();
        }

        $allRedirects = $redirectQuery->get();
        $selected = $allRedirects
            ->filter(fn (SiteRedirect $redirect): bool => $redirect->is_active
                && preg_match('~^/catalog/(?:[^/?#]+/)+[0-9]+/?$~D', $redirect->source_path) === 1)
            ->values();

        if ($selected->count() !== $expected) {
            throw new RuntimeException("Expected exactly {$expected} active original Bitrix redirects; found {$selected->count()}.");
        }

        $siteUrlPaths = SiteUrl::query()
            ->where('site_id', $site->id)
            ->pluck('path')
            ->flip();
        $redirectsBySource = $allRedirects->groupBy('source_path');
        $normalizedOwners = [];
        $pending = collect();
        $unchanged = 0;

        foreach ($selected as $redirect) {
            $sourcePath = $redirect->source_path;
            $this->assertSafeLocalPath($sourcePath, 'source path', true);
            $this->assertSafeLocalPath($redirect->target_path, "target path for {$sourcePath}", false);

            if ((int) $redirect->status_code !== 301
                || ! in_array($redirect->purpose, [SiteRedirect::PURPOSE_PREVIEW, SiteRedirect::PURPOSE_SEO], true)) {
                throw new RuntimeException("Bitrix redirect {$sourcePath} must be active 301 with preview or seo purpose.");
            }

            $hasTrailingSlash = str_ends_with($sourcePath, '/');
            $normalizedPath = $hasTrailingSlash ? substr($sourcePath, 0, -1) : $sourcePath;
            if ($normalizedPath === '' || $normalizedPath === $redirect->target_path) {
                throw new RuntimeException("Bitrix redirect {$sourcePath} would become an empty or self redirect.");
            }
            if (isset($normalizedOwners[$normalizedPath])) {
                throw new RuntimeException("Multiple Bitrix redirects normalize to {$normalizedPath}.");
            }
            $normalizedOwners[$normalizedPath] = $redirect->id;

            if ($siteUrlPaths->has($normalizedPath)) {
                throw new RuntimeException("Normalized source {$normalizedPath} conflicts with an active site URL.");
            }

            $sourceConflicts = $redirectsBySource->get($normalizedPath, collect())
                ->reject(fn (SiteRedirect $other): bool => $other->id === $redirect->id);
            if ($sourceConflicts->isNotEmpty()) {
                throw new RuntimeException("Normalized source {$normalizedPath} conflicts with another redirect source.");
            }

            if ($hasTrailingSlash) {
                $pending->push($redirect);
            } else {
                $unchanged++;
            }
        }

        return [
            'selected_count' => $selected->count(),
            'pending' => $pending,
            'unchanged_count' => $unchanged,
        ];
    }

    private function assertSafeLocalPath(string $path, string $label, bool $allowSingleTrailingSlash): void
    {
        $parts = parse_url($path);
        $pathPart = is_array($parts) ? ($parts['path'] ?? null) : null;
        $unsafe = ! is_string($pathPart)
            || $path === ''
            || ! str_starts_with($path, '/')
            || $pathPart !== $path
            || str_contains($path, '\\')
            || str_contains($path, '//')
            || preg_match('/[\x00-\x1F\x7F]/', $path) === 1
            || preg_match('#/(?:\.|\.\.)(?:/|$)#', $path) === 1;

        if ($unsafe) {
            throw new RuntimeException("Unsafe local {$label}: {$path}.");
        }
        if ($allowSingleTrailingSlash) {
            if (str_ends_with($path, '//')) {
                throw new RuntimeException("Unsafe local {$label}: {$path}.");
            }

            return;
        }
        if ($path !== '/' && str_ends_with($path, '/')) {
            throw new RuntimeException("Local {$label} is not normalized: {$path}.");
        }
    }
}
