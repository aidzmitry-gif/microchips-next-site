<?php

namespace App\Console\Commands;

use App\Models\Site;
use Carbon\CarbonImmutable;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;

class BuildRbPriceEvidenceManifest extends Command
{
    protected $signature = 'catalog:build-rb-price-evidence
                            {bitrix_manifest : Generated RB import manifest CSV}
                            {output : Destination semicolon-delimited CSV}
                            {--site=microchips-by : Site key}
                            {--bitrix-manifest-sha256= : Exact SHA-256 pin enabling direct published bitrix:<id> prices}';

    protected $description = 'Build exact-identity RB price evidence: legacy site first, then current 1C price multiplied by two';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->option('site'))->first();
        if ($site === null) {
            $this->error('Unknown site key.');

            return self::FAILURE;
        }

        try {
            $manifestPath = (string) $this->argument('bitrix_manifest');
            $directBitrixEnabled = $this->verifyOptionalManifestPin(
                $manifestPath,
                (string) $this->option('bitrix-manifest-sha256')
            );
            $legacyPrices = $this->readLegacyPrices($manifestPath);
            $rows = $this->buildRows($site, $legacyPrices, $directBitrixEnabled);
            $this->writeRows((string) $this->argument('output'), $rows);
        } catch (RuntimeException $exception) {
            $this->error($exception->getMessage());

            return self::FAILURE;
        }

        $counts = collect($rows)->countBy('source');
        $directBitrixCount = collect($rows)
            ->where('price_type', 'legacy_public_price_direct_bitrix')
            ->count();
        $this->info(sprintf(
            'Built %d exact-identity row(s): legacy_site=%d, direct_bitrix=%d, one_c_x2=%d.',
            count($rows), (int) $counts->get('legacy_site', 0), $directBitrixCount,
            (int) $counts->get('one_c_x2', 0)
        ));

        return self::SUCCESS;
    }

    private function verifyOptionalManifestPin(string $path, string $expectedSha256): bool
    {
        $expectedSha256 = trim($expectedSha256);
        if ($expectedSha256 === '') {
            return false;
        }
        if (preg_match('/\A[a-f0-9]{64}\z/', $expectedSha256) !== 1) {
            throw new RuntimeException('Bitrix manifest SHA-256 pin must be exactly 64 lowercase hexadecimal characters.');
        }
        if (! is_file($path) || ! is_readable($path)) {
            throw new RuntimeException("Bitrix price manifest is not readable: {$path}");
        }
        $actualSha256 = hash_file('sha256', $path);
        if (! is_string($actualSha256) || ! hash_equals($expectedSha256, $actualSha256)) {
            throw new RuntimeException('Bitrix price manifest SHA-256 pin mismatch.');
        }

        return true;
    }

    /** @return array<string, array<string, string>> */
    private function readLegacyPrices(string $path): array
    {
        if (! is_file($path) || ! is_readable($path)) {
            throw new RuntimeException("Bitrix price manifest is not readable: {$path}");
        }
        $handle = fopen($path, 'rb');
        if ($handle === false) {
            throw new RuntimeException("Cannot open Bitrix price manifest: {$path}");
        }

        try {
            if (fread($handle, 3) !== "\xEF\xBB\xBF") {
                rewind($handle);
            }
            $headers = fgetcsv($handle, escape: '');
            if ($headers === false) {
                throw new RuntimeException('Bitrix price manifest is empty.');
            }
            foreach (['legacy_element_id', 'price_byn', 'price_status', 'price_source', 'legacy_url_candidate'] as $required) {
                if (! in_array($required, $headers, true)) {
                    throw new RuntimeException("Bitrix price manifest requires {$required}.");
                }
            }

            $result = [];
            while (($values = fgetcsv($handle, escape: '')) !== false) {
                if (count($values) !== count($headers)) {
                    throw new RuntimeException('Bitrix price manifest contains a malformed row.');
                }
                $row = array_combine($headers, $values);
                if ($row['price_status'] !== 'ok' || ! is_numeric($row['price_byn']) || (float) $row['price_byn'] <= 0) {
                    continue;
                }
                $legacyId = trim($row['legacy_element_id']);
                if ($legacyId === '' || isset($result[$legacyId])) {
                    throw new RuntimeException("Bitrix price manifest has an empty or duplicate priced legacy ID: {$legacyId}");
                }
                $result[$legacyId] = $row;
            }

            return $result;
        } finally {
            fclose($handle);
        }
    }

    /**
     * @param  array<string, array<string, string>>  $legacyPrices
     * @return list<array<string, string>>
     */
    private function buildRows(Site $site, array $legacyPrices, bool $directBitrixEnabled): array
    {
        $approvedByExternalId = DB::table('catalog_identity_candidates as candidates')
            ->join('one_c_nomenclature_items as one_c', 'one_c.id', '=', 'candidates.one_c_nomenclature_item_id')
            ->where('candidates.legacy_source', 'bitrix')
            ->where('candidates.review_status', 'approved_for_staging')
            ->get(['one_c.external_id', 'candidates.legacy_id'])
            ->keyBy('external_id');

        $candidateLegacyIds = $directBitrixEnabled
            ? DB::table('catalog_identity_candidates')
                ->pluck('legacy_id')
                ->mapWithKeys(fn (mixed $legacyId): array => [(string) $legacyId => true])
            : collect();
        $siteProductIdsWithCurrentEvidence = $directBitrixEnabled
            ? DB::table('site_product_price_evidences')
                ->where('site_id', $site->id)
                ->where('is_current', true)
                ->pluck('site_product_id')
                ->mapWithKeys(fn (mixed $siteProductId): array => [(string) $siteProductId => true])
            : collect();

        // Select only the commercial fields required for evidence. Loading the
        // full inventory Eloquent models also hydrates their large source JSON
        // payloads and previously exhausted the default PHP memory limit once
        // the RB catalogue exceeded 24k market rows.
        $inventory = DB::table('one_c_nomenclature_items as one_c')
            ->leftJoin('import_runs', 'import_runs.id', '=', 'one_c.import_run_id')
            ->where('one_c.is_group', false)
            ->whereNotNull('one_c.price')
            ->where('one_c.price', '>', 0)
            ->where('one_c.currency', $site->currency_code)
            ->orderBy('one_c.updated_at')
            ->get([
                'one_c.external_id', 'one_c.source_key', 'one_c.price', 'one_c.currency',
                'one_c.price_type', 'one_c.updated_at', 'import_runs.finished_at as import_finished_at',
            ])
            ->keyBy('external_id');

        $rows = [];
        $siteProducts = DB::table('site_products')
            ->join('products', 'products.id', '=', 'site_products.product_id')
            ->where('site_products.site_id', $site->id)
            ->orderBy('site_products.id')
            ->select(['site_products.id as site_product_id', 'site_products.is_published', 'products.external_id'])
            ->cursor();
        foreach ($siteProducts as $siteProduct) {
            $externalId = (string) $siteProduct->external_id;

            if ($directBitrixEnabled
                && $site->currency_code === 'BYN'
                && (bool) $siteProduct->is_published
                && preg_match('/\Abitrix:([0-9]+)\z/D', $externalId, $matches) === 1
            ) {
                $legacyId = $matches[1];
                $legacy = $legacyPrices[$legacyId] ?? null;
                if ($legacy !== null
                    && $legacy['price_source'] === 'bitrix_backup_2026-06-23'
                    && ! $candidateLegacyIds->has($legacyId)
                    && ! $siteProductIdsWithCurrentEvidence->has((string) $siteProduct->site_product_id)
                ) {
                    $rows[] = [
                        'product_external_id' => $externalId,
                        'source' => 'legacy_site',
                        'source_price' => $legacy['price_byn'],
                        'currency' => 'BYN',
                        'observed_at' => '2026-06-23T00:00:00+03:00',
                        'source_reference' => 'bitrix-backup://2026-06-23/element/'.$legacyId,
                        'source_external_id' => $legacyId,
                        'multiplier' => '1',
                        'price_type' => 'legacy_public_price_direct_bitrix',
                    ];

                    continue;
                }
            }

            $candidate = $approvedByExternalId->get($externalId);
            $legacy = $candidate === null ? null : ($legacyPrices[(string) $candidate->legacy_id] ?? null);
            if ($legacy !== null) {
                $sourceDate = str_replace('bitrix_backup_', '', $legacy['price_source']);
                $rows[] = [
                    'product_external_id' => $externalId,
                    'source' => 'legacy_site',
                    'source_price' => $legacy['price_byn'],
                    'currency' => $site->currency_code,
                    'observed_at' => $sourceDate.'T00:00:00+03:00',
                    'source_reference' => 'bitrix-backup://'.$sourceDate.'/element/'.$candidate->legacy_id,
                    'source_external_id' => (string) $candidate->legacy_id,
                    'multiplier' => '1',
                    'price_type' => 'legacy_public_price',
                ];

                continue;
            }

            $oneC = $inventory->get($externalId);
            if ($oneC === null || $oneC->price_type === null || trim((string) $oneC->price_type) === '') {
                continue;
            }
            $observedAt = $oneC->import_finished_at ?? $oneC->updated_at;
            if ($observedAt === null) {
                continue;
            }
            $rows[] = [
                'product_external_id' => $externalId,
                'source' => 'one_c_x2',
                'source_price' => (string) $oneC->price,
                'currency' => (string) $oneC->currency,
                'observed_at' => CarbonImmutable::parse((string) $observedAt)->toIso8601String(),
                'source_reference' => '1c-inventory://'.$oneC->source_key.'/'.$oneC->external_id,
                'source_external_id' => (string) $oneC->external_id,
                'multiplier' => '2',
                'price_type' => (string) $oneC->price_type,
            ];
        }

        usort($rows, fn (array $left, array $right): int => [$left['source'], $left['product_external_id']] <=> [$right['source'], $right['product_external_id']]);

        return $rows;
    }

    /** @param list<array<string, string>> $rows */
    private function writeRows(string $path, array $rows): void
    {
        $directory = dirname($path);
        if (! is_dir($directory) || ! is_writable($directory)) {
            throw new RuntimeException("Output directory is not writable: {$directory}");
        }
        $handle = fopen($path, 'wb');
        if ($handle === false) {
            throw new RuntimeException("Cannot write price evidence manifest: {$path}");
        }
        try {
            $headers = ['product_external_id', 'source', 'source_price', 'currency', 'observed_at', 'source_reference', 'source_external_id', 'multiplier', 'price_type'];
            fputcsv($handle, $headers, ';', '"', '');
            foreach ($rows as $row) {
                fputcsv($handle, array_map(fn (string $header): string => $row[$header], $headers), ';', '"', '');
            }
        } finally {
            fclose($handle);
        }
    }
}
