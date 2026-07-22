<?php

namespace App\Console\Commands;

use App\Domain\Imports\OneCNomenclatureClassifier;
use App\Models\ImportRun;
use App\Models\OneCNomenclatureItem;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class InventoryOneCNomenclature extends Command
{
    protected $signature = 'catalog:inventory-1c
                            {file : Absolute or project-relative path to the complete 1C nomenclature CSV}
                            {--delimiter=; : Single-character CSV delimiter}
                            {--source-key=1c_nomenclature : Stable source namespace}';

    protected $description = 'Inventory the complete 1C nomenclature without creating or publishing products';

    /** @var array<string, string> */
    private const HEADERS = [
        'этогруппа' => 'is_group',
        'код' => 'external_id',
        'артикул' => 'article',
        'наименование' => 'name',
        'родителькод' => 'parent_external_id',
        'родительнаименование' => 'parent_name',
        'полныйпуть' => 'full_path',
        'единица' => 'unit',
        'цена' => 'price',
        'валюта' => 'currency',
        'видцены' => 'price_type',
    ];

    public function __construct(private readonly OneCNomenclatureClassifier $classifier)
    {
        parent::__construct();
    }

    public function handle(): int
    {
        $file = (string) $this->argument('file');
        $delimiter = (string) $this->option('delimiter');
        $sourceKey = trim((string) $this->option('source-key'));

        if (! is_file($file)) {
            $this->error('CSV file was not found.');

            return self::FAILURE;
        }

        if (mb_strlen($delimiter) !== 1 || $sourceKey === '') {
            $this->error('Delimiter must be one character and source key must not be empty.');

            return self::FAILURE;
        }

        $handle = fopen($file, 'rb');
        if ($handle === false) {
            throw new RuntimeException("Unable to open {$file}.");
        }

        try {
            $headers = $this->readHeaders($handle, $delimiter);
        } catch (Throwable $error) {
            fclose($handle);
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $run = ImportRun::create([
            'source' => '1c_nomenclature_inventory',
            'source_file' => basename($file),
            'status' => 'running',
            'started_at' => now(),
        ]);

        $summary = [
            'source_key' => $sourceKey,
            'csv_records' => 0,
            'total_rows' => 0,
            'empty_records' => 0,
            'groups' => 0,
            'products' => 0,
            'articles_filled' => 0,
            'missing_articles' => 0,
            'storage_location_articles' => 0,
            'suspected_non_products' => 0,
            'classification_status_counts' => [],
            'invalid_rows' => 0,
            'invalid_row_details' => [],
            'duplicate_source_rows' => 0,
            'inserted' => 0,
            'updated' => 0,
            'publication_status' => 'not_publishable_inventory_only',
        ];

        /** @var array<string, true> $seen */
        $seen = [];
        $rowNumber = 1;

        try {
            DB::transaction(function () use ($handle, $delimiter, $headers, $sourceKey, $run, &$summary, &$seen, &$rowNumber): void {
                while (($row = fgetcsv($handle, 0, $delimiter, '"', '')) !== false) {
                    $rowNumber++;
                    $summary['csv_records']++;
                    if ($row === [null] || $row === []) {
                        $summary['empty_records']++;

                        continue;
                    }

                    $summary['total_rows']++;

                    if (count($row) !== count($headers)) {
                        $summary['invalid_rows']++;
                        $this->rememberInvalidRow($summary, $rowNumber, 'column_count_mismatch', [
                            'column_count' => count($row),
                            'preview' => array_slice($row, 0, 5),
                        ]);

                        continue;
                    }

                    /** @var array<string, string|null> $payload */
                    $payload = array_combine($headers, $row);
                    $externalId = $this->clean($payload['external_id'] ?? null);
                    $name = $this->clean($payload['name'] ?? null);
                    $isGroup = $this->parseGroupFlag($payload['is_group'] ?? null);

                    if ($externalId === null || $name === null || $isGroup === null) {
                        $summary['invalid_rows']++;
                        $missing = array_keys(array_filter([
                            'external_id' => $externalId === null,
                            'name' => $name === null,
                            'is_group' => $isGroup === null,
                        ]));
                        $this->rememberInvalidRow($summary, $rowNumber, 'invalid_required_fields:'.implode(',', $missing));

                        continue;
                    }

                    $identity = $sourceKey.'|'.$externalId.'|'.($isGroup ? 'group' : 'item');
                    if (isset($seen[$identity])) {
                        $summary['duplicate_source_rows']++;

                        continue;
                    }
                    $seen[$identity] = true;

                    $article = $this->clean($payload['article'] ?? null);
                    $classification = $this->classifier->classify($isGroup, $article, $name);
                    $price = $this->parsePrice($payload['price'] ?? null);
                    $summary['classification_status_counts'][$classification['status']] =
                        ($summary['classification_status_counts'][$classification['status']] ?? 0) + 1;

                    $isGroup ? $summary['groups']++ : $summary['products']++;
                    if (! $isGroup) {
                        $article === null ? $summary['missing_articles']++ : $summary['articles_filled']++;
                    }
                    if (in_array('article_looks_like_storage_location', $classification['flags'], true)) {
                        $summary['storage_location_articles']++;
                    }
                    if (in_array('suspected_non_product', $classification['flags'], true)) {
                        $summary['suspected_non_products']++;
                    }

                    $attributes = [
                        'import_run_id' => $run->id,
                        'parent_external_id' => $this->clean($payload['parent_external_id'] ?? null),
                        'article' => $article,
                        'name' => $name,
                        'full_path' => $this->clean($payload['full_path'] ?? null),
                        'unit' => $this->clean($payload['unit'] ?? null),
                        'price' => $price,
                        'currency' => $this->currency($payload['currency'] ?? null),
                        'price_type' => $this->clean($payload['price_type'] ?? null),
                        'classification_status' => $classification['status'],
                        'classification_flags' => $classification['flags'],
                        'source_payload' => $payload,
                        'source_checksum' => hash('sha256', json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)),
                    ];

                    $item = OneCNomenclatureItem::query()->firstOrNew([
                        'source_key' => $sourceKey,
                        'external_id' => $externalId,
                        'is_group' => $isGroup,
                    ]);
                    $item->exists ? $summary['updated']++ : $summary['inserted']++;
                    $item->fill($attributes)->save();
                }
            });

            $needsReview = $summary['invalid_rows'] > 0 || $summary['duplicate_source_rows'] > 0;
            $run->update([
                'status' => $needsReview ? 'needs_review' : 'inventory_ready',
                'total_records' => $summary['total_rows'],
                'processed_records' => $summary['groups'] + $summary['products'],
                'failed_records' => $summary['invalid_rows'] + $summary['duplicate_source_rows'],
                'summary' => $summary,
                'finished_at' => now(),
            ]);
        } catch (Throwable $error) {
            $run->update([
                'status' => 'failed',
                'summary' => [...$summary, 'error' => $error->getMessage(), 'row_number' => $rowNumber],
                'finished_at' => now(),
            ]);
            throw $error;
        } finally {
            fclose($handle);
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR));
        $this->warn('Inventory rows are not approved products and cannot be published.');

        return self::SUCCESS;
    }

    /** @param array<string, mixed> $summary */
    /** @param array<string, mixed> $context */
    private function rememberInvalidRow(array &$summary, int $rowNumber, string $reason, array $context = []): void
    {
        if (count($summary['invalid_row_details']) >= 20) {
            return;
        }

        $summary['invalid_row_details'][] = [
            'row_number' => $rowNumber,
            'reason' => $reason,
            ...$context,
        ];
    }

    /** @return list<string> */
    private function readHeaders(mixed $handle, string $delimiter): array
    {
        $raw = fgetcsv($handle, 0, $delimiter, '"', '');
        if ($raw === false) {
            throw new RuntimeException('CSV file does not contain a header row.');
        }

        $headers = array_map(function (mixed $header): string {
            $normalized = mb_strtolower(ltrim(trim((string) $header), "\xEF\xBB\xBF"));
            $normalized = preg_replace('/[^\p{L}\p{N}]+/u', '', $normalized) ?? '';

            return self::HEADERS[$normalized] ?? $normalized;
        }, $raw);

        foreach (['is_group', 'external_id', 'name'] as $required) {
            if (! in_array($required, $headers, true)) {
                throw new RuntimeException("Required 1C column is missing: {$required}.");
            }
        }

        if (count($headers) !== count(array_unique($headers))) {
            throw new RuntimeException('CSV contains duplicate normalized headers.');
        }

        return $headers;
    }

    private function clean(mixed $value): ?string
    {
        return is_scalar($value) && trim((string) $value) !== '' ? trim((string) $value) : null;
    }

    private function parseGroupFlag(mixed $value): ?bool
    {
        $normalized = mb_strtolower(trim((string) $value));

        return match ($normalized) {
            'истина', 'true', '1', 'yes', 'y' => true,
            'ложь', 'false', '0', 'no', 'n' => false,
            default => null,
        };
    }

    private function parsePrice(mixed $value): ?string
    {
        $value = $this->clean($value);
        if ($value === null) {
            return null;
        }

        $normalized = str_replace([' ', ','], ['', '.'], $value);

        return is_numeric($normalized) ? $normalized : null;
    }

    private function currency(mixed $value): ?string
    {
        $currency = $this->clean($value);

        return $currency !== null && mb_strlen($currency) === 3 ? mb_strtoupper($currency) : null;
    }
}
