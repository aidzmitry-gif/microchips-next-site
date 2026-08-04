<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Models\Product;
use App\Models\ProductFamily;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
use App\Models\SiteUrl;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\Cache;
use Illuminate\Validation\ValidationException;

class CatalogController extends Controller
{
    /** Bump when facet extraction semantics change so deployed code never reuses stale Redis records. */
    private const FACET_SCHEMA_VERSION = 7;

    public function index(Request $request, string $site): JsonResponse
    {
        $validated = $request->validate([
            'q' => ['nullable', 'string', 'max:100'],
            'category' => ['nullable', 'string', 'max:255'],
            'locale' => ['nullable', 'string', 'max:20'],
            'sort' => ['nullable', 'string', 'in:name_asc,name_desc,price_asc,price_desc'],
            'manufacturer' => ['nullable', 'string', 'max:255'],
            'technology' => ['nullable', 'string', 'max:100'],
            'nominal_voltage' => ['nullable', 'string', 'max:100'],
            'capacity' => ['nullable', 'string', 'max:100'],
            'power' => ['nullable', 'string', 'max:100'],
            'input_voltage' => ['nullable', 'string', 'max:100'],
            'output_voltage' => ['nullable', 'string', 'max:100'],
            'input_current' => ['nullable', 'string', 'max:100'],
            'output_current' => ['nullable', 'string', 'max:100'],
            'phase' => ['nullable', 'string', 'max:100'],
            'topology' => ['nullable', 'string', 'max:100'],
            'device_type' => ['nullable', 'string', 'max:255'],
            'per_page' => ['nullable', 'integer', 'min:1', 'max:100'],
        ]);

        $siteModel = Site::query()->where('key', $site)->where('is_active', true)->firstOrFail();
        $locale = $this->requestedEnabledLocale($siteModel, $validated['locale'] ?? null);
        $query = SiteProduct::query()
            ->with([
                'product.media' => fn ($query) => $query->previewReady()->orderBy('sort_order')->orderBy('id'),
                'currentPriceEvidence',
            ])
            ->published()
            ->where('site_id', $siteModel->id)
            // A reviewed variant is selectable on its canonical family page;
            // it must not consume a second catalogue card, pagination slot or
            // crawlable product URL.
            ->whereDoesntHave('product.familyVariants', fn (Builder $variants) => $variants
                ->active()
                ->whereHas('family', fn (Builder $families) => $families
                    ->where('site_id', $siteModel->id)
                    ->where('status', ProductFamily::STATUS_VERIFIED)));

        $search = trim($validated['q'] ?? '');
        if ($search !== '') {
            $this->applySearch($query, $search, ($validated['sort'] ?? null) === null);
        }

        if (($validated['category'] ?? null) !== null) {
            $categoryIds = $this->categoryAndDescendantIds($siteModel, $validated['category']);
            $query->whereHas('categories', function (Builder $categories) use ($categoryIds, $siteModel): void {
                $categories
                    ->where('site_categories.site_id', $siteModel->id)
                    ->published()
                    ->whereIn('site_categories.id', $categoryIds);
            });
        }

        $powerFacetsEnabled = $this->powerFacetsEnabled($validated['category'] ?? null);
        $facetVersion = (int) Cache::get('catalog:facet-version:'.$siteModel->id, 1);
        $facetCacheKey = 'catalog:facet-records:'.hash('sha256', json_encode([
            'site_id' => $siteModel->id,
            'version' => $facetVersion,
            'schema' => self::FACET_SCHEMA_VERSION,
            'search' => $search,
            'category' => $validated['category'] ?? null,
            'power' => $powerFacetsEnabled,
        ], JSON_THROW_ON_ERROR));
        $facetRecords = collect(Cache::remember($facetCacheKey, now()->addMinutes(10), function () use ($query, $powerFacetsEnabled): array {
            return (clone $query)
                ->setEagerLoads([])
                ->with('product:id,manufacturer,technical_attributes')
                ->get(['site_products.id', 'site_products.product_id'])
                ->map(fn (SiteProduct $siteProduct): array => $this->facetRecord($siteProduct, $powerFacetsEnabled))
                ->all();
        }));
        $appliedFilters = $this->appliedFilters($validated, $powerFacetsEnabled);
        $priceSortEnabled = SiteProductPriceEvidence::query()
            ->where('site_id', $siteModel->id)
            ->where('is_current', true)
            ->whereIn('site_product_id', $facetRecords->pluck('id'))
            ->whereHas('siteProduct', fn (Builder $query) => $query->published()->whereNotNull('price'))
            ->exists();
        if (in_array($validated['sort'] ?? null, ['price_asc', 'price_desc'], true) && ! $priceSortEnabled) {
            throw ValidationException::withMessages([
                'sort' => ['Price sorting requires current source-backed prices in the selected catalogue scope.'],
            ]);
        }

        if (array_filter($appliedFilters, static fn (?string $value): bool => $value !== null) !== []) {
            $matchingIds = $facetRecords
                ->filter(fn (array $record): bool => $this->matchesFilters($record, $appliedFilters))
                ->pluck('id')
                ->all();
            $query->whereIn('site_products.id', $matchingIds);
        }

        $this->applySort($query, $validated['sort'] ?? null);

        $products = $query->paginate($validated['per_page'] ?? 24);
        $pathsByProductId = SiteUrl::query()
            ->where('site_id', $siteModel->id)
            ->where('target_type', 'product')
            ->where('locale', $locale)
            ->whereIn('target_id', $products->getCollection()->pluck('id'))
            ->pluck('path', 'target_id');

        return response()->json([
            'data' => $products->getCollection()->map(fn (SiteProduct $siteProduct) => [
                'slug' => $siteProduct->slug,
                'path' => $pathsByProductId->get($siteProduct->id),
                'name' => $siteProduct->product->name,
                'sku' => $siteProduct->product->sku,
                'mpn' => $siteProduct->product->mpn,
                'manufacturer' => $siteProduct->product->manufacturer,
                'summary_attributes' => $this->summaryAttributes($siteProduct->product, $powerFacetsEnabled),
                'availability' => $siteProduct->availability,
                'price' => $siteProduct->price,
                'price_observed_at' => $this->priceObservedAt($siteProduct, $siteModel->currency_code),
                'currency' => $siteModel->currency_code,
                'image_path' => $siteProduct->product->media->first()?->id === null ? null : '/api/v1/media/'.$siteProduct->product->media->first()->id,
            ])->values(),
            'meta' => [
                'current_page' => $products->currentPage(),
                'last_page' => $products->lastPage(),
                'total' => $products->total(),
                'sort' => $validated['sort'] ?? 'default',
                'price_sort_enabled' => $priceSortEnabled,
                'facets' => $this->facets($facetRecords, $powerFacetsEnabled, $appliedFilters),
                'applied_filters' => $appliedFilters,
            ],
        ]);
    }

    private function priceObservedAt(SiteProduct $siteProduct, string $currency): ?string
    {
        $evidence = $siteProduct->currentPriceEvidence;

        if ($siteProduct->price === null
            || $evidence === null
            || (string) $evidence->calculated_price !== (string) $siteProduct->price
            || $evidence->currency !== $currency) {
            return null;
        }

        return $evidence->observed_at?->toIso8601String();
    }

    private function applySearch(Builder $query, string $search, bool $rankResults): void
    {
        $operator = $query->getModel()->getConnection()->getDriverName() === 'pgsql' ? 'ilike' : 'like';
        $contains = "%{$search}%";
        $query->whereHas('product', function (Builder $products) use ($contains, $operator): void {
            $products->where('name', $operator, $contains)
                ->orWhere('sku', $operator, $contains)
                ->orWhere('mpn', $operator, $contains)
                ->orWhere('manufacturer', $operator, $contains);
        });

        if (! $rankResults) {
            return;
        }

        $needle = mb_strtolower($search);
        $prefix = $needle.'%';
        $containsNeedle = '%'.$needle.'%';
        $rank = Product::query()
            ->selectRaw(
                <<<'SQL'
CASE
    WHEN LOWER(COALESCE(products.sku, '')) = ? OR LOWER(COALESCE(products.mpn, '')) = ? THEN 0
    WHEN LOWER(products.name) = ? THEN 1
    WHEN LOWER(products.name) LIKE ? THEN 2
    WHEN LOWER(COALESCE(products.manufacturer, '')) = ? THEN 3
    WHEN LOWER(COALESCE(products.manufacturer, '')) LIKE ? THEN 4
    WHEN LOWER(products.name) LIKE ? THEN 5
    ELSE 6
END
SQL,
                [$needle, $needle, $needle, $prefix, $needle, $prefix, $containsNeedle],
            )
            ->whereColumn('products.id', 'site_products.product_id');
        $query->orderBy($rank);
    }

    /**
     * Catalogue sorting is intentionally allow-listed. Query parameters never
     * become raw SQL columns. Price sorting is enabled only after the caller
     * has confirmed current price evidence exists for this market.
     */
    private function applySort(Builder $query, ?string $sort): void
    {
        match ($sort) {
            'name_asc' => $query->orderBy(
                Product::query()->select('name')->whereColumn('products.id', 'site_products.product_id'),
                'asc',
            )->orderBy('site_products.id'),
            'name_desc' => $query->orderBy(
                Product::query()->select('name')->whereColumn('products.id', 'site_products.product_id'),
                'desc',
            )->orderBy('site_products.id'),
            'price_asc' => $query->orderByRaw('site_products.price IS NULL')
                ->orderBy('site_products.price')
                ->orderBy('site_products.id'),
            'price_desc' => $query->orderByRaw('site_products.price IS NULL')
                ->orderByDesc('site_products.price')
                ->orderBy('site_products.id'),
            // Preserve explicit merchandising order, then prefer cards with a
            // displayable local image. This keeps a large migrated category
            // from opening with an entire placeholder-only page merely because
            // older 1C SiteProduct rows have lower database IDs.
            default => $query->orderBy('site_products.sort_order')
                ->orderByDesc(ProductMedia::query()
                    // COUNT returns 0/1+ on both PostgreSQL and SQLite.
                    // A scalar 1/NULL subquery is not portable here because
                    // PostgreSQL sorts NULLS FIRST for DESC by default.
                    ->selectRaw('COUNT(*)')
                    ->whereColumn('product_media.product_id', 'site_products.product_id')
                    ->previewReady())
                ->orderBy('site_products.id'),
        };
    }

    /** @return array<string, int|string|null> */
    private function facetRecord(SiteProduct $siteProduct, bool $includePowerFacets): array
    {
        $values = $this->productFacetValues($siteProduct->product, $includePowerFacets);
        $values['capacity'] = $this->capacityBucket($values['capacity']);

        return [
            'id' => (int) $siteProduct->id,
            ...$values,
        ];
    }

    /** @return array<string, ?string> */
    private function productFacetValues(Product $product, bool $includePowerFacets = false): array
    {
        $attributes = is_array($product->technical_attributes) ? $product->technical_attributes : [];

        $values = [
            'manufacturer' => $this->normalizeManufacturer($product->manufacturer),
            'technology' => $this->normalizeTechnology($this->firstAttribute($attributes, ['Технология', 'chemistry'])),
            'nominal_voltage' => $this->normalizeNominalVoltage($this->firstAttribute($attributes, ['Номинальное напряжение', 'Напряжение'])),
            'capacity' => $this->normalizeCapacity($this->firstAttribute($attributes, [
                'Номинальная ёмкость',
                'Номинальная ёмкость C5',
                'Номинальная ёмкость C10',
                'Номинальная ёмкость (C10)',
                'Номинальная ёмкость (C20)',
                'Номинальная ёмкость C120',
                'Номинальная ёмкость (10 ч, 1,80 В/эл., 20 °C)',
                'Номинальная ёмкость (20 ч, 1,75 В/эл., 25 °C)',
                'Ёмкость',
            ])),
        ];

        if (! $includePowerFacets) {
            return $values;
        }

        return [
            ...$values,
            // Power-system facets are intentionally sourced only from explicit
            // technical attributes. Product names are never parsed into facts.
            'power' => $this->cleanFacetValue($this->firstAttribute($attributes, [
                'Активная мощность', 'Номинальная мощность', 'Выходная мощность', 'Полная мощность', 'Мощность',
                'active_power', 'rated_power', 'output_power', 'apparent_power', 'power',
            ])),
            'input_voltage' => $this->cleanFacetValue($this->firstAttribute($attributes, [
                'Входное напряжение', 'Диапазон входного напряжения', 'input_voltage', 'input_voltage_range',
            ])),
            'output_voltage' => $this->cleanFacetValue($this->firstAttribute($attributes, [
                'Выходное напряжение', 'Диапазон выходного напряжения', 'output_voltage', 'output_voltage_range',
            ])),
            'input_current' => $this->cleanFacetValue($this->firstAttribute($attributes, [
                'Входной ток', 'Максимальный входной ток', 'input_current', 'max_input_current',
            ])),
            'output_current' => $this->cleanFacetValue($this->firstAttribute($attributes, [
                'Выходной ток', 'Максимальный выходной ток', 'output_current', 'max_output_current',
            ])),
            'phase' => $this->cleanFacetValue($this->firstAttribute($attributes, [
                'Фазность', 'Количество фаз', 'phase', 'phases',
            ])),
            'topology' => $this->cleanFacetValue($this->firstAttribute($attributes, ['Топология', 'topology'])),
            'device_type' => $this->cleanFacetValue($this->firstAttribute($attributes, ['Тип устройства', 'Тип', 'device_type', 'type'])),
        ];
    }

    /** @param array<string, mixed> $attributes */
    private function firstAttribute(array $attributes, array $keys): mixed
    {
        foreach ($keys as $key) {
            if (array_key_exists($key, $attributes)
                && is_scalar($attributes[$key])
                && trim((string) $attributes[$key]) !== '') {
                return $attributes[$key];
            }
        }

        return null;
    }

    private function cleanFacetValue(mixed $value): ?string
    {
        if (! is_scalar($value)) {
            return null;
        }

        $clean = preg_replace('/\s+/u', ' ', trim((string) $value));

        return $clean === '' ? null : $clean;
    }

    private function normalizeTechnology(mixed $value): ?string
    {
        $clean = $this->cleanFacetValue($value);
        if ($clean === null) {
            return null;
        }

        $upper = mb_strtoupper($clean);

        return match (true) {
            str_contains($upper, 'LIFEPO4') || str_contains($upper, 'LFP') => 'LiFePO4',
            str_contains($upper, 'LI-POL') || str_contains($upper, 'LIPO') || str_contains($upper, 'ЛИТИЙ-ПОЛИМЕР') => 'Li-Pol',
            str_contains($upper, 'LI-ION') || str_contains($upper, 'LITHIUM-ION') || str_contains($upper, 'ЛИТИЙ-ИОН') => 'Li-ion',
            str_contains($upper, 'NI-CD') || str_contains($upper, 'NICD') || str_contains($upper, 'НИКЕЛЬ-КАДМИ') => 'Ni-Cd',
            str_contains($upper, 'NI-MH') || str_contains($upper, 'NIMH') || str_contains($upper, 'НИКЕЛЬ-МЕТАЛЛГИДРИД') => 'NiMH',
            str_contains($upper, 'NI-ZN') || str_contains($upper, 'NIZN') || str_contains($upper, 'НИКЕЛЬ-ЦИНК') => 'NiZn',
            preg_match('/(?:^|[^A-Z0-9])LTO(?:$|[^A-Z0-9])/u', $upper) === 1 || str_contains($upper, 'ЛИТИЙ-ТИТАНАТ') => 'LTO',
            str_contains($upper, 'AGM') => 'AGM',
            str_contains($upper, 'GEL') => 'GEL',
            str_contains($upper, 'VRLA') || str_contains($upper, 'КЛАПАН') => 'VRLA',
            str_contains($upper, 'LEAD-ACID') || str_contains($upper, 'СВИНЦОВ') => 'Свинцово-кислотная',
            str_contains($upper, 'ALKALINE') || str_contains($upper, 'ЩЕЛОЧН') => 'Щелочная',
            str_contains($upper, 'SILVER-ZINC') || str_contains($upper, 'СЕРЕБРЯНО-ЦИНК') => 'Серебряно-цинковая',
            str_contains($upper, 'ZINC-AIR') || str_contains($upper, 'ЦИНК-ВОЗДУШ') => 'Цинк-воздушная',
            // A legacy field named "Технология" also contains device types
            // (UPS battery modules, scanner/printer batteries and similar).
            // Unknown free text must not become a public facet or an SEO URL.
            default => null,
        };
    }

    private function normalizeManufacturer(mixed $value): ?string
    {
        $clean = $this->cleanFacetValue($value);
        if ($clean === null) {
            return null;
        }
        $upper = mb_strtoupper($clean);

        return match (true) {
            str_starts_with($upper, 'APC') => 'APC',
            str_starts_with($upper, 'CSB') => 'CSB',
            str_starts_with($upper, 'FIAMM') => 'FIAMM',
            str_starts_with($upper, 'LEOCH') => 'LEOCH',
            default => $clean,
        };
    }

    private function normalizeNominalVoltage(mixed $value): ?string
    {
        return $this->normalizeMeasuredFacet($value, '/(\d+(?:[.,]\d+)?)\s*(?:V|В)(?![A-Za-zА-Яа-я])/iu', 'V');
    }

    private function normalizeCapacity(mixed $value): ?string
    {
        return $this->normalizeMeasuredFacet($value, '/(\d+(?:[.,]\d+)?)\s*(?:A\s*[·∙⋅.]?\s*h|А\s*[·∙⋅.]?\s*ч)/iu', 'Ah');
    }

    private function normalizeMeasuredFacet(mixed $value, string $pattern, string $unit): ?string
    {
        $clean = $this->cleanFacetValue($value);
        if ($clean === null || preg_match($pattern, $clean, $match) !== 1) {
            return $clean;
        }
        $number = (float) str_replace(',', '.', $match[1]);
        $formatted = rtrim(rtrim(number_format($number, 3, '.', ''), '0'), '.');

        return $formatted.' '.$unit;
    }

    private function capacityBucket(mixed $value): ?string
    {
        $clean = $this->cleanFacetValue($value);
        $labels = ['До 5 Ah', '5–10 Ah', '10–20 Ah', '20–50 Ah', '50–100 Ah', '100–200 Ah', 'Более 200 Ah'];
        if ($clean === null || in_array($clean, $labels, true)) {
            return $clean;
        }
        $normalized = $this->normalizeCapacity($clean);
        if ($normalized === null || preg_match('/^(\d+(?:\.\d+)?) Ah$/', $normalized, $match) !== 1) {
            return null;
        }
        $capacity = (float) $match[1];

        return match (true) {
            $capacity <= 5 => 'До 5 Ah',
            $capacity <= 10 => '5–10 Ah',
            $capacity <= 20 => '10–20 Ah',
            $capacity <= 50 => '20–50 Ah',
            $capacity <= 100 => '50–100 Ah',
            $capacity <= 200 => '100–200 Ah',
            default => 'Более 200 Ah',
        };
    }

    /** @param Collection<int, array<string, mixed>> $records
     * @param  array<string, ?string>  $appliedFilters
     * @return array<string, list<array{value:string,label:string,count:int}>>
     */
    private function facets(Collection $records, bool $powerFacetsEnabled, array $appliedFilters): array
    {
        $facets = ['manufacturer', 'technology', 'nominal_voltage', 'capacity'];
        if ($powerFacetsEnabled) {
            $facets = [...$facets, ...$this->powerFacetKeys()];
        }

        return collect($facets)
            ->filter(fn (string $facet): bool => ($appliedFilters[$facet] ?? null) !== null
                || $this->facetPassesVisibilityGate($records, $facet))
            ->mapWithKeys(fn (string $facet): array => [$facet => $this->facetOptions($records, $facet)])
            ->all();
    }

    /** @param Collection<int, array<string, mixed>> $records */
    private function facetPassesVisibilityGate(Collection $records, string $facet): bool
    {
        $minimumFilled = max(10, (int) ceil($records->count() * 0.1));
        $filled = $records->filter(function (array $record) use ($facet): bool {
            $value = $record[$facet] ?? null;

            return is_string($value) && $value !== '';
        })->count();

        return $filled >= $minimumFilled;
    }

    /** @param Collection<int, array<string, mixed>> $records
     * @return list<array{value:string,label:string,count:int}>
     */
    private function facetOptions(Collection $records, string $facet): array
    {
        $counts = [];
        foreach ($records as $record) {
            $value = $record[$facet] ?? null;
            if (! is_string($value) || $value === '') {
                continue;
            }

            $identity = mb_strtolower($value);
            $counts[$identity] ??= ['value' => $value, 'label' => $value, 'count' => 0];
            $counts[$identity]['count']++;
        }

        $options = array_values($counts);
        usort($options, static function (array $left, array $right) use ($facet): int {
            if ($facet === 'capacity') {
                $order = array_flip(['До 5 Ah', '5–10 Ah', '10–20 Ah', '20–50 Ah', '50–100 Ah', '100–200 Ah', 'Более 200 Ah']);
                $rank = ($order[$left['value']] ?? PHP_INT_MAX) <=> ($order[$right['value']] ?? PHP_INT_MAX);
                if ($rank !== 0) {
                    return $rank;
                }
            } elseif ($facet === 'nominal_voltage') {
                $numeric = (float) $left['value'] <=> (float) $right['value'];
                if ($numeric !== 0) {
                    return $numeric;
                }
            }

            return strnatcasecmp($left['label'], $right['label']);
        });

        return $options;
    }

    /** @param array<string, mixed> $validated
     * @return array<string, ?string>
     */
    private function appliedFilters(array $validated, bool $powerFacetsEnabled): array
    {
        $filters = [
            'manufacturer' => $this->normalizeManufacturer($validated['manufacturer'] ?? null),
            'technology' => $this->normalizeTechnology($validated['technology'] ?? null),
            'nominal_voltage' => $this->normalizeNominalVoltage($validated['nominal_voltage'] ?? null),
            'capacity' => $this->capacityBucket($validated['capacity'] ?? null),
        ];

        foreach ($this->powerFacetKeys() as $facet) {
            $filters[$facet] = $powerFacetsEnabled
                ? $this->cleanFacetValue($validated[$facet] ?? null)
                : null;
        }

        return $filters;
    }

    /** @return list<string> */
    private function powerFacetKeys(): array
    {
        return ['power', 'input_voltage', 'output_voltage', 'input_current', 'output_current', 'phase', 'topology', 'device_type'];
    }

    private function powerFacetsEnabled(?string $category): bool
    {
        if ($category === null) {
            return false;
        }

        $leaf = strtolower((string) str($category)->afterLast('/'));

        return in_array($leaf, ['power-supplies', 'power-converters', 'ups-systems'], true);
    }

    /** @param array<string, mixed> $record
     * @param  array<string, ?string>  $filters
     */
    private function matchesFilters(array $record, array $filters): bool
    {
        foreach ($filters as $facet => $selected) {
            if ($selected !== null && mb_strtolower((string) ($record[$facet] ?? '')) !== mb_strtolower($selected)) {
                return false;
            }
        }

        return true;
    }

    /** @return array<string, string> */
    private function summaryAttributes(Product $product, bool $includePowerFacets): array
    {
        $summary = $this->productFacetValues($product, $includePowerFacets);
        unset($summary['manufacturer']);

        return array_filter($summary, static fn (?string $value): bool => $value !== null);
    }

    public function categories(Request $request, string $site): JsonResponse
    {
        $validated = $request->validate([
            'locale' => ['nullable', 'string', 'max:20'],
        ]);
        $siteModel = Site::query()->where('key', $site)->where('is_active', true)->firstOrFail();
        $locale = $this->requestedEnabledLocale($siteModel, $validated['locale'] ?? null);
        $categories = SiteCategory::query()
            ->with('category')
            ->published()
            ->where('site_id', $siteModel->id)
            ->orderBy('sort_order')
            ->orderBy('id')
            ->get();
        $pathsByCategoryId = SiteUrl::query()
            ->where('site_id', $siteModel->id)
            ->where('target_type', 'category')
            ->where('locale', $locale)
            ->pluck('path', 'target_id');
        $byCanonicalId = $categories->keyBy('category_id');
        $children = $categories->groupBy(function (SiteCategory $siteCategory) use ($byCanonicalId): int {
            $parentId = $siteCategory->category?->parent_id;

            return $parentId !== null && $byCanonicalId->has($parentId) ? $parentId : 0;
        });

        return response()->json([
            'data' => $this->categoryTree($children, 0, $pathsByCategoryId),
        ]);
    }

    /** @return list<int> */
    private function categoryAndDescendantIds(Site $site, string $slug): array
    {
        $categories = SiteCategory::query()
            ->with('category')
            ->published()
            ->where('site_id', $site->id)
            ->get();
        $selected = $categories->firstWhere('slug', $slug);
        if ($selected === null) {
            return [];
        }

        $canonicalIds = [(int) $selected->category_id];
        do {
            $before = count($canonicalIds);
            foreach ($categories as $candidate) {
                if (in_array($candidate->category?->parent_id, $canonicalIds, true)) {
                    $canonicalIds[] = (int) $candidate->category_id;
                    $canonicalIds = array_values(array_unique($canonicalIds));
                }
            }
        } while (count($canonicalIds) > $before);

        return $categories
            ->whereIn('category_id', $canonicalIds)
            ->pluck('id')
            ->map(static fn (mixed $id): int => (int) $id)
            ->values()
            ->all();
    }

    private function requestedEnabledLocale(Site $site, ?string $requestedLocale): string
    {
        $locale = $requestedLocale ?? $site->default_locale;
        $siteLocale = $site->locales()
            ->where('locale', $locale)
            ->first();

        // Existing sites created before site_locales was introduced may not
        // have an explicit row for their default locale. The Site model still
        // owns that default as its compatibility contract; non-default
        // locales must always have an enabled row.
        if ($siteLocale === null && $locale === $site->default_locale) {
            return $locale;
        }

        if ($siteLocale === null || ! $siteLocale->is_enabled) {
            throw ValidationException::withMessages(['locale' => 'The requested locale is not enabled for this site.']);
        }

        return $locale;
    }

    /**
     * @param  Collection<int, Collection<int, SiteCategory>>  $children
     * @param  Collection<int, string>  $pathsByCategoryId
     * @return list<array<string, mixed>>
     */
    private function categoryTree(Collection $children, int $parentId, Collection $pathsByCategoryId): array
    {
        return $children->get($parentId, collect())
            ->map(fn (SiteCategory $siteCategory): array => [
                'slug' => $siteCategory->slug,
                'name' => $siteCategory->name ?? $siteCategory->category?->name,
                'path' => $pathsByCategoryId->get($siteCategory->id),
                'children' => $this->categoryTree($children, (int) $siteCategory->category_id, $pathsByCategoryId),
            ])
            ->values()
            ->all();
    }
}
