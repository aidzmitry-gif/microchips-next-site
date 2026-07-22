<?php

namespace App\Console\Commands;

use App\Models\CatalogIdentityCandidate;
use App\Models\ImportRun;
use App\Models\OneCNomenclatureItem;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class ImportCatalogIdentityCandidates extends Command
{
    protected $signature = 'catalog:import-identity-candidates
                            {file? : CSV created by build-rb-1c-review-queue.py}
                            {--source-key=1c_nomenclature : Inventory source namespace}
                            {--initial-batch=50 : Number of rows in the first review batch}';

    protected $description = 'Load strict Bitrix-to-1C matches as human-review candidates without staging products';

    /** @var list<string> */
    private const REQUIRED_HEADERS = [
        'Bitrix ID', 'Название сайта', '1С-код', '1С-Наименование', 'signature',
        'brand_ok', 'confidence', 'method', 'сравнение', 'queue_status',
        'review_required', 'selection_rule_version',
    ];

    public function handle(): int
    {
        $file = (string) ($this->argument('file') ?: base_path('../docs/imports/rb-1c-review-candidates.csv'));
        $sourceKey = trim((string) $this->option('source-key'));
        $initialBatch = filter_var($this->option('initial-batch'), FILTER_VALIDATE_INT, ['options' => ['min_range' => 1]]);

        if (! is_file($file) || $sourceKey === '' || $initialBatch === false) {
            $this->error('Candidate file, source key, or initial batch value is invalid.');

            return self::FAILURE;
        }

        try {
            [$headers, $rows] = $this->readCsv($file);
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $run = ImportRun::create([
            'source' => 'bitrix_1c_identity_candidates',
            'source_file' => basename($file),
            'status' => 'running',
            'started_at' => now(),
        ]);
        $summary = [
            'source_rows' => count($rows),
            'initial_batch_size' => $initialBatch,
            'inserted' => 0,
            'updated' => 0,
            'missing_inventory_items' => 0,
            'invalid_candidate_rows' => 0,
            'initial_batch' => 0,
            'backlog' => 0,
            'publication_status' => 'human_review_required',
        ];

        /** @var array<string, true> $seenLegacy */
        $seenLegacy = [];
        /** @var array<string, true> $seenOneC */
        $seenOneC = [];
        $initialBatchName = "rb-initial-{$initialBatch}";

        try {
            DB::transaction(function () use ($headers, $rows, $sourceKey, $initialBatch, $initialBatchName, $run, &$summary, &$seenLegacy, &$seenOneC): void {
                foreach ($rows as $offset => $values) {
                    if (count($values) !== count($headers)) {
                        $summary['invalid_candidate_rows']++;

                        continue;
                    }

                    /** @var array<string, string> $payload */
                    $payload = array_combine($headers, $values);
                    $legacyId = trim($payload['Bitrix ID'] ?? '');
                    $oneCCode = trim($payload['1С-код'] ?? '');
                    $validGate = ($payload['queue_status'] ?? '') === 'review_candidate'
                        && mb_strtolower(trim($payload['review_required'] ?? '')) === 'yes'
                        && (float) str_replace(',', '.', $payload['confidence'] ?? '') === 0.95
                        && mb_strtolower(trim($payload['brand_ok'] ?? '')) === 'yes'
                        && ! str_contains(mb_strtolower($payload['method'] ?? ''), 'generic');

                    if ($legacyId === '' || $oneCCode === '' || ! $validGate || isset($seenLegacy[$legacyId]) || isset($seenOneC[$oneCCode])) {
                        $summary['invalid_candidate_rows']++;

                        continue;
                    }
                    $seenLegacy[$legacyId] = true;
                    $seenOneC[$oneCCode] = true;

                    $inventory = OneCNomenclatureItem::query()
                        ->where('source_key', $sourceKey)
                        ->where('external_id', $oneCCode)
                        ->where('is_group', false)
                        ->first();
                    if ($inventory === null) {
                        $summary['missing_inventory_items']++;

                        continue;
                    }

                    $priority = $offset + 1;
                    $batch = $priority <= $initialBatch ? $initialBatchName : 'rb-backlog';
                    $candidate = CatalogIdentityCandidate::query()->firstOrNew([
                        'legacy_source' => 'bitrix',
                        'legacy_id' => $legacyId,
                    ]);

                    $candidate->exists ? $summary['updated']++ : $summary['inserted']++;
                    $batch === $initialBatchName ? $summary['initial_batch']++ : $summary['backlog']++;

                    $candidate->fill([
                        'import_run_id' => $run->id,
                        'one_c_nomenclature_item_id' => $inventory->id,
                        'legacy_name' => trim($payload['Название сайта']),
                        'review_priority' => $priority,
                        'review_batch' => $batch,
                        'confidence' => '0.9500',
                        'match_method' => trim($payload['method']),
                        'signature' => trim($payload['signature']) ?: null,
                        'comparison_status' => trim($payload['сравнение']) ?: null,
                        'source_payload' => $payload,
                        'source_checksum' => hash('sha256', json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR)),
                    ]);
                    if (! $candidate->exists) {
                        $candidate->review_status = 'pending';
                    }
                    $candidate->save();
                }
            });

            $hasErrors = $summary['missing_inventory_items'] > 0 || $summary['invalid_candidate_rows'] > 0;
            $run->update([
                'status' => $hasErrors ? 'needs_review' : 'review_queue_ready',
                'total_records' => count($rows),
                'processed_records' => $summary['inserted'] + $summary['updated'],
                'failed_records' => $summary['missing_inventory_items'] + $summary['invalid_candidate_rows'],
                'summary' => $summary,
                'finished_at' => now(),
            ]);
        } catch (Throwable $error) {
            $run->update([
                'status' => 'failed',
                'summary' => [...$summary, 'error' => $error->getMessage()],
                'finished_at' => now(),
            ]);
            throw $error;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR));
        $this->warn('Candidates require explicit review and are not staged or published.');

        return self::SUCCESS;
    }

    /** @return array{0: list<string>, 1: list<list<string>>} */
    private function readCsv(string $file): array
    {
        $handle = fopen($file, 'rb');
        if ($handle === false) {
            throw new RuntimeException("Unable to open {$file}.");
        }

        try {
            $headers = fgetcsv($handle, 0, ',', '"', '');
            if ($headers === false) {
                throw new RuntimeException('Candidate CSV does not contain headers.');
            }
            $headers = array_map(fn (mixed $header): string => ltrim(trim((string) $header), "\xEF\xBB\xBF"), $headers);
            $missing = array_diff(self::REQUIRED_HEADERS, $headers);
            if ($missing !== []) {
                throw new RuntimeException('Candidate CSV misses columns: '.implode(', ', $missing));
            }

            $rows = [];
            while (($row = fgetcsv($handle, 0, ',', '"', '')) !== false) {
                if ($row !== [null] && $row !== []) {
                    $rows[] = array_map(fn (mixed $value): string => trim((string) $value), $row);
                }
            }

            return [$headers, $rows];
        } finally {
            fclose($handle);
        }
    }
}
