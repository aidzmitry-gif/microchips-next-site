<?php

namespace App\Console\Commands;

use App\Models\CatalogIdentityCandidate;
use Illuminate\Console\Command;
use RuntimeException;

class ExportApprovedIdentityCandidates extends Command
{
    protected $signature = 'catalog:export-approved-identities
                            {output : Output CSV path for catalog:stage-1c}
                            {--batch=rb-initial-50 : Review batch to export ("all" exports every batch)}
                            {--candidate-ids= : Comma-separated approved candidate IDs for a non-overlapping delta export}';

    protected $description = 'Export human-approved identity candidates to staging CSV without staging or publishing them';

    private const ALL_BATCHES = 'all';

    public function handle(): int
    {
        $batch = trim((string) $this->option('batch'));
        $candidateIds = $this->candidateIds((string) $this->option('candidate-ids'));
        $exportAll = $batch === '' || strcasecmp($batch, self::ALL_BATCHES) === 0;

        $query = CatalogIdentityCandidate::query()
            ->with('oneCItem')
            ->where('review_status', 'approved_for_staging');

        if ($candidateIds !== []) {
            $query->whereIn('id', $candidateIds);
        } elseif (! $exportAll) {
            $query->where('review_batch', $batch);
        }

        $rows = $query->orderBy('review_batch')->orderBy('review_priority')->get();

        // Guard against the silent-loss defect: if a specific batch was requested,
        // warn loudly when approved candidates exist in OTHER batches that this
        // filter just excluded. Losing 48% of a review pass without a warning is
        // worse than a noisy command, so this check runs even when $rows is empty.
        if ($candidateIds === [] && ! $exportAll) {
            $otherApprovedByBatch = CatalogIdentityCandidate::query()
                ->where('review_status', 'approved_for_staging')
                ->where('review_batch', '!=', $batch)
                ->selectRaw('review_batch, count(*) as approved_count')
                ->groupBy('review_batch')
                ->orderBy('review_batch')
                ->get();

            if ($otherApprovedByBatch->isNotEmpty()) {
                $totalOther = (int) $otherApprovedByBatch->sum('approved_count');
                $summary = $otherApprovedByBatch
                    ->map(static fn ($row) => "{$row->review_batch} ({$row->approved_count})")
                    ->implode(', ');
                $this->warn(
                    "Warning: {$totalOther} approved candidate(s) in other batch(es) were NOT exported: "
                    .$summary
                    .'. Re-run with --batch=all to export every approved candidate.'
                );
            }
        }

        if ($rows->isEmpty()) {
            $this->warn('No approved candidates found; no file was written.');

            return self::SUCCESS;
        }

        if ($candidateIds !== [] && $rows->pluck('id')->sort()->values()->all() !== $candidateIds) {
            throw new RuntimeException('A requested candidate is not approved_for_staging; delta export was stopped.');
        }

        $output = (string) $this->argument('output');
        $directory = dirname($output);
        if (! is_dir($directory) && ! mkdir($directory, 0777, true) && ! is_dir($directory)) {
            throw new RuntimeException("Unable to create {$directory}.");
        }

        $handle = fopen($output, 'wb');
        if ($handle === false) {
            throw new RuntimeException("Unable to create {$output}.");
        }

        try {
            fputcsv($handle, ['external_id', 'name', 'sku', 'mpn', 'manufacturer', 'review_batch'], ';', '"', '');
            foreach ($rows as $candidate) {
                fputcsv($handle, [
                    $candidate->oneCItem->external_id,
                    $candidate->oneCItem->name,
                    $candidate->confirmed_sku,
                    $candidate->confirmed_mpn,
                    $candidate->confirmed_manufacturer,
                    $candidate->review_batch,
                ], ';', '"', '');
            }
        } finally {
            fclose($handle);
        }

        $scope = $candidateIds !== [] ? 'explicit candidate delta' : ($exportAll ? 'all batches' : "batch \"{$batch}\"");
        $this->info("Exported {$rows->count()} approved candidates from {$scope}. No staging or publication was performed.");

        return self::SUCCESS;
    }

    /** @return list<int> */
    private function candidateIds(string $value): array
    {
        if (trim($value) === '') {
            return [];
        }

        $ids = array_values(array_unique(array_map('intval', array_filter(explode(',', $value), fn (string $id): bool => ctype_digit(trim($id)) && (int) $id > 0))));
        if ($ids === [] || count($ids) !== count(array_filter(explode(',', $value), fn (string $id): bool => trim($id) !== ''))) {
            throw new RuntimeException('candidate-ids must be a comma-separated list of positive integers.');
        }
        sort($ids);

        return $ids;
    }
}
