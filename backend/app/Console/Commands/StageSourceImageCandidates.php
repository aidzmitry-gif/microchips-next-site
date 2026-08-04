<?php

namespace App\Console\Commands;

use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/** Records remote manufacturer image candidates without granting reuse rights. */
class StageSourceImageCandidates extends Command
{
    protected $signature = 'media:stage-source-image-candidates
                            {site : Site key}
                            {file : JSON source-image candidate manifest}
                            {--apply : Persist pending candidates; default is dry-run}';

    protected $description = 'Stage official image candidates as non-public pending records; never downloads or publishes them';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $summary = $this->stage($site, (string) $this->argument('file'), (bool) $this->option('apply'));
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /** @return array{mode: string, records: int, created: int, unchanged: int, published: int} */
    private function stage(Site $site, string $file, bool $apply): array
    {
        $manifest = $this->manifest($file);
        if (($manifest['locale'] ?? null) !== $site->default_locale || ! is_array($manifest['products'] ?? null) || $manifest['products'] === []) {
            throw new RuntimeException('Manifest locale must match the site default locale and contain products.');
        }

        $summary = ['mode' => $apply ? 'apply' : 'dry_run', 'records' => count($manifest['products']), 'created' => 0, 'unchanged' => 0, 'published' => 0];
        $seen = [];
        $work = function () use ($site, $manifest, &$summary, &$seen): void {
            foreach ($manifest['products'] as $index => $row) {
                if (! is_array($row)) {
                    throw new RuntimeException("Manifest row {$index} must be an object.");
                }
                foreach (['external_id', 'source_page_url', 'source_asset_url', 'source_kind', 'verification_note'] as $field) {
                    if (! is_string($row[$field] ?? null) || blank(trim($row[$field]))) {
                        throw new RuntimeException("Manifest row {$index} requires {$field}.");
                    }
                }
                $externalId = trim($row['external_id']);
                $assetUrl = trim($row['source_asset_url']);
                if (! filter_var(trim($row['source_page_url']), FILTER_VALIDATE_URL) || ! filter_var($assetUrl, FILTER_VALIDATE_URL)) {
                    throw new RuntimeException("Manifest row {$index} requires absolute source URLs.");
                }
                if (isset($seen[$externalId][$assetUrl])) {
                    throw new RuntimeException("Manifest repeats the same product image candidate for {$externalId}.");
                }
                $seen[$externalId][$assetUrl] = true;

                $product = Product::query()->where('external_id', $externalId)->first();
                if ($product === null || ! $product->sites()->where('site_id', $site->id)->exists()) {
                    throw new RuntimeException("Product {$externalId} is not assigned to site {$site->key}.");
                }
                $candidate = ProductMedia::query()->firstOrCreate(
                    ['product_id' => $product->id, 'content_sha256' => null, 'source_asset_url' => $assetUrl],
                    [
                        'kind' => 'image',
                        'role' => 'primary',
                        'source_page_url' => trim($row['source_page_url']),
                        'source_kind' => trim($row['source_kind']),
                        'verification_status' => 'pending',
                        'verification_note' => trim($row['verification_note']),
                        'is_published' => false,
                    ],
                );
                if ($candidate->wasRecentlyCreated) {
                    $summary['created']++;
                } else {
                    if ($candidate->is_published || $candidate->verification_status === 'verified' || filled($candidate->storage_path) || filled($candidate->rights_basis)) {
                        throw new RuntimeException("Candidate {$externalId} has already advanced beyond the pending media gate.");
                    }
                    $summary['unchanged']++;
                }
            }
        };

        if ($apply) {
            DB::transaction($work);
        } else {
            DB::beginTransaction();
            try {
                $work();
            } finally {
                DB::rollBack();
            }
        }

        return $summary;
    }

    /** @return array<string, mixed> */
    private function manifest(string $file): array
    {
        if (! is_readable($file)) {
            throw new RuntimeException('Source image candidate manifest is not readable.');
        }
        try {
            $manifest = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $error) {
            throw new RuntimeException('Source image candidate manifest is not valid JSON.', previous: $error);
        }
        if (! is_array($manifest)) {
            throw new RuntimeException('Source image candidate manifest must be an object.');
        }

        return $manifest;
    }
}
