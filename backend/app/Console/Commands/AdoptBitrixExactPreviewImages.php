<?php

namespace App\Console\Commands;

use App\Events\SiteContentChanged;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;
use RuntimeException;
use Throwable;

class AdoptBitrixExactPreviewImages extends Command
{
    private const SOURCE_KIND = 'legacy_bitrix_exact_element_preview';

    protected $signature = 'media:adopt-bitrix-exact-preview-images
                            {site : Site key}
                            {--source-run= : Pinned full Bitrix staging run ID}
                            {--batch-size=500 : Maximum images to attach in one cycle}
                            {--apply : Persist the preview image links; default is dry-run}';

    protected $description = 'Attach company-owned legacy images to the same namespaced Bitrix product for noindex preview use';

    public function handle(): int
    {
        try {
            $site = Site::query()->where('key', trim((string) $this->argument('site')))->sole();
            $runId = (int) $this->option('source-run');
            $batchSize = (int) $this->option('batch-size');
            if ($runId < 1 || $batchSize < 1 || $batchSize > 1000) {
                throw new RuntimeException('A source run and batch size between 1 and 1000 are required.');
            }

            $assets = $this->assetsByLegacyId();
            $rows = DB::table('catalog_draft_materializations as m')
                ->join('staged_import_records as r', 'r.id', '=', 'm.staged_import_record_id')
                ->join('site_products as sp', 'sp.id', '=', 'm.site_product_id')
                ->join('products as p', 'p.id', '=', 'm.product_id')
                ->join('site_urls as u', function ($join) use ($site): void {
                    $join->on('u.target_id', '=', 'sp.id')
                        ->where('u.site_id', '=', $site->id)
                        ->where('u.target_type', '=', 'product')
                        ->where('u.is_indexable', '=', false);
                })
                ->where('m.site_id', $site->id)
                ->where('m.source_import_run_id', $runId)
                ->whereIn('r.normalized_payload->transfer_status', [
                    'legacy_only_draft_candidate',
                    'hold_duplicate_candidate',
                    'hold_linked_identity_candidate',
                    'hold_one_c_collision',
                    'existing_one_c_exact_link',
                ])
                ->where('sp.is_published', true)
                ->where('sp.availability', 'on_request')
                ->get(['m.product_id', 'm.source_external_id', 'p.name']);

            $existing = ProductMedia::query()
                ->whereIn('product_id', $rows->pluck('product_id'))
                ->where('source_kind', self::SOURCE_KIND)
                ->pluck('product_id')
                ->flip();
            $eligible = $rows->filter(function ($row) use ($assets, $existing): bool {
                $legacyId = $this->legacyId($row->source_external_id);

                return isset($assets[$legacyId]) && ! $existing->has($row->product_id);
            })->values();
            $selected = $eligible->take($batchSize);
            $summary = [
                'mode' => $this->option('apply') ? 'apply' : 'dry_run',
                'source_run_id' => $runId,
                'extracted_legacy_assets' => count($assets),
                'safe_published_products' => $rows->count(),
                'eligible_missing_preview_media' => $eligible->count(),
                'selected_batch' => $selected->count(),
                'remaining_after' => $eligible->count() - $selected->count(),
                'preview_images_created' => 0,
                'revalidation_batches' => 0,
                'visually_verified_images_created' => 0,
                'indexable_pages_changed' => 0,
            ];

            if ($this->option('apply') && $selected->isNotEmpty()) {
                DB::transaction(function () use ($selected, $assets): void {
                    foreach ($selected as $row) {
                        $legacyId = $this->legacyId($row->source_external_id);
                        $asset = $assets[$legacyId];
                        ProductMedia::query()->create([
                            'product_id' => $row->product_id,
                            'kind' => 'image',
                            'role' => 'primary',
                            'source_page_url' => 'bitrix-backup://element/'.$legacyId,
                            'source_asset_url' => 'bitrix-backup://file/'.$asset['file_id'],
                            'source_kind' => self::SOURCE_KIND,
                            'rights_basis' => 'Company-owned Microchips legacy Bitrix upload backup.',
                            'storage_path' => $asset['path'],
                            'content_sha256' => $asset['sha256'],
                            'verification_status' => ProductMedia::STATUS_LEGACY_EXACT_PREVIEW,
                            'verification_note' => 'Exact PREVIEW/DETAIL_PICTURE relation from the same Bitrix element; raster integrity checked; visual model identity still requires review.',
                            'verified_at' => null,
                            'is_published' => true,
                            'sort_order' => 0,
                        ]);
                    }
                });
                $summary['preview_images_created'] = $selected->count();
                $summary['revalidation_batches'] = $this->revalidateAffected($site, $selected->pluck('product_id')->all());
            }

            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /** @return array<int, array{path: string, file_id: int, sha256: string}> */
    private function assetsByLegacyId(): array
    {
        $result = [];
        foreach (Storage::disk('public')->files('legacy-staging/rb') as $path) {
            if (preg_match('#^legacy-staging/rb/bitrix-(\d+)-(\d+)\.(jpe?g|png|webp|gif)$#i', $path, $match) !== 1) {
                continue;
            }
            $absolute = Storage::disk('public')->path($path);
            $size = filesize($absolute);
            $dimensions = @getimagesize($absolute);
            if ($size === false || $size < 1 || $size > 25 * 1024 * 1024 || $dimensions === false) {
                continue;
            }
            $legacyId = (int) $match[1];
            if (isset($result[$legacyId])) {
                throw new RuntimeException("Legacy element {$legacyId} has more than one staged primary image.");
            }
            $hash = hash_file('sha256', $absolute);
            if (! is_string($hash)) {
                throw new RuntimeException("Cannot hash staged image {$path}.");
            }
            $result[$legacyId] = ['path' => $path, 'file_id' => (int) $match[2], 'sha256' => $hash];
        }

        return $result;
    }

    private function legacyId(string $externalId): int
    {
        if (preg_match('/^bitrix:(\d+)$/', $externalId, $match) !== 1) {
            throw new RuntimeException("Unexpected Bitrix external ID {$externalId}.");
        }

        return (int) $match[1];
    }

    /** @param list<int|string> $productIds */
    private function revalidateAffected(Site $site, array $productIds): int
    {
        $siteProductIds = SiteProduct::query()
            ->where('site_id', $site->id)
            ->whereIn('product_id', array_values(array_unique(array_map('intval', $productIds))))
            ->pluck('id');
        $paths = SiteUrl::query()
            ->where('site_id', $site->id)
            ->where('target_type', 'product')
            ->whereIn('target_id', $siteProductIds)
            ->pluck('path');
        $categoryIds = DB::table('site_category_product')
            ->where('site_id', $site->id)
            ->whereIn('site_product_id', $siteProductIds)
            ->pluck('site_category_id')
            ->map(static fn (mixed $id): int => (int) $id)
            ->unique()
            ->all();
        $paths = $paths
            ->merge(SiteCategory::revalidationPaths($site->id, $categoryIds))
            ->push('/catalog')
            ->filter(static fn (mixed $path): bool => is_string($path) && str_starts_with($path, '/'))
            ->unique()
            ->values();

        $batches = 0;
        foreach ($paths->chunk(100) as $batch) {
            SiteContentChanged::dispatch($site, $batch->values()->all());
            $batches++;
        }

        return $batches;
    }
}
