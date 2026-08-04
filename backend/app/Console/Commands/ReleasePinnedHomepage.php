<?php

namespace App\Console\Commands;

use App\Domain\Seo\SiteIndexabilityPublisher;
use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Events\SiteContentChanged;
use App\Models\ImportRun;
use App\Models\Site;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use App\Models\SitePage;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/**
 * Replace the pinned RB demo root with owner-approved content and release it.
 *
 * This command deliberately owns neither products nor the commercial profile.
 * It only verifies those site facts, updates the existing root page/SEO pair,
 * and delegates the noindex -> indexable transition to the shared publisher.
 */
class ReleasePinnedHomepage extends Command
{
    private const RELEASE_SCHEMA = 'rb_homepage_release_v1';

    private const ROLLBACK_SCHEMA = 'rb_homepage_rollback_v1';

    private const SITE_KEY = 'microchips-by';

    private const DOMAIN = 'microchips.by';

    private const LOCALE = 'ru-BY';

    private const OWNER_APPROVAL = [
        'approved_at' => '2026-07-26',
        'approval_basis' => 'Owner-confirmed RB commercial profile pinned in docs/imports/rb-commercial-profile-drafts.json',
        'legal_name' => 'ООО «Аккумуляторные решения»',
        'unp' => '192766048',
        'legal_address' => '220035, г. Минск, ул. Тимирязева, 65А, пом. 407',
        'pickup_address' => 'г. Минск, ул. Тимирязева, 65А, офис 408; только по предварительному согласованию',
        'phones' => ['+375 (33) 347-75-10', '+375 (17) 396-23-02'],
        'email' => 'order@microchips.by',
        'working_hours' => 'пн–пт 9:00–17:00',
        'b2b_focus' => [
            'промышленные аккумуляторы',
            'батареи для ИБП',
            'решения резервного питания',
        ],
    ];

    protected $signature = 'seo:release-homepage
                            {site : Must be microchips-by}
                            {file : Hash-pinned RB homepage release or rollback manifest}
                            {--apply : Persist; the default executes the complete path then rolls it back}
                            {--rollback : Restore the exact pre-release root state}
                            {--rollback-output= : Rollback manifest path; defaults beside the release manifest}';

    protected $description = 'Atomically replace and release the owner-approved RB homepage through the shared SEO publisher';

    public function handle(SiteIndexabilityPublisher $publisher, SiteSeoReleaseAuditor $auditor): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        $apply = (bool) $this->option('apply');
        $rollback = (bool) $this->option('rollback');
        $file = (string) $this->argument('file');
        if ($rollback && filled($this->option('rollback-output'))) {
            $this->error('--rollback-output cannot be used with --rollback.');

            return self::FAILURE;
        }

        try {
            $manifest = $this->readManifest($file);
            DB::beginTransaction();
            try {
                $summary = $rollback
                    ? $this->rollback($site, $manifest, $apply, $auditor, $file)
                    : $this->release($site, $manifest, $apply, $publisher, $file);
                $apply ? DB::commit() : DB::rollBack();
            } catch (Throwable $error) {
                if (DB::transactionLevel() > 0) {
                    DB::rollBack();
                }
                throw $error;
            }
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line((string) json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

        return self::SUCCESS;
    }

    /** @param array<string, mixed> $manifest
     * @return array<string, mixed>
     */
    private function release(Site $site, array $manifest, bool $apply, SiteIndexabilityPublisher $publisher, string $file): array
    {
        $this->validateReleaseEnvelope($site, $manifest);
        [$url, $page, $seo] = $this->lockedRoot($site);
        $before = $this->rootState($url, $page, $seo);
        $this->assertHash($before, $manifest['expected_before_sha256'], 'Root before-state');
        $this->assertNoindexPublishedRoot($site, $url, $page, $seo);
        $this->assertApprovedProfile($site, $manifest['owner_approval']);
        $this->assertHomepageContent($manifest['homepage'], $manifest['owner_approval']);

        /** @var array<string, mixed> $homepage */
        $homepage = $manifest['homepage'];
        $page->forceFill([
            'title' => $homepage['title'],
            'h1' => $homepage['h1'],
            'content' => $homepage['content'],
        ])->saveQuietly();
        $url->forceFill(['is_indexable' => false])->saveQuietly();
        $seo->forceFill([
            'canonical_path' => '/',
            'title' => $homepage['seo_title'],
            'description' => $homepage['seo_description'],
            'schema' => $homepage['schema'],
            'is_indexable' => false,
        ])->saveQuietly();

        if ($url->fresh()->is_indexable || $seo->fresh()->is_indexable) {
            throw new RuntimeException('The root must remain noindex until the shared publisher runs.');
        }

        $publisher->promote($url->fresh());
        // SiteIndexabilityPublisher::promote() intentionally returns void;
        // read the same auditor result through its transactional gate summary.
        $releasedUrl = $url->fresh();
        $releasedPage = $page->fresh();
        $releasedSeo = $seo->fresh();
        if (! $releasedUrl->is_indexable || ! $releasedSeo->is_indexable) {
            throw new RuntimeException('The shared publisher did not release both root records.');
        }

        $releasedState = $this->rootState($releasedUrl, $releasedPage, $releasedSeo);
        $rollbackPath = null;
        if ($apply) {
            $rollbackPath = $this->rollbackOutputPath($file);
            $rollbackManifest = [
                'schema' => self::ROLLBACK_SCHEMA,
                'site_key' => $site->key,
                'domain' => $site->domain,
                'locale' => $site->default_locale,
                'path' => '/',
                'release_manifest_sha256' => strtolower((string) hash_file('sha256', $file)),
                'released_state_sha256' => $this->hashState($releasedState),
                'restore_state_sha256' => $this->hashState($before),
                'restore' => $before,
            ];
            $this->writeJsonAtomically($rollbackPath, $rollbackManifest);
        }

        $seoReport = app(SiteSeoReleaseAuditor::class)->audit($site);
        if (! $seoReport['passed']) {
            throw new RuntimeException('Released homepage did not retain a passing SEO audit.');
        }

        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'operation' => 'release_homepage',
            'site' => $site->key,
            'path' => '/',
            'indexable' => true,
            'seo_audit_summary' => $seoReport['summary'],
            'before_state_sha256' => $this->hashState($before),
            'released_state_sha256' => $this->hashState($releasedState),
            'rollback_manifest' => $rollbackPath,
        ];
        if ($apply) {
            $this->recordAudit($site, $file, $manifest, $summary, 'released_indexable');
        }

        return $summary;
    }

    /** @param array<string, mixed> $manifest
     * @return array<string, mixed>
     */
    private function rollback(Site $site, array $manifest, bool $apply, SiteSeoReleaseAuditor $auditor, string $file): array
    {
        $this->validateRollbackEnvelope($site, $manifest);
        [$url, $page, $seo] = $this->lockedRoot($site);
        $this->assertHash($this->rootState($url, $page, $seo), $manifest['released_state_sha256'], 'Released root state');
        if (! $url->is_indexable || ! $seo->is_indexable) {
            throw new RuntimeException('Rollback requires the currently released indexable root.');
        }
        if (SiteUrl::query()->where('site_id', $site->id)->where('is_indexable', true)->whereKeyNot($url->id)->exists()) {
            throw new RuntimeException('Homepage rollback is blocked while another site URL is indexable; robots.txt would hide it.');
        }

        /** @var array<string, mixed> $restore */
        $restore = $manifest['restore'];
        $this->assertRestoreIdentity($url, $page, $seo, $restore);
        $url->forceFill(['is_indexable' => false])->saveQuietly();
        $page->forceFill([
            'locale' => $restore['page']['locale'],
            'slug' => $restore['page']['slug'],
            'title' => $restore['page']['title'],
            'h1' => $restore['page']['h1'],
            'content' => $restore['page']['content'],
            'is_published' => $restore['page']['is_published'],
        ])->saveQuietly();
        $seo->forceFill([
            'locale' => $restore['seo']['locale'],
            'resource_type' => $restore['seo']['resource_type'],
            'resource_id' => $restore['seo']['resource_id'],
            'canonical_path' => $restore['seo']['canonical_path'],
            'title' => $restore['seo']['title'],
            'description' => $restore['seo']['description'],
            'is_indexable' => false,
            'schema' => $restore['seo']['schema'],
        ])->saveQuietly();

        $report = $auditor->audit($site);
        if (! $report['passed']) {
            $codes = implode(', ', array_unique(array_column($report['issues'], 'code')));
            throw new RuntimeException("Homepage rollback leaves the SEO audit failing: {$codes}");
        }
        SiteContentChanged::dispatch($site, ['/', '/sitemap.xml']);

        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'operation' => 'rollback_homepage',
            'site' => $site->key,
            'path' => '/',
            'indexable' => false,
            'seo_audit_summary' => $report['summary'],
            'restored_state_sha256' => $this->hashState($this->rootState($url->fresh(), $page->fresh(), $seo->fresh())),
        ];
        if ($apply) {
            $this->recordAudit($site, $file, $manifest, $summary, 'restored_noindex');
        }

        return $summary;
    }

    /** @param array<string, mixed> $manifest */
    private function validateReleaseEnvelope(Site $site, array $manifest): void
    {
        $this->assertExactKeys($manifest, [
            'schema', 'site_key', 'domain', 'locale', 'path', 'expected_before_sha256', 'owner_approval', 'homepage',
        ], 'Release manifest');
        if ($manifest['schema'] !== self::RELEASE_SCHEMA || $manifest['site_key'] !== self::SITE_KEY
            || $manifest['domain'] !== self::DOMAIN || $manifest['locale'] !== self::LOCALE || $manifest['path'] !== '/') {
            throw new RuntimeException('Release manifest is not the pinned RB production homepage package.');
        }
        $this->assertSite($site);
        if (! is_array($manifest['owner_approval']) || ! is_array($manifest['homepage'])) {
            throw new RuntimeException('Release manifest requires owner_approval and homepage objects.');
        }
    }

    /** @param array<string, mixed> $manifest */
    private function validateRollbackEnvelope(Site $site, array $manifest): void
    {
        $this->assertExactKeys($manifest, [
            'schema', 'site_key', 'domain', 'locale', 'path', 'release_manifest_sha256', 'released_state_sha256',
            'restore_state_sha256', 'restore',
        ], 'Rollback manifest');
        if ($manifest['schema'] !== self::ROLLBACK_SCHEMA || $manifest['site_key'] !== self::SITE_KEY
            || $manifest['domain'] !== self::DOMAIN || $manifest['locale'] !== self::LOCALE || $manifest['path'] !== '/') {
            throw new RuntimeException('Rollback manifest is not the pinned RB production homepage package.');
        }
        $this->assertSite($site);
        if (! is_array($manifest['restore'])) {
            throw new RuntimeException('Rollback manifest requires an exact restore object.');
        }
        $this->assertSha256($manifest['release_manifest_sha256'], 'release_manifest_sha256');
        $this->assertSha256($manifest['released_state_sha256'], 'released_state_sha256');
        $this->assertHash($manifest['restore'], $manifest['restore_state_sha256'], 'Rollback restore-state');
    }

    private function assertSite(Site $site): void
    {
        $localeEnabled = $site->locales()->where('locale', self::LOCALE)->where('is_enabled', true)->exists();
        if ($site->key !== self::SITE_KEY || $site->domain !== self::DOMAIN || $site->default_locale !== self::LOCALE
            || $site->currency_code !== 'BYN' || ! $site->is_active || ! $localeEnabled) {
            throw new RuntimeException('Site must be the active microchips.by RB profile with enabled ru-BY and BYN.');
        }
    }

    /** @return array{SiteUrl, SitePage, SiteSeo} */
    private function lockedRoot(Site $site): array
    {
        $url = SiteUrl::query()->where('site_id', $site->id)->where('path', '/')->lockForUpdate()->first();
        $page = $url === null ? null : SitePage::query()->where('site_id', $site->id)->lockForUpdate()->find($url->target_id);
        $seo = $url === null ? null : SiteSeo::query()
            ->where('site_id', $site->id)->where('locale', self::LOCALE)
            ->where('resource_type', 'page')->where('resource_id', $url->target_id)
            ->lockForUpdate()->first();
        if ($url === null || $page === null || $seo === null) {
            throw new RuntimeException('The existing root URL, published page, and matching SEO record are required.');
        }

        return [$url, $page, $seo];
    }

    private function assertNoindexPublishedRoot(Site $site, SiteUrl $url, SitePage $page, SiteSeo $seo): void
    {
        if ($url->site_id !== $site->id || $url->path !== '/' || $url->locale !== self::LOCALE
            || $url->target_type !== 'page' || $url->target_id !== $page->id || $url->is_indexable
            || $page->site_id !== $site->id || $page->locale !== self::LOCALE || $page->slug !== 'home' || ! $page->is_published
            || $seo->site_id !== $site->id || $seo->locale !== self::LOCALE || $seo->resource_type !== 'page'
            || $seo->resource_id !== $page->id || $seo->canonical_path !== '/' || $seo->is_indexable) {
            throw new RuntimeException('Root must be the existing published, self-canonical ru-BY noindex page/SEO pair.');
        }
        if (SiteUrl::query()->where('site_id', $site->id)->where('is_indexable', true)->exists()) {
            throw new RuntimeException('Homepage must be the first indexable URL for this site.');
        }
    }

    /** @param array<string, mixed> $approval */
    private function assertApprovedProfile(Site $site, array $approval): void
    {
        if ($this->canonicalize($approval) !== $this->canonicalize(self::OWNER_APPROVAL)) {
            throw new RuntimeException('Owner-approved RB facts do not match the command pin.');
        }

        $expectedContacts = [
            ['legal_entity', 'Юридическое лицо', self::OWNER_APPROVAL['legal_name'].', УНП '.self::OWNER_APPROVAL['unp']],
            ['address', 'Юридический адрес', self::OWNER_APPROVAL['legal_address']],
            ['address', 'Самовывоз', self::OWNER_APPROVAL['pickup_address']],
            ['phone', 'Основной телефон', self::OWNER_APPROVAL['phones'][0]],
            ['phone', 'Городской телефон', self::OWNER_APPROVAL['phones'][1]],
            ['email', 'E-mail', self::OWNER_APPROVAL['email']],
            ['working_hours', 'Режим работы', self::OWNER_APPROVAL['working_hours']],
        ];
        foreach ($expectedContacts as [$type, $label, $value]) {
            $exists = SiteContact::query()->where('site_id', $site->id)->where('locale', self::LOCALE)
                ->where('type', $type)->where('label', $label)->where('value', $value)
                ->published()->whereNotNull('verified_at')->whereNotNull('verified_by')->whereNotNull('verification_note')->exists();
            if (! $exists) {
                throw new RuntimeException("Verified owner-approved contact is missing: {$label}.");
            }
        }

        foreach ([
            'legal_name' => self::OWNER_APPROVAL['legal_name'].', УНП '.self::OWNER_APPROVAL['unp'],
            'legal_address' => self::OWNER_APPROVAL['legal_address'],
        ] as $key => $value) {
            $exists = SiteCommercialFact::query()->where('site_id', $site->id)->where('locale', self::LOCALE)
                ->where('key', $key)->where('value', $value)->published()
                ->whereNotNull('verified_at')->whereNotNull('verified_by')->whereNotNull('verification_note')->exists();
            if (! $exists) {
                throw new RuntimeException("Verified owner-approved commercial fact is missing: {$key}.");
            }
        }
    }

    /** @param array<string, mixed> $homepage
     * @param  array<string, mixed>  $approval
     */
    private function assertHomepageContent(array $homepage, array $approval): void
    {
        $this->assertExactKeys($homepage, ['title', 'h1', 'content', 'seo_title', 'seo_description', 'schema'], 'Homepage');
        foreach (['title', 'h1', 'content', 'seo_title', 'seo_description'] as $field) {
            if (! is_string($homepage[$field]) || trim($homepage[$field]) === '') {
                throw new RuntimeException("Homepage requires non-empty {$field}.");
            }
        }
        $visible = implode(' ', array_intersect_key($homepage, array_flip(['title', 'h1', 'content', 'seo_title', 'seo_description'])));
        if (preg_match('/\b(?:demo|placeholder)\b|демо|прототип|черновик|миграц|тестов(?:ый|ая|ое|ые)?\s+контент|заполнител/ui', $visible) === 1) {
            throw new RuntimeException('Homepage release content contains a demo, placeholder, draft, or migration marker.');
        }
        if (mb_strlen(trim($homepage['content'])) < 300 || mb_strlen(trim($homepage['seo_description'])) < 100) {
            throw new RuntimeException('Homepage content or SEO description is too thin for release.');
        }
        $required = [
            $approval['legal_name'], $approval['unp'], $approval['legal_address'], $approval['pickup_address'],
            ...$approval['phones'], $approval['email'], $approval['working_hours'], 'B2B', ...$approval['b2b_focus'],
        ];
        foreach ($required as $fact) {
            if (! is_string($fact) || ! str_contains($homepage['content'], $fact)) {
                throw new RuntimeException("Homepage content omits owner-approved fact: {$fact}");
            }
        }
        if (! is_array($homepage['schema']) || ($homepage['schema']['@type'] ?? null) !== 'Organization'
            || ($homepage['schema']['name'] ?? null) !== $approval['legal_name']
            || ($homepage['schema']['taxID'] ?? null) !== $approval['unp']
            || ($homepage['schema']['url'] ?? null) !== 'https://'.self::DOMAIN.'/') {
            throw new RuntimeException('Homepage schema must be the pinned production Organization identity.');
        }
        if (str_contains((string) json_encode($homepage['schema']), 'Offer')) {
            throw new RuntimeException('Homepage release must not infer an Offer.');
        }
    }

    /** @param array<string, mixed> $restore */
    private function assertRestoreIdentity(SiteUrl $url, SitePage $page, SiteSeo $seo, array $restore): void
    {
        $this->assertExactKeys($restore, ['url', 'page', 'seo'], 'Rollback restore');
        if (! is_array($restore['url']) || ! is_array($restore['page']) || ! is_array($restore['seo'])
            || ($restore['url']['id'] ?? null) !== $url->id || ($restore['url']['site_id'] ?? null) !== $url->site_id
            || ($restore['url']['path'] ?? null) !== '/' || ($restore['url']['target_id'] ?? null) !== $page->id
            || ($restore['url']['is_indexable'] ?? null) !== false
            || ($restore['page']['id'] ?? null) !== $page->id || ($restore['page']['site_id'] ?? null) !== $page->site_id
            || ($restore['page']['is_published'] ?? null) !== true
            || ($restore['seo']['id'] ?? null) !== $seo->id || ($restore['seo']['site_id'] ?? null) !== $seo->site_id
            || ($restore['seo']['resource_id'] ?? null) !== $page->id || ($restore['seo']['is_indexable'] ?? null) !== false) {
            throw new RuntimeException('Rollback restore state does not identify the exact original root records.');
        }
    }

    /** @return array<string, mixed> */
    private function rootState(SiteUrl $url, SitePage $page, SiteSeo $seo): array
    {
        return [
            'url' => $url->only(['id', 'site_id', 'path', 'locale', 'target_type', 'target_id', 'is_indexable']),
            'page' => $page->only(['id', 'site_id', 'locale', 'slug', 'title', 'h1', 'content', 'is_published']),
            'seo' => $seo->only(['id', 'site_id', 'locale', 'resource_type', 'resource_id', 'canonical_path', 'title', 'description', 'is_indexable', 'schema']),
        ];
    }

    /** @param array<string, mixed> $manifest
     * @param  array<string, mixed>  $summary
     */
    private function recordAudit(Site $site, string $file, array $manifest, array $summary, string $status): void
    {
        $run = ImportRun::query()->create([
            'source' => 'seo_homepage_release:'.$site->key,
            'source_file' => basename($file),
            'status' => 'completed',
            'total_records' => 1,
            'processed_records' => 1,
            'summary' => $summary + ['manifest_sha256' => strtolower((string) hash_file('sha256', $file))],
            'started_at' => now(),
            'finished_at' => now(),
        ]);
        StagedImportRecord::query()->create([
            'import_run_id' => $run->id,
            'row_number' => 1,
            'entity_type' => 'homepage_indexability_release',
            'external_id' => $site->key.':/',
            'payload' => $manifest,
            'normalized_payload' => ['site_id' => $site->id, 'path' => '/', 'is_indexable' => $status === 'released_indexable'],
            'status' => $status,
        ]);
    }

    /** @return array<string, mixed> */
    private function readManifest(string $file): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Homepage manifest is not readable.');
        }
        $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest)) {
            throw new RuntimeException('Homepage manifest must be a JSON object.');
        }

        return $manifest;
    }

    private function rollbackOutputPath(string $manifestPath): string
    {
        $option = $this->option('rollback-output');
        if (is_string($option) && trim($option) !== '') {
            return $option;
        }

        return (preg_replace('/\.json$/i', '', $manifestPath) ?: $manifestPath).'.rollback.json';
    }

    /** @param array<string, mixed> $value */
    private function writeJsonAtomically(string $path, array $value): void
    {
        $directory = dirname($path);
        if (! is_dir($directory) || ! is_writable($directory)) {
            throw new RuntimeException('Rollback manifest directory is not writable.');
        }
        $temporary = $path.'.tmp.'.bin2hex(random_bytes(6));
        $json = json_encode($value, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR).PHP_EOL;
        if (file_put_contents($temporary, $json, LOCK_EX) === false || ! rename($temporary, $path)) {
            @unlink($temporary);
            throw new RuntimeException('Rollback manifest could not be written atomically.');
        }
    }

    /** @param array<string, mixed> $actual
     * @param  list<string>  $expected
     */
    private function assertExactKeys(array $actual, array $expected, string $label): void
    {
        $actualKeys = array_keys($actual);
        sort($actualKeys);
        sort($expected);
        if ($actualKeys !== $expected) {
            throw new RuntimeException("{$label} fields must be exactly: ".implode(', ', $expected).'.');
        }
    }

    private function assertHash(array $state, mixed $pin, string $label): void
    {
        $this->assertSha256($pin, $label);
        if (! hash_equals($this->hashState($state), $pin)) {
            throw new RuntimeException("{$label} changed after the manifest was approved.");
        }
    }

    private function assertSha256(mixed $pin, string $label): void
    {
        if (! is_string($pin) || preg_match('/^[a-f0-9]{64}$/', $pin) !== 1) {
            throw new RuntimeException("{$label} must be a lowercase SHA-256 hash.");
        }
    }

    /** @param array<string, mixed> $state */
    private function hashState(array $state): string
    {
        return hash('sha256', json_encode($this->canonicalize($state), JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
    }

    private function canonicalize(mixed $value): mixed
    {
        if (! is_array($value)) {
            return $value;
        }
        if (! array_is_list($value)) {
            ksort($value);
        }
        foreach ($value as $key => $child) {
            $value[$key] = $this->canonicalize($child);
        }

        return $value;
    }
}
