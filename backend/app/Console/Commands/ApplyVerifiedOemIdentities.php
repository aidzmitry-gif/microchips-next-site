<?php

namespace App\Console\Commands;

use App\Domain\Content\ModelCoreIdentityMatcher;
use App\Domain\Imports\ProductIdentity;
use App\Domain\Imports\ProductIdentityGuard;
use App\Events\SiteContentChanged;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use Carbon\CarbonImmutable;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/**
 * Records exact OEM identity evidence for an existing noindex catalogue card.
 * Manufacturer sources are accepted directly. An authorised-distributor
 * catalogue is accepted only with a same-host, hash-pinned authority page
 * containing the exact authorisation statement. This is deliberately narrower
 * than a description import: identity evidence proves neither technical facts
 * nor availability nor price.
 */
class ApplyVerifiedOemIdentities extends Command
{
    private const OFFICIAL_SOURCE_KINDS = [
        'official_manufacturer_catalogue',
        'official_manufacturer_accessory_catalogue',
        'official_manufacturer_product_page',
        'official_manufacturer_service_document',
        'official_authorized_distributor_catalogue',
    ];

    protected $signature = 'catalog:apply-verified-oem-identities
                            {site : Site key}
                            {file : Schema-versioned JSON evidence manifest}
                            {--apply : Persist evidence and fill only blank manufacturer/MPN fields}';

    protected $description = 'Fill only blank OEM manufacturer/MPN fields on exact, official-source, noindex catalogue cards';

    public function __construct(private readonly ProductIdentityGuard $identityGuard)
    {
        parent::__construct();
    }

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            [$manifest, $raw] = $this->manifest((string) $this->argument('file'), $site);
            $hash = hash('sha256', $raw);
            $validated = $this->validateCurrentState($site, $manifest['products'], false, $manifest['target_kind']);
            $summary = [
                'mode' => $this->option('apply') ? 'apply' : 'dry_run',
                'site' => $site->key,
                'target_kind' => $manifest['target_kind'],
                'records' => count($validated),
                'manifest_sha256' => $hash,
                'identities_filled' => 0,
                'unchanged' => 0,
                'commercial_fields_changed' => 0,
                'publication_fields_changed' => 0,
            ];

            if (! $this->option('apply')) {
                $this->line((string) json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

                return self::SUCCESS;
            }

            $source = ($manifest['target_kind'] === 'active_1c'
                ? 'verified_oem_identity_active_1c:'
                : 'verified_oem_identity:').$site->key;
            $sitePaths = [];
            $result = DB::transaction(function () use ($site, $manifest, $hash, $source, &$sitePaths): array {
                if (DB::getDriverName() === 'pgsql') {
                    DB::select('select pg_advisory_xact_lock(hashtext(?))', ['verified-oem-identity:'.$source.':'.$hash]);
                }

                // Revalidate and lock after entering the write transaction so
                // a concurrent importer cannot change identity between the
                // dry validation and the canonical update.
                $locked = $this->validateCurrentState($site, $manifest['products'], true, $manifest['target_kind']);
                $existingRun = $this->completedEvidenceRun($source, $hash, $manifest['products']);
                if ($existingRun !== null
                    && collect($locked)->every(fn (array $entry): bool => $entry['already_applied'])) {
                    foreach ($locked as $entry) {
                        foreach ($entry['site_paths'] as $siteKey => $entryPaths) {
                            $sitePaths[$siteKey] = [...($sitePaths[$siteKey] ?? []), ...$entryPaths];
                        }
                    }

                    return ['filled' => 0, 'unchanged' => count($locked), 'idempotent' => true];
                }

                $run = ImportRun::query()->create([
                    'source' => $source,
                    'source_file' => basename((string) $this->argument('file')),
                    'status' => 'running',
                    'total_records' => count($locked),
                    'processed_records' => 0,
                    'started_at' => now(),
                    'summary' => ['manifest_sha256' => $hash],
                ]);
                $filled = 0;
                $unchanged = 0;

                foreach ($locked as $index => $entry) {
                    /** @var Product $product */
                    $product = $entry['product'];
                    /** @var SiteProduct $siteProduct */
                    $siteProduct = $entry['site_product'];
                    $row = $entry['row'];
                    $beforeProduct = $product->only(['name', 'sku', 'status']);
                    $beforeSite = $siteProduct->only(['is_published', 'availability', 'price']);

                    if ($entry['already_applied']) {
                        $unchanged++;
                    } else {
                        $product->update([
                            'manufacturer' => blank($product->manufacturer) ? trim($row['manufacturer']) : $product->manufacturer,
                            'mpn' => blank($product->mpn) ? trim($row['mpn']) : $product->mpn,
                        ]);
                        $filled++;
                    }

                    $product->refresh();
                    $siteProduct->refresh();
                    if ($product->only(['name', 'sku', 'status']) !== $beforeProduct
                        || $siteProduct->only(['is_published', 'availability', 'price']) !== $beforeSite) {
                        throw new RuntimeException("Product {$product->external_id} changed outside the permitted identity fields.");
                    }

                    StagedImportRecord::query()->create([
                        'import_run_id' => $run->id,
                        'row_number' => $index + 1,
                        'entity_type' => 'verified_oem_identity_evidence',
                        'external_id' => $product->external_id,
                        'payload' => $row,
                        'normalized_payload' => [
                            'manufacturer' => ProductIdentity::normalize($row['manufacturer']),
                            'mpn' => ProductIdentity::normalize($row['mpn']),
                            'evidence_checksum' => hash('sha256', json_encode($row, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES)),
                        ],
                        'validation_errors' => [],
                        'status' => 'reviewed_evidence',
                        'review_note' => $manifest['target_kind'] === 'active_1c'
                            ? 'Exact OEM identity for an active 1C product; no commercial, publication or technical-specification claim.'
                            : ($row['source_kind'] === 'official_authorized_distributor_catalogue'
                            ? 'Exact OEM identity from an authorised-distributor catalogue with hash-pinned authority proof; no commercial, publication or technical-specification claim.'
                            : 'Exact first-party OEM identity only; no commercial, publication or technical-specification claim.'),
                    ]);
                    foreach ($entry['site_paths'] as $siteKey => $entryPaths) {
                        $sitePaths[$siteKey] = [...($sitePaths[$siteKey] ?? []), ...$entryPaths];
                    }
                }

                $run->update([
                    'status' => 'completed',
                    'processed_records' => count($locked),
                    'summary' => [
                        'manifest_sha256' => $hash,
                        'identities_filled' => $filled,
                        'unchanged' => $unchanged,
                        'commercial_fields_changed' => 0,
                        'publication_fields_changed' => 0,
                    ],
                    'finished_at' => now(),
                ]);

                return ['filled' => $filled, 'unchanged' => $unchanged, 'idempotent' => false];
            });

            $summary['identities_filled'] = $result['filled'];
            $summary['unchanged'] = $result['unchanged'];
            if (! $result['idempotent']) {
                foreach ($sitePaths as $siteKey => $affectedPaths) {
                    $affectedSite = Site::query()->where('key', $siteKey)->firstOrFail();
                    SiteContentChanged::dispatch($affectedSite, array_values(array_unique([...$affectedPaths, '/catalog'])));
                }
            }
            $this->line((string) json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /**
     * @param  list<array<string, mixed>>  $rows
     * @return list<array{row:array<string,mixed>,product:Product,site_product:SiteProduct,path:string,site_paths:array<string,list<string>>,already_applied:bool}>
     */
    private function validateCurrentState(Site $site, array $rows, bool $lock = false, string $targetKind = 'bitrix_draft'): array
    {
        $validated = [];
        foreach ($rows as $row) {
            $query = Product::query()->where('external_id', $row['external_id']);
            $product = $lock ? $query->lockForUpdate()->first() : $query->first();
            $validTarget = $product !== null && (
                ($targetKind === 'bitrix_draft'
                    && str_starts_with($product->external_id, 'bitrix:')
                    && $product->status === 'draft')
                || ($targetKind === 'active_1c'
                    && ! str_starts_with($product->external_id, 'bitrix:')
                    && $product->status === 'active')
            );
            if (! $validTarget || $product->name !== $row['current_name']) {
                throw new RuntimeException('Pinned product target/current name mismatch.');
            }
            if (! ModelCoreIdentityMatcher::nameContains($product->name, $row['manufacturer'])
                || ! ModelCoreIdentityMatcher::nameContains($product->name, $row['mpn'])) {
                throw new RuntimeException("Product {$product->external_id} name lacks the bounded manufacturer or MPN.");
            }
            foreach (['manufacturer', 'mpn'] as $field) {
                $before = ProductIdentity::normalize($product->getAttribute($field));
                $verified = ProductIdentity::normalize($row[$field]);
                if ($before !== null && $before !== $verified) {
                    throw new RuntimeException("Product {$product->external_id} existing {$field} conflicts with official evidence.");
                }
            }

            $this->identityGuard->assertCanPersist([
                'external_id' => $product->external_id,
                'sku' => $product->sku,
                'manufacturer' => $row['manufacturer'],
                'mpn' => $row['mpn'],
            ], $product);

            $siteProductQuery = SiteProduct::query()
                ->where('site_id', $site->id)
                ->where('product_id', $product->id);
            $siteProduct = $lock ? $siteProductQuery->lockForUpdate()->sole() : $siteProductQuery->sole();
            if (! $siteProduct->is_published) {
                throw new RuntimeException("Product {$product->external_id} is not a visible noindex preview.");
            }
            $urlQuery = SiteUrl::query()
                ->where('site_id', $site->id)
                ->where('target_type', 'product')
                ->where('target_id', $siteProduct->id);
            $urls = $lock ? $urlQuery->lockForUpdate()->get() : $urlQuery->get();
            $seoQuery = SiteSeo::query()
                ->where('site_id', $site->id)
                ->where('resource_type', 'product')
                ->where('resource_id', $siteProduct->id);
            $seoRows = $lock ? $seoQuery->lockForUpdate()->get() : $seoQuery->get();
            if ($urls->count() !== 1 || $urls->first()->is_indexable
                || $seoRows->count() !== 1 || $seoRows->first()->is_indexable || $seoRows->first()->schema !== null) {
                throw new RuntimeException("Product {$product->external_id} must have exactly one schema-null noindex URL and SEO row.");
            }

            $sitePaths = [];
            $allSiteProductQuery = SiteProduct::query()
                ->with('site')
                ->where('product_id', $product->id);
            $allSiteProducts = $lock ? $allSiteProductQuery->lockForUpdate()->get() : $allSiteProductQuery->get();
            foreach ($allSiteProducts as $linkedSiteProduct) {
                $linkedUrlQuery = SiteUrl::query()
                    ->where('site_id', $linkedSiteProduct->site_id)
                    ->where('target_type', 'product')
                    ->where('target_id', $linkedSiteProduct->id);
                $linkedUrls = $lock ? $linkedUrlQuery->lockForUpdate()->get() : $linkedUrlQuery->get();
                $linkedSeoQuery = SiteSeo::query()
                    ->where('site_id', $linkedSiteProduct->site_id)
                    ->where('resource_type', 'product')
                    ->where('resource_id', $linkedSiteProduct->id);
                $linkedSeoRows = $lock ? $linkedSeoQuery->lockForUpdate()->get() : $linkedSeoQuery->get();
                if ($linkedUrls->count() !== 1 || $linkedUrls->first()->is_indexable
                    || $linkedSeoRows->count() !== 1 || $linkedSeoRows->first()->is_indexable
                    || $linkedSeoRows->first()->schema !== null) {
                    throw new RuntimeException("Product {$product->external_id} has a linked site page outside the schema-null noindex preview gate.");
                }
                $sitePaths[$linkedSiteProduct->site->key][] = $linkedUrls->first()->path;
            }

            $validated[] = [
                'row' => $row,
                'product' => $product,
                'site_product' => $siteProduct,
                'path' => $urls->first()->path,
                'site_paths' => $sitePaths,
                'already_applied' => ProductIdentity::normalize($product->manufacturer) === ProductIdentity::normalize($row['manufacturer'])
                    && ProductIdentity::normalize($product->mpn) === ProductIdentity::normalize($row['mpn']),
            ];
        }

        return $validated;
    }

    /** @return array{array{schema_version:int,site_key:string,target_kind:string,products:list<array<string,mixed>>},string} */
    private function manifest(string $path, Site $site): array
    {
        if (! is_file($path) || ! is_readable($path)) {
            throw new RuntimeException('OEM identity manifest is missing or unreadable.');
        }
        $raw = file_get_contents($path);
        if ($raw === false) {
            throw new RuntimeException('OEM identity manifest could not be read.');
        }
        $manifest = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest) || ($manifest['schema_version'] ?? null) !== 1
            || ($manifest['site_key'] ?? null) !== $site->key
            || ! is_array($manifest['products'] ?? null) || $manifest['products'] === []) {
            throw new RuntimeException('Manifest requires schema_version=1, the selected site_key and a non-empty products list.');
        }
        $targetKind = $manifest['target_kind'] ?? 'bitrix_draft';
        if (! is_string($targetKind) || ! in_array($targetKind, ['bitrix_draft', 'active_1c'], true)) {
            throw new RuntimeException('Manifest target_kind must be bitrix_draft or active_1c.');
        }
        $manifest['target_kind'] = $targetKind;

        $seenExternalIds = [];
        $seenMpns = [];
        $allowed = [
            'external_id', 'current_name', 'manufacturer', 'mpn', 'source_url',
            'source_kind', 'source_publisher', 'checked_at', 'product_type',
            'source_snapshot_path', 'source_snapshot_sha256',
            'authority_url', 'authority_snapshot_path', 'authority_snapshot_sha256',
            'authority_statement',
        ];
        $required = array_values(array_diff($allowed, [
            'authority_url', 'authority_snapshot_path', 'authority_snapshot_sha256', 'authority_statement',
        ]));
        foreach ($manifest['products'] as $index => $row) {
            if (! is_array($row) || array_diff(array_keys($row), $allowed) !== []) {
                throw new RuntimeException("Product row {$index} is not a supported OEM evidence object.");
            }
            foreach ($required as $field) {
                if (! is_string($row[$field] ?? null) || blank($row[$field])) {
                    throw new RuntimeException("Product row {$index} requires {$field}.");
                }
            }
            if (! in_array($row['source_kind'], self::OFFICIAL_SOURCE_KINDS, true)
                || ! filter_var($row['source_url'], FILTER_VALIDATE_URL)
                || parse_url($row['source_url'], PHP_URL_SCHEME) !== 'https') {
                throw new RuntimeException("Product row {$index} requires an HTTPS official manufacturer source.");
            }
            $snapshotPath = trim($row['source_snapshot_path']);
            if (! str_starts_with($snapshotPath, '/') && ! preg_match('/^[A-Za-z]:[\\\\\/]/', $snapshotPath)) {
                $snapshotPath = dirname($path).DIRECTORY_SEPARATOR.$snapshotPath;
            }
            $snapshotSha256 = strtolower(trim($row['source_snapshot_sha256']));
            if (! is_file($snapshotPath) || ! is_readable($snapshotPath)
                || ! preg_match('/^[0-9a-f]{64}$/', $snapshotSha256)
                || hash_file('sha256', $snapshotPath) !== $snapshotSha256) {
                throw new RuntimeException("Product row {$index} requires a readable SHA-256-pinned source snapshot.");
            }
            $authorityFields = [
                'authority_url', 'authority_snapshot_path', 'authority_snapshot_sha256', 'authority_statement',
            ];
            if ($row['source_kind'] === 'official_authorized_distributor_catalogue') {
                foreach ($authorityFields as $field) {
                    if (! is_string($row[$field] ?? null) || blank($row[$field])) {
                        throw new RuntimeException("Product row {$index} authorised-distributor evidence requires {$field}.");
                    }
                }
                if (! filter_var($row['authority_url'], FILTER_VALIDATE_URL)
                    || parse_url($row['authority_url'], PHP_URL_SCHEME) !== 'https'
                    || strcasecmp((string) parse_url($row['authority_url'], PHP_URL_HOST), (string) parse_url($row['source_url'], PHP_URL_HOST)) !== 0) {
                    throw new RuntimeException("Product row {$index} authority proof must use HTTPS on the catalogue host.");
                }
                $authorityPath = trim($row['authority_snapshot_path']);
                if (! str_starts_with($authorityPath, '/') && ! preg_match('/^[A-Za-z]:[\\\\\/]/', $authorityPath)) {
                    $authorityPath = dirname($path).DIRECTORY_SEPARATOR.$authorityPath;
                }
                $authoritySha256 = strtolower(trim($row['authority_snapshot_sha256']));
                $authorityRaw = is_file($authorityPath) && is_readable($authorityPath)
                    ? file_get_contents($authorityPath)
                    : false;
                if ($authorityRaw === false
                    || ! preg_match('/^[0-9a-f]{64}$/', $authoritySha256)
                    || hash_file('sha256', $authorityPath) !== $authoritySha256
                    || mb_stripos($authorityRaw, trim($row['authority_statement'])) === false) {
                    throw new RuntimeException("Product row {$index} requires hash-pinned authority proof containing the exact authorisation statement.");
                }
            } else {
                foreach ($authorityFields as $field) {
                    if (array_key_exists($field, $row)) {
                        throw new RuntimeException("Product row {$index} manufacturer evidence must not carry distributor authority fields.");
                    }
                }
            }
            try {
                $checkedAt = CarbonImmutable::createFromFormat('!Y-m-d', $row['checked_at']);
            } catch (Throwable) {
                $checkedAt = null;
            }
            if ($checkedAt === null || $checkedAt->format('Y-m-d') !== $row['checked_at'] || $checkedAt->isFuture()) {
                throw new RuntimeException("Product row {$index} checked_at must be a non-future YYYY-MM-DD date.");
            }

            $externalId = trim($row['external_id']);
            $mpn = ProductIdentity::normalize($row['mpn']);
            if (isset($seenExternalIds[$externalId]) || $mpn === null || isset($seenMpns[$mpn])) {
                throw new RuntimeException('OEM identity manifest repeats an external ID or normalized MPN.');
            }
            $seenExternalIds[$externalId] = true;
            $seenMpns[$mpn] = true;
        }

        return [$manifest, $raw];
    }

    /**
     * @param  list<array<string, mixed>>  $rows
     */
    private function completedEvidenceRun(string $source, string $hash, array $rows): ?ImportRun
    {
        $run = ImportRun::query()
            ->where('source', $source)
            ->where('status', 'completed')
            ->where('summary->manifest_sha256', $hash)
            ->latest('id')
            ->first();
        if ($run === null) {
            return null;
        }

        $expected = collect($rows)->mapWithKeys(static function (array $row): array {
            $checksum = hash('sha256', json_encode($row, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

            return [$row['external_id'] => $checksum];
        })->all();
        $records = StagedImportRecord::query()
            ->where('import_run_id', $run->id)
            ->where('entity_type', 'verified_oem_identity_evidence')
            ->where('status', 'reviewed_evidence')
            ->get();
        $actual = $records->mapWithKeys(static fn (StagedImportRecord $record): array => [
            $record->external_id => $record->normalized_payload['evidence_checksum'] ?? null,
        ])->all();
        ksort($expected);
        ksort($actual);
        if ($records->count() !== count($expected) || $actual !== $expected) {
            throw new RuntimeException('Completed OEM evidence run is incomplete or does not match the pinned manifest.');
        }

        return $run;
    }
}
