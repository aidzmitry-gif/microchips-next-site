<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Support\Collection;

class CatalogController extends Controller
{
    public function index(Request $request, string $site): JsonResponse
    {
        $validated = $request->validate([
            'q' => ['nullable', 'string', 'max:100'],
            'category' => ['nullable', 'string', 'max:255'],
            'locale' => ['nullable', 'string', 'max:20'],
            'per_page' => ['nullable', 'integer', 'min:1', 'max:100'],
        ]);

        $siteModel = Site::query()->where('key', $site)->where('is_active', true)->firstOrFail();
        $query = SiteProduct::query()
            ->with('product')
            ->published()
            ->where('site_id', $siteModel->id)
            ->orderBy('sort_order')
            ->orderBy('id');

        if (($validated['q'] ?? null) !== null) {
            $search = $validated['q'];
            $query->whereHas('product', function (Builder $products) use ($search): void {
                $products->where('name', 'like', "%{$search}%")
                    ->orWhere('sku', 'like', "%{$search}%")
                    ->orWhere('mpn', 'like', "%{$search}%");
            });
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

        $products = $query->paginate($validated['per_page'] ?? 24);
        $pathsByProductId = SiteUrl::query()
            ->where('site_id', $siteModel->id)
            ->where('target_type', 'product')
            ->where('locale', $validated['locale'] ?? $siteModel->default_locale)
            ->whereIn('target_id', $products->getCollection()->pluck('id'))
            ->pluck('path', 'target_id');

        return response()->json([
            'data' => $products->getCollection()->map(fn (SiteProduct $siteProduct) => [
                'slug' => $siteProduct->slug,
                'path' => $pathsByProductId->get($siteProduct->id),
                'name' => $siteProduct->product->name,
                'sku' => $siteProduct->product->sku,
                'mpn' => $siteProduct->product->mpn,
                'availability' => $siteProduct->availability,
                'price' => $siteProduct->price,
                'currency' => $siteModel->currency_code,
            ])->values(),
            'meta' => [
                'current_page' => $products->currentPage(),
                'last_page' => $products->lastPage(),
                'total' => $products->total(),
            ],
        ]);
    }

    public function categories(Request $request, string $site): JsonResponse
    {
        $validated = $request->validate([
            'locale' => ['nullable', 'string', 'max:20'],
        ]);
        $siteModel = Site::query()->where('key', $site)->where('is_active', true)->firstOrFail();
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
            ->where('locale', $validated['locale'] ?? $siteModel->default_locale)
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
