<?php

namespace App\Console\Commands;

use App\Domain\Imports\ProductIdentity;
use App\Domain\Imports\StageProductValidator;
use App\Models\DuplicateConflict;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use RuntimeException;

class StageOneCCatalog extends Command
{
    protected $signature = 'catalog:stage-1c
                            {file? : Absolute or project-relative path to a 1C CSV export}
                            {--delimiter=; : Single-character CSV delimiter}';

    protected $description = 'Validate and stage a 1C catalogue CSV without publishing any product to a regional site';

    public function __construct(private readonly StageProductValidator $validator)
    {
        parent::__construct();
    }

    public function handle(): int
    {
        $file = $this->argument('file') ?: config('imports.one_c_csv_path');
        $delimiter = (string) $this->option('delimiter');

        if (blank($file) || ! is_file($file)) {
            $this->error('CSV file was not found. Pass it as an argument or set ONE_C_CSV_PATH.');

            return self::FAILURE;
        }

        if (mb_strlen($delimiter) !== 1) {
            $this->error('The delimiter must contain exactly one character.');

            return self::FAILURE;
        }

        $handle = fopen($file, 'rb');
        if ($handle === false) {
            throw new RuntimeException("Unable to open {$file}.");
        }

        $run = ImportRun::create([
            'source' => '1c_csv',
            'source_file' => basename($file),
            'status' => 'running',
            'started_at' => now(),
        ]);

        try {
            $headers = fgetcsv($handle, 0, $delimiter);
            if ($headers === false) {
                throw new RuntimeException('The CSV file does not contain a header row.');
            }

            $headers = array_map(fn ($header) => $this->normalizeHeader((string) $header), $headers);
            /** @var array<string, list<int>> $seen */
            $seen = [];
            $rowNumber = 1;
            $processed = 0;

            while (($row = fgetcsv($handle, 0, $delimiter)) !== false) {
                $rowNumber++;
                if ($row === [null] || $row === []) {
                    continue;
                }

                // array_pad only pads short rows; a row with MORE columns than the
                // header stays longer, and on PHP 8 array_combine() throws instead of
                // returning false. Guard the column-count mismatch explicitly so a
                // ragged row is recorded invalid and the import continues.
                $values = array_pad($row, count($headers), null);
                if (count($values) !== count($headers)) {
                    StagedImportRecord::create([
                        'import_run_id' => $run->id,
                        'row_number' => $rowNumber,
                        'entity_type' => 'product',
                        'payload' => ['raw' => $row],
                        'status' => 'invalid',
                        'validation_errors' => ['csv' => 'Column count does not match the header.'],
                        'error' => 'Column count does not match the header.',
                    ]);

                    continue;
                }

                $payload = array_combine($headers, $values);

                $validation = $this->validator->normalizeAndValidate($payload);
                $externalId = $validation['data']['external_id'] ?? null;
                $record = StagedImportRecord::create([
                    'import_run_id' => $run->id,
                    'row_number' => $rowNumber,
                    'entity_type' => 'product',
                    'external_id' => filled($externalId) ? (string) $externalId : null,
                    'payload' => $payload,
                    'normalized_payload' => $validation['data'],
                    'validation_errors' => $validation['errors'],
                    'status' => $validation['errors'] === [] ? 'ready_for_review' : 'invalid',
                    'error' => $validation['errors'] === [] ? null : implode(' ', $validation['errors']),
                ]);
                $processed++;

                foreach ($this->matchKeys($validation['data']) as $matchKey) {
                    $seen[$matchKey][] = $record->id;
                }
            }

            foreach ($seen as $matchKey => $candidateIds) {
                $productIds = $this->conflictingExistingProductIds($matchKey, $candidateIds);

                if (count($candidateIds) < 2 && $productIds === []) {
                    continue;
                }

                DuplicateConflict::create([
                    'import_run_id' => $run->id,
                    'entity_type' => 'product',
                    'match_key' => $matchKey,
                    'candidate_ids' => [
                        'staged_record_ids' => $candidateIds,
                        'product_ids' => $productIds,
                    ],
                ]);

                StagedImportRecord::query()
                    ->whereIn('id', $candidateIds)
                    ->where('status', 'ready_for_review')
                    ->update([
                        'status' => 'duplicate',
                        'error' => "Duplicate conflict: {$matchKey}.",
                    ]);
            }

            $conflicts = DuplicateConflict::query()->where('import_run_id', $run->id)->count();
            $run->update([
                'status' => $conflicts > 0 ? 'needs_review' : 'ready_for_review',
                'total_records' => $processed,
                'processed_records' => $processed,
                'failed_records' => StagedImportRecord::query()->where('import_run_id', $run->id)->where('status', 'invalid')->count(),
                'summary' => [
                    'duplicate_conflicts' => $conflicts,
                    'ready_for_review' => StagedImportRecord::query()->where('import_run_id', $run->id)->where('status', 'ready_for_review')->count(),
                    'invalid' => StagedImportRecord::query()->where('import_run_id', $run->id)->where('status', 'invalid')->count(),
                ],
                'finished_at' => now(),
            ]);
            $this->info("Import run {$run->id} staged {$processed} records; {$conflicts} duplicate conflict(s) need review.");

            return self::SUCCESS;
        } catch (\Throwable $exception) {
            $run->update(['status' => 'failed', 'summary' => ['error' => $exception->getMessage()], 'finished_at' => now()]);
            throw $exception;
        } finally {
            fclose($handle);
        }
    }

    /**
     * @param  array<string, mixed>  $normalizedPayload
     * @return list<string>
     */
    private function matchKeys(array $normalizedPayload): array
    {
        $keys = [];

        foreach (ProductIdentity::FIELDS as $field) {
            $fingerprint = ProductIdentity::normalize($normalizedPayload[$field] ?? null);

            if ($fingerprint !== null) {
                $keys[] = $field.':'.$fingerprint;
            }
        }

        return $keys;
    }

    /**
     * An identical external ID is a legitimate update of the same shared product.
     * A matching SKU/MPN with a different (or absent) external ID must be reviewed.
     *
     * @param  list<int>  $stagedRecordIds
     * @return list<int>
     */
    private function conflictingExistingProductIds(string $matchKey, array $stagedRecordIds): array
    {
        [$field, $value] = explode(':', $matchKey, 2);

        if ($field === 'external_id') {
            return [];
        }

        $record = StagedImportRecord::query()->find($stagedRecordIds[0]);
        $externalId = ProductIdentity::normalize($record?->normalized_payload['external_id'] ?? null);
        $normalizedColumn = $field.'_normalized';

        return Product::query()
            ->where($normalizedColumn, $value)
            ->when($externalId !== null, fn ($query) => $query->where(fn ($query) => $query->whereNull('external_id_normalized')->orWhere('external_id_normalized', '!=', $externalId)))
            ->pluck('id')
            ->map(static fn (mixed $id): int => (int) $id)
            ->all();
    }

    private function normalizeHeader(string $header): string
    {
        return mb_strtolower(trim(preg_replace('/^\xEF\xBB\xBF/', '', $header) ?? $header));
    }
}
