<?php

namespace App\Console\Commands;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use Carbon\CarbonImmutable;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;

class ImportVerifiedSitePrices extends Command
{
    protected $signature = 'catalog:import-verified-prices
                            {site : Site key}
                            {file : Semicolon-delimited evidence CSV}
                            {--apply : Persist evidence and update site prices}';

    protected $description = 'Validate and import provenance-backed site prices; legacy site wins and 1C is multiplied by two';

    /** @var array<string, int> */
    private const PRIORITY = [
        SiteProductPriceEvidence::SOURCE_ONE_C_X2 => 10,
        SiteProductPriceEvidence::SOURCE_LEGACY_SITE => 20,
    ];

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Unknown site key.');

            return self::FAILURE;
        }

        try {
            $rows = $this->readRows((string) $this->argument('file'));
            $validated = $this->validateRows($site, $rows);
        } catch (RuntimeException $exception) {
            $this->error($exception->getMessage());

            return self::FAILURE;
        }

        $bySource = collect($validated)->countBy('source')->sortKeys();
        $this->line(sprintf(
            'Validated %d price evidence row(s): %s.',
            count($validated),
            $bySource->map(fn (int $count, string $source): string => "{$source}={$count}")->implode(', ')
        ));

        if (! $this->option('apply')) {
            $this->warn('Dry run only: no evidence or site price was changed.');

            return self::SUCCESS;
        }

        $result = DB::transaction(function () use ($site, $validated): array {
            $created = 0;
            $updatedPrices = 0;

            foreach ($validated as $row) {
                $evidence = SiteProductPriceEvidence::query()->firstOrCreate(
                    ['evidence_key' => $row['evidence_key']],
                    $row
                );
                $created += $evidence->wasRecentlyCreated ? 1 : 0;

                $current = SiteProductPriceEvidence::query()
                    ->where('site_product_id', $row['site_product_id'])
                    ->where('is_current', true)
                    ->orderByDesc('observed_at')
                    ->first();

                if ($current !== null && ! $this->shouldReplace($current, $evidence)) {
                    continue;
                }

                SiteProductPriceEvidence::query()
                    ->where('site_product_id', $row['site_product_id'])
                    ->where('is_current', true)
                    ->update(['is_current' => false]);
                $evidence->forceFill(['is_current' => true])->save();

                $siteProduct = SiteProduct::query()
                    ->where('site_id', $site->id)
                    ->findOrFail($row['site_product_id']);
                if ($siteProduct->price !== $evidence->calculated_price) {
                    $siteProduct->update(['price' => $evidence->calculated_price]);
                    $updatedPrices++;
                }
            }

            return compact('created', 'updatedPrices');
        });

        $this->info(sprintf(
            'Applied: evidence_created=%d, site_prices_updated=%d. Publication and availability were not changed.',
            $result['created'], $result['updatedPrices']
        ));

        return self::SUCCESS;
    }

    private function shouldReplace(SiteProductPriceEvidence $current, SiteProductPriceEvidence $candidate): bool
    {
        $currentPriority = self::PRIORITY[$current->source] ?? 0;
        $candidatePriority = self::PRIORITY[$candidate->source] ?? 0;

        if ($candidatePriority !== $currentPriority) {
            return $candidatePriority > $currentPriority;
        }

        return $candidate->observed_at->greaterThan($current->observed_at);
    }

    /** @return list<array<string, string>> */
    private function readRows(string $path): array
    {
        if (! is_file($path) || ! is_readable($path)) {
            throw new RuntimeException("Price evidence CSV is not readable: {$path}");
        }

        $handle = fopen($path, 'rb');
        if ($handle === false) {
            throw new RuntimeException("Cannot open price evidence CSV: {$path}");
        }

        try {
            $headers = fgetcsv($handle, separator: ';', escape: '');
            if ($headers === false) {
                throw new RuntimeException('Price evidence CSV is empty.');
            }
            $headers = array_map(fn (string $value): string => mb_strtolower(trim($value)), $headers);
            $required = ['product_external_id', 'source', 'source_price', 'currency', 'observed_at', 'source_reference'];
            if (array_diff($required, $headers) !== []) {
                throw new RuntimeException('Price evidence CSV requires: '.implode(', ', $required).'.');
            }

            $rows = [];
            while (($values = fgetcsv($handle, separator: ';', escape: '')) !== false) {
                if (count($values) !== count($headers)) {
                    throw new RuntimeException('Price evidence CSV contains a malformed row.');
                }
                $rows[] = array_combine($headers, array_map('trim', $values));
            }

            return $rows;
        } finally {
            fclose($handle);
        }
    }

    /**
     * @param  list<array<string, string>>  $rows
     * @return list<array<string, mixed>>
     */
    private function validateRows(Site $site, array $rows): array
    {
        if ($rows === []) {
            throw new RuntimeException('Price evidence CSV contains no data rows.');
        }

        $seenRows = [];
        $validated = [];
        foreach ($rows as $offset => $row) {
            $line = $offset + 2;
            $externalId = $row['product_external_id'];
            if ($externalId === '') {
                throw new RuntimeException("Line {$line}: product_external_id is empty.");
            }

            $source = $row['source'];
            if (! array_key_exists($source, self::PRIORITY)) {
                throw new RuntimeException("Line {$line}: source must be legacy_site or one_c_x2.");
            }
            $rowIdentity = $externalId.'|'.$source;
            if (isset($seenRows[$rowIdentity])) {
                throw new RuntimeException("Line {$line}: product and source pair is duplicated.");
            }
            $seenRows[$rowIdentity] = true;

            $sourcePrice = filter_var(str_replace(',', '.', $row['source_price']), FILTER_VALIDATE_FLOAT);
            if ($sourcePrice === false || $sourcePrice <= 0) {
                throw new RuntimeException("Line {$line}: source_price must be positive.");
            }

            $currency = mb_strtoupper($row['currency']);
            if ($currency !== $site->currency_code) {
                throw new RuntimeException("Line {$line}: currency {$currency} does not match site currency {$site->currency_code}.");
            }

            if ($row['source_reference'] === '') {
                throw new RuntimeException("Line {$line}: source_reference is required.");
            }

            try {
                $observedAt = CarbonImmutable::parse($row['observed_at']);
            } catch (\Throwable) {
                throw new RuntimeException("Line {$line}: observed_at is invalid.");
            }
            if ($observedAt->isFuture()) {
                throw new RuntimeException("Line {$line}: observed_at cannot be in the future.");
            }

            $product = Product::query()->where('external_id', $externalId)->first();
            $siteProduct = $product === null ? null : SiteProduct::query()
                ->where('site_id', $site->id)
                ->where('product_id', $product->id)
                ->first();
            if ($siteProduct === null) {
                throw new RuntimeException("Line {$line}: product {$externalId} is not uniquely linked to this site.");
            }

            $multiplier = $source === SiteProductPriceEvidence::SOURCE_ONE_C_X2 ? 2.0 : 1.0;
            if (isset($row['multiplier']) && $row['multiplier'] !== '' && (float) str_replace(',', '.', $row['multiplier']) !== $multiplier) {
                throw new RuntimeException("Line {$line}: multiplier contradicts source policy.");
            }
            $calculated = round($sourcePrice * $multiplier, 2, PHP_ROUND_HALF_UP);
            $evidenceKey = hash('sha256', implode('|', [
                $site->id, $siteProduct->id, $source, number_format($sourcePrice, 4, '.', ''),
                number_format($multiplier, 4, '.', ''), $currency, $observedAt->toIso8601String(), $row['source_reference'],
            ]));

            $validated[] = [
                'site_id' => $site->id,
                'site_product_id' => $siteProduct->id,
                'source' => $source,
                'source_price' => number_format($sourcePrice, 4, '.', ''),
                'multiplier' => number_format($multiplier, 4, '.', ''),
                'calculated_price' => number_format($calculated, 2, '.', ''),
                'currency' => $currency,
                'price_type' => $row['price_type'] ?? null,
                'source_external_id' => $row['source_external_id'] ?? null,
                'source_reference' => $row['source_reference'],
                'observed_at' => $observedAt,
                'evidence_key' => $evidenceKey,
                'evidence' => ['product_external_id' => $externalId, 'input_line' => $line],
                'is_current' => false,
            ];
        }

        return $validated;
    }
}
