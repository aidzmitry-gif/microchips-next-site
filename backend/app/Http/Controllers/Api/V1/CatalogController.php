<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class CatalogController extends Controller
{
    public function index(Request $request, string $site): JsonResponse
    {
        $validated = $request->validate([
            'q' => ['nullable', 'string', 'max:100'],
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

        $products = $query->paginate($validated['per_page'] ?? 24);

        return response()->json([
            'data' => $products->getCollection()->map(fn (SiteProduct $siteProduct) => [
                'slug' => $siteProduct->slug,
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
}
