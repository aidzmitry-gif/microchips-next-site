<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Models\CatalogIdentityCandidate;
use App\Models\ImportRun;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\StagedImportRecord;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Storage;
use Illuminate\Validation\Rule;

class LegacyCatalogPreviewController extends Controller
{
    private const VISIBLE_STATUSES = [
        'strict_mapped_evidence',
        'candidate_mapped_evidence',
        'candidate_duplicate_group',
        'hold_missing_1c_identity',
        'hold_missing_rb_site_product',
    ];

    private const ALL_STATUSES = [
        ...self::VISIBLE_STATUSES,
        'scope_excluded_electronics',
        'excluded_inactive_legacy',
    ];

    public function index(Request $request, string $site): JsonResponse
    {
        $validated = $request->validate([
            'q' => ['nullable', 'string', 'max:100'],
            'category' => ['nullable', 'string', 'max:500'],
            'status' => ['nullable', 'string', Rule::in(self::VISIBLE_STATUSES)],
            'sort' => ['nullable', 'string', Rule::in(['legacy_id', 'name_asc', 'name_desc'])],
            'per_page' => ['nullable', 'integer', 'min:1', 'max:100'],
            'page' => ['nullable', 'integer', 'min:1'],
        ]);

        $siteModel = $this->previewSite($site);
        $run = $this->latestSnapshot($siteModel);
        $allRecords = $this->snapshotRecords($run);
        $records = $allRecords->whereIn('payload.transfer_status', self::VISIBLE_STATUSES)->values();

        if (($validated['status'] ?? null) !== null) {
            $records = $records->where('payload.transfer_status', $validated['status'])->values();
        }

        $category = $this->normalizeCategoryPath($validated['category'] ?? null);
        if ($category !== null) {
            $records = $records
                ->filter(fn (StagedImportRecord $record): bool => $this->recordBelongsToCategory($record, $category))
                ->values();
        }

        $search = mb_strtolower(trim($validated['q'] ?? ''));
        if ($search !== '') {
            $records = $records->filter(function (StagedImportRecord $record) use ($search): bool {
                $payload = $record->payload ?? [];
                $haystack = mb_strtolower(implode(' ', [
                    $payload['legacy_element_id'] ?? '',
                    $payload['legacy_name'] ?? '',
                    $payload['one_c_external_id'] ?? '',
                    $payload['one_c_name'] ?? '',
                    $payload['one_c_article'] ?? '',
                    $payload['legacy_primary_section_path'] ?? '',
                ]));

                return str_contains($haystack, $search);
            })->values();
        }

        $records = match ($validated['sort'] ?? 'legacy_id') {
            'name_asc' => $records->sortBy(fn (StagedImportRecord $record): string => mb_strtolower((string) data_get($record->payload, 'legacy_name'))),
            'name_desc' => $records->sortByDesc(fn (StagedImportRecord $record): string => mb_strtolower((string) data_get($record->payload, 'legacy_name'))),
            default => $records->sortBy(fn (StagedImportRecord $record): int => (int) data_get($record->payload, 'legacy_element_id')),
        };

        $page = (int) ($validated['page'] ?? 1);
        $perPage = (int) ($validated['per_page'] ?? 24);
        $total = $records->count();
        $lastPage = max(1, (int) ceil($total / $perPage));
        $page = min($page, $lastPage);
        $mediaIds = $this->availableMediaIds();
        $identityReviews = $this->identityReviews($siteModel);
        $items = $records->forPage($page, $perPage)
            ->map(fn (StagedImportRecord $record): array => $this->productPayload($record, $siteModel, $mediaIds, $identityReviews, false))
            ->values();

        return $this->previewJson([
            'data' => $items,
            'meta' => [
                'snapshot_run_id' => $run->id,
                'current_page' => $page,
                'last_page' => $lastPage,
                'per_page' => $perPage,
                'total' => $total,
                'snapshot_total' => $allRecords->count(),
                'visible_scope_total' => $allRecords->whereIn('payload.transfer_status', self::VISIBLE_STATUSES)->count(),
                'excluded_total' => $allRecords->whereIn('payload.transfer_status', [
                    'scope_excluded_electronics',
                    'excluded_inactive_legacy',
                ])->count(),
                'status_counts' => $allRecords
                    ->countBy(fn (StagedImportRecord $record): string => (string) data_get($record->payload, 'transfer_status'))
                    ->sortKeys(),
                'filters' => [
                    'q' => $validated['q'] ?? null,
                    'category' => $category,
                    'status' => $validated['status'] ?? null,
                    'sort' => $validated['sort'] ?? 'legacy_id',
                ],
            ],
        ]);
    }

    public function categories(string $site): JsonResponse
    {
        $siteModel = $this->previewSite($site);
        $run = $this->latestSnapshot($siteModel);
        $records = $this->snapshotRecords($run)
            ->whereIn('payload.transfer_status', self::VISIBLE_STATUSES)
            ->values();
        $categories = SiteCategory::query()
            ->with('category')
            ->where('site_id', $siteModel->id)
            ->where('source', 'bitrix_sections')
            ->where('is_published', false)
            ->orderBy('sort_order')
            ->orderBy('id')
            ->get();
        $categoryCounts = [];
        foreach ($records as $record) {
            $recordCategories = [];
            foreach ($this->sectionPaths($record) as $path) {
                $segments = explode('/', $path);
                $prefix = '';
                foreach ($segments as $segment) {
                    $prefix = $prefix === '' ? $segment : $prefix.'/'.$segment;
                    $recordCategories[$prefix] = true;
                }
            }
            foreach (array_keys($recordCategories) as $path) {
                $categoryCounts[$path] = ($categoryCounts[$path] ?? 0) + 1;
            }
        }
        $byCanonicalId = $categories->keyBy('category_id');
        $children = [];
        $roots = [];

        foreach ($categories as $category) {
            $parentSiteCategory = $category->category?->parent_id === null
                ? null
                : $byCanonicalId->get($category->category->parent_id);
            if ($parentSiteCategory === null) {
                $roots[] = $category;
            } else {
                $children[$parentSiteCategory->id][] = $category;
            }
        }

        $build = function (SiteCategory $category) use (&$build, $children, $categoryCounts): array {
            $sourcePath = $this->normalizeCategoryPath($category->slug) ?? '';
            $categoryChildren = collect($children[$category->id] ?? [])
                ->map(fn (SiteCategory $child): array => $build($child))
                ->values()
                ->all();

            return [
                'external_id' => $category->external_id,
                'name' => $category->name ?? $category->category?->name ?? $sourcePath,
                'source_path' => $sourcePath,
                'path' => $this->categoryPreviewPath($sourcePath),
                'count' => $categoryCounts[$sourcePath] ?? 0,
                'children' => $categoryChildren,
            ];
        };

        return $this->previewJson([
            'data' => collect($roots)->map(fn (SiteCategory $root): array => $build($root))->values(),
            'meta' => [
                'snapshot_run_id' => $run->id,
                'categories_total' => $categories->count(),
            ],
        ]);
    }

    public function show(string $site, int $legacyId): JsonResponse
    {
        $siteModel = $this->previewSite($site);
        $run = $this->latestSnapshot($siteModel);
        $record = StagedImportRecord::query()
            ->where('import_run_id', $run->id)
            ->where('entity_type', 'bitrix_legacy_product_evidence')
            ->where('external_id', 'bitrix:'.$legacyId)
            ->firstOrFail();
        abort_unless(in_array(data_get($record->payload, 'transfer_status'), self::VISIBLE_STATUSES, true), 404);

        return $this->previewJson([
            'data' => $this->productPayload($record, $siteModel, $this->availableMediaIds(), $this->identityReviews($siteModel), true),
            'meta' => ['snapshot_run_id' => $run->id],
        ]);
    }

    public function media(string $site, int $legacyId): mixed
    {
        $siteModel = $this->previewSite($site);
        $run = $this->latestSnapshot($siteModel);
        $record = StagedImportRecord::query()
            ->where('import_run_id', $run->id)
            ->where('entity_type', 'bitrix_legacy_product_evidence')
            ->where('external_id', 'bitrix:'.$legacyId)
            ->firstOrFail();
        abort_unless(in_array(data_get($record->payload, 'transfer_status'), self::VISIBLE_STATUSES, true), 404);

        $path = $this->availableMediaIds()[$legacyId] ?? null;
        abort_if($path === null || ! Storage::disk('public')->exists($path), 404);

        return Storage::disk('public')->response($path, null, [
            ...$this->previewHeaders(),
            'Content-Disposition' => 'inline',
        ]);
    }

    private function previewSite(string $key): Site
    {
        $site = Site::query()->where('key', $key)->where('is_active', true)->firstOrFail();
        abort_unless(str_ends_with(strtolower($site->domain), '.test'), 404);

        return $site;
    }

    private function latestSnapshot(Site $site): ImportRun
    {
        return ImportRun::query()
            ->where('source', 'bitrix_legacy_snapshot:'.$site->key)
            ->where('status', 'completed')
            ->latest('id')
            ->firstOrFail();
    }

    /** @return Collection<int, StagedImportRecord> */
    private function snapshotRecords(ImportRun $run): Collection
    {
        return StagedImportRecord::query()
            ->where('import_run_id', $run->id)
            ->where('entity_type', 'bitrix_legacy_product_evidence')
            ->orderBy('row_number')
            ->get();
    }

    /**
     * @param  array<int, string>  $mediaIds
     * @param  array<int, array<string, mixed>>  $identityReviews
     * @return array<string, mixed>
     */
    private function productPayload(StagedImportRecord $record, Site $site, array $mediaIds, array $identityReviews, bool $includeDetail): array
    {
        $payload = $record->payload ?? [];
        $legacyId = (int) ($payload['legacy_element_id'] ?? 0);
        $description = $this->plainText(
            (string) (($payload['detail_text'] ?? '') ?: ($payload['preview_text'] ?? '')),
            $includeDetail ? 20000 : 360,
        );

        return [
            'legacy_id' => $legacyId,
            'name' => (string) ($payload['legacy_name'] ?? ''),
            'preview_path' => '/legacy-preview/product/'.$legacyId,
            'legacy_url_candidate' => $payload['legacy_url_candidate'] ?? null,
            'primary_section_path' => $payload['legacy_primary_section_path'] ?? null,
            'matched_section_paths' => $this->sectionPaths($record),
            'description' => $description,
            'one_c' => [
                'external_id' => $payload['one_c_external_id'] ?: null,
                'name' => $payload['one_c_name'] ?: null,
                'article' => $payload['one_c_article'] ?: null,
            ],
            'identity_review' => $identityReviews[$legacyId] ?? null,
            'transfer_status' => $payload['transfer_status'] ?? null,
            'has_staging_image' => isset($mediaIds[$legacyId]),
            'image_path' => isset($mediaIds[$legacyId])
                ? '/api/v1/sites/'.$site->key.'/legacy-preview/media/'.$legacyId
                : null,
            'source_notice' => 'Legacy Bitrix snapshot evidence. Not published; facts require review before canonical use.',
        ];
    }

    /** @return array<int, array<string, mixed>> */
    private function identityReviews(Site $site): array
    {
        $run = ImportRun::query()
            ->where('source', 'bitrix_identity_review_decisions:'.$site->key)
            ->where('status', 'completed')
            ->latest('id')
            ->first();
        if ($run === null) {
            return [];
        }

        $records = StagedImportRecord::query()
            ->where('import_run_id', $run->id)
            ->where('entity_type', 'bitrix_identity_review_decision')
            ->get();
        $legacyIds = $records
            ->map(fn (StagedImportRecord $record): string => (string) ($record->payload['legacy_element_id'] ?? ''))
            ->filter()
            ->values();
        $confirmed = CatalogIdentityCandidate::query()
            ->with('oneCItem')
            ->where('legacy_source', 'bitrix')
            ->where('review_status', 'same_identity_confirmed')
            ->whereIn('legacy_id', $legacyIds)
            ->get()
            ->keyBy('legacy_id');

        $result = [];
        foreach ($records as $record) {
            $payload = $record->payload ?? [];
            $legacyId = (int) ($payload['legacy_element_id'] ?? 0);
            $oneCExternalId = (string) ($payload['one_c_external_id'] ?? '');
            $decision = (string) ($payload['decision'] ?? '');
            $candidate = $confirmed->get((string) $legacyId);
            $isConfirmed = $decision === 'same_identity'
                && $candidate !== null
                && $candidate->oneCItem?->external_id === $oneCExternalId;
            $result[$legacyId] = [
                'decision' => $decision,
                'state' => match (true) {
                    $isConfirmed => 'confirmed',
                    $decision === 'hold' => 'hold',
                    $decision === 'different_product_false_mapping' => 'rejected_mapping',
                    default => 'invalid_evidence',
                },
                'canonical_external_id' => $isConfirmed ? $oneCExternalId : null,
                'reason' => (string) ($payload['reason'] ?? ''),
            ];
        }

        return $result;
    }

    /** @return list<string> */
    private function sectionPaths(StagedImportRecord $record): array
    {
        $payload = $record->payload ?? [];
        $paths = preg_split('/\s*\|\s*/u', (string) ($payload['legacy_matched_section_paths'] ?? ''), -1, PREG_SPLIT_NO_EMPTY) ?: [];
        $primary = trim((string) ($payload['legacy_primary_section_path'] ?? ''));
        if ($primary !== '') {
            $paths[] = $primary;
        }

        return collect($paths)
            ->map(fn (string $path): string => $this->normalizeCategoryPath($path) ?? '')
            ->filter()
            ->unique()
            ->values()
            ->all();
    }

    private function recordBelongsToCategory(StagedImportRecord $record, string $category): bool
    {
        foreach ($this->sectionPaths($record) as $path) {
            if ($path === $category || str_starts_with($path, $category.'/')) {
                return true;
            }
        }

        return false;
    }

    private function normalizeCategoryPath(?string $path): ?string
    {
        $path = trim((string) $path, " \t\n\r\0\x0B/");
        if ($path === '') {
            return null;
        }
        if (str_starts_with($path, 'catalog/')) {
            $path = substr($path, strlen('catalog/'));
        }
        abort_if(str_contains($path, '..') || str_contains($path, '\\'), 422);

        return trim($path, '/');
    }

    private function categoryPreviewPath(string $sourcePath): string
    {
        return '/legacy-preview/catalog/'.collect(explode('/', $sourcePath))
            ->map(fn (string $part): string => rawurlencode($part))
            ->implode('/');
    }

    private function plainText(string $html, int $maxLength): string
    {
        $html = preg_replace('#<(script|style)[^>]*>.*?</\1>#is', ' ', $html) ?? '';
        $html = preg_replace('#<(br|/p|/li|/h[1-6])\b[^>]*>#i', ' ', $html) ?? $html;
        $text = html_entity_decode(strip_tags($html), ENT_QUOTES | ENT_HTML5, 'UTF-8');
        $text = preg_replace('/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/u', ' ', $text) ?? '';
        $text = preg_replace('/\s+/u', ' ', $text) ?? '';

        return trim(mb_substr($text, 0, $maxLength));
    }

    /** @return array<int, string> */
    private function availableMediaIds(): array
    {
        $result = [];
        foreach (Storage::disk('public')->files('legacy-staging/rb') as $path) {
            if (preg_match('#^legacy-staging/rb/bitrix-(\d+)-\d+\.(?:jpe?g|png|webp|gif)$#i', $path, $match) === 1) {
                $result[(int) $match[1]] = $path;
            }
        }

        return $result;
    }

    /** @param array<string, mixed> $payload */
    private function previewJson(array $payload): JsonResponse
    {
        return response()->json($payload)->withHeaders($this->previewHeaders());
    }

    /** @return array<string, string> */
    private function previewHeaders(): array
    {
        return [
            'Cache-Control' => 'private, no-store, max-age=0',
            'X-Robots-Tag' => 'noindex, nofollow, noarchive',
        ];
    }
}
