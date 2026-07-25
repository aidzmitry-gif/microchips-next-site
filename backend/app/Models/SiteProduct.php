<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;

class SiteProduct extends Model
{
    protected $fillable = [
        'site_id', 'product_id', 'slug', 'is_published', 'availability', 'price', 'seo', 'sort_order',
    ];

    protected function casts(): array
    {
        return ['is_published' => 'boolean', 'price' => 'decimal:2', 'seo' => 'array'];
    }

    public function scopePublished(Builder $query): Builder
    {
        return $query->where('is_published', true);
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    public function product(): BelongsTo
    {
        return $this->belongsTo(Product::class);
    }

    public function categories(): BelongsToMany
    {
        return $this->belongsToMany(SiteCategory::class, 'site_category_product')
            ->using(SiteCategoryProduct::class)
            ->withPivot('site_id')
            ->withTimestamps();
    }

    protected static function booted(): void
    {
        static::saved(function (self $siteProduct): void {
            $paths = SiteUrl::query()
                ->where('site_id', $siteProduct->site_id)
                ->where('target_type', 'product')
                ->where('target_id', $siteProduct->id)
                ->pluck('path')
                ->all();

            $categoryIds = $siteProduct->categories()
                ->published()
                ->pluck('site_categories.id')
                ->map(static fn (mixed $id): int => (int) $id)
                ->all();
            $paths = array_values(array_unique([
                ...$paths,
                ...SiteCategory::revalidationPaths($siteProduct->site_id, $categoryIds),
            ]));

            SiteContentChanged::dispatch($siteProduct->site, $paths === [] ? ['/'] : $paths);
        });
    }
}
