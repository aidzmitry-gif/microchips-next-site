<?php

namespace App\Console\Commands;

use App\Models\Site;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class AdoptBitrixExactPreviewDescriptions extends Command
{
    private const SOURCE_KIND = 'legacy_bitrix_exact_element_preview';

    protected $signature = 'catalog:adopt-bitrix-exact-preview-descriptions
                            {site : Site key}
                            {--source-run= : Pinned full Bitrix materialization source run}
                            {--snapshot-run= : Pinned detailed Bitrix snapshot run}
                            {--batch-size=500 : Maximum descriptions to attach in one cycle}
                            {--apply : Persist legacy preview descriptions; default is dry-run}';

    protected $description = 'Attach sanitized company-owned legacy text to the same namespaced Bitrix product without treating it as manufacturer-verified';

    public function handle(): int
    {
        try {
            $site = Site::query()->where('key', trim((string) $this->argument('site')))->sole();
            $sourceRunId = (int) $this->option('source-run');
            $snapshotRunId = (int) $this->option('snapshot-run');
            $batchSize = (int) $this->option('batch-size');
            if ($sourceRunId < 1 || $snapshotRunId < 1 || $batchSize < 1 || $batchSize > 1000) {
                throw new RuntimeException('Source/snapshot runs and a batch size between 1 and 1000 are required.');
            }
            $this->assertSnapshot($site->key, $snapshotRunId);

            $rows = DB::table('catalog_draft_materializations as m')
                ->join('staged_import_records as full', 'full.id', '=', 'm.staged_import_record_id')
                ->join('staged_import_records as detail', function ($join) use ($snapshotRunId): void {
                    $join->on('detail.external_id', '=', 'm.source_external_id')
                        ->where('detail.import_run_id', '=', $snapshotRunId)
                        ->where('detail.entity_type', '=', 'bitrix_legacy_product_evidence');
                })
                ->join('site_products as sp', 'sp.id', '=', 'm.site_product_id')
                ->join('products as p', 'p.id', '=', 'm.product_id')
                ->join('site_urls as u', function ($join) use ($site): void {
                    $join->on('u.target_id', '=', 'sp.id')
                        ->where('u.site_id', '=', $site->id)
                        ->where('u.target_type', '=', 'product')
                        ->where('u.is_indexable', '=', false);
                })
                ->where('m.site_id', $site->id)
                ->where('m.source_import_run_id', $sourceRunId)
                ->where('full.normalized_payload->transfer_status', 'legacy_only_draft_candidate')
                ->where('sp.is_published', true)
                ->where(function ($query): void {
                    $query->whereNull('p.short_description')->orWhereRaw("btrim(p.short_description) = ''");
                })
                ->whereNotExists(function ($query): void {
                    $query->selectRaw('1')->from('product_description_drafts as d')
                        ->whereColumn('d.product_id', 'p.id')
                        ->where('d.source_kind', self::SOURCE_KIND);
                })
                ->orderBy('detail.row_number')
                ->get([
                    'p.id as product_id', 'p.name', 'detail.id as detail_record_id',
                    'detail.payload as detail_payload', 'full.payload as full_payload',
                ])
                ->map(function ($row): ?object {
                    $detail = json_decode((string) $row->detail_payload, true, 512, JSON_THROW_ON_ERROR);
                    $full = json_decode((string) $row->full_payload, true, 512, JSON_THROW_ON_ERROR);
                    $content = $this->plainText((string) (($detail['detail_text'] ?? '') ?: ($detail['preview_text'] ?? '')));
                    if ($content === '') {
                        return null;
                    }
                    $row->content = $content;
                    $row->legacy_url = (string) ($full['legacy_url'] ?? '');

                    return $row;
                })
                ->filter()
                ->values();

            $selected = $rows->take($batchSize);
            $summary = [
                'mode' => $this->option('apply') ? 'apply' : 'dry_run',
                'source_run_id' => $sourceRunId,
                'snapshot_run_id' => $snapshotRunId,
                'eligible_missing_preview_descriptions' => $rows->count(),
                'selected_batch' => $selected->count(),
                'remaining_after' => $rows->count() - $selected->count(),
                'manufacturer_verified_descriptions_created' => 0,
                'indexable_pages_changed' => 0,
            ];

            if ($this->option('apply') && $selected->isNotEmpty()) {
                DB::transaction(function () use ($selected, $site): void {
                    $now = now();
                    $draftRows = [];
                    foreach ($selected as $row) {
                        DB::table('products')->where('id', $row->product_id)->update([
                            'short_description' => $row->content,
                            'updated_at' => $now,
                        ]);
                        $draftRows[] = [
                            'product_id' => $row->product_id,
                            'staged_import_record_id' => $row->detail_record_id,
                            'locale' => $site->default_locale,
                            'title' => $row->name,
                            'content' => $row->content,
                            'verified_fields' => json_encode([], JSON_THROW_ON_ERROR),
                            'source_urls' => json_encode(array_values(array_filter([$row->legacy_url])), JSON_THROW_ON_ERROR),
                            'source_kind' => self::SOURCE_KIND,
                            'source_tier' => 'company_owned_legacy_preview',
                            'source_publisher' => 'microchips.by legacy Bitrix',
                            'manufacturer_primary' => null,
                            'identity_scope' => 'exact_legacy_element',
                            'source_checked_at' => now()->toDateString(),
                            'status' => 'legacy_preview_applied',
                            'rejection_reason' => null,
                            'submitted_by' => null,
                            'submitted_at' => null,
                            'created_at' => $now,
                            'updated_at' => $now,
                        ];
                    }
                    DB::table('product_description_drafts')->insert($draftRows);
                });
            }

            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    private function assertSnapshot(string $siteKey, int $runId): void
    {
        $run = DB::table('import_runs')->where('id', $runId)->first();
        if ($run === null || $run->source !== 'bitrix_legacy_snapshot:'.$siteKey || $run->status !== 'completed' || (int) $run->failed_records !== 0) {
            throw new RuntimeException('Detailed Bitrix snapshot is not a completed zero-failure run for this site.');
        }
    }

    private function plainText(string $html): string
    {
        $html = preg_replace('#<(script|style)[^>]*>.*?</\1>#is', ' ', $html) ?? '';
        $html = preg_replace('#<(br|/p|/li|/h[1-6]|/tr|/td)\b[^>]*>#i', ' ', $html) ?? $html;
        $text = html_entity_decode(strip_tags($html), ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $text = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', ' ', $text) ?? '';
        $text = preg_replace('/\s+/u', ' ', $text) ?? '';

        return trim(mb_substr($text, 0, 4000));
    }
}
