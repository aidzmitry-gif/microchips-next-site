<?php

namespace App\Console\Commands;

use App\Models\CatalogIdentityCandidate;
use Illuminate\Console\Command;
use RuntimeException;

class ExportApprovedIdentityCandidates extends Command
{
    protected $signature = 'catalog:export-approved-identities
                            {output : Output CSV path for catalog:stage-1c}
                            {--batch=rb-initial-50 : Review batch to export}';

    protected $description = 'Export human-approved identity candidates to staging CSV without staging or publishing them';

    public function handle(): int
    {
        $batch = trim((string) $this->option('batch'));
        $rows = CatalogIdentityCandidate::query()
            ->with('oneCItem')
            ->where('review_batch', $batch)
            ->where('review_status', 'approved_for_staging')
            ->orderBy('review_priority')
            ->get();

        if ($rows->isEmpty()) {
            $this->warn('No approved candidates found; no file was written.');

            return self::SUCCESS;
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
            fputcsv($handle, ['external_id', 'name', 'sku', 'mpn', 'manufacturer'], ';', '"', '');
            foreach ($rows as $candidate) {
                fputcsv($handle, [
                    $candidate->oneCItem->external_id,
                    $candidate->oneCItem->name,
                    $candidate->confirmed_sku,
                    $candidate->confirmed_mpn,
                    $candidate->confirmed_manufacturer,
                ], ';', '"', '');
            }
        } finally {
            fclose($handle);
        }

        $this->info("Exported {$rows->count()} approved candidates. No staging or publication was performed.");

        return self::SUCCESS;
    }
}
