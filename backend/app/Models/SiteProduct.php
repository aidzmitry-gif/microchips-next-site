<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;
use Illuminate\Database\Eloquent\Relations\HasMany;
use Illuminate\Database\Eloquent\Relations\HasOne;

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

    public function priceEvidences(): HasMany
    {
        return $this->hasMany(SiteProductPriceEvidence::class);
    }

    public function currentPriceEvidence(): HasOne
    {
        return $this->hasOne(SiteProductPriceEvidence::class)->where('is_current', true);
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

            // `/catalog` is a live aggregate (tree, total and first page),
            // not merely a redirect. A newly visible product can change it
            // even when no URL existed at model-creation time, so refreshing
            // only the product/category paths leaves the root stale until its
            // ISR TTL expires.
            if ($siteProduct->is_published || $siteProduct->wasChanged('is_published')) {
                $paths[] = '/catalog';
                $paths = array_values(array_unique($paths));
            }

            SiteContentChanged::dispatch($siteProduct->site, $paths === [] ? ['/'] : $paths);
        });
    }
}
