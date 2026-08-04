<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;

class SiteCategory extends Model
{
    protected $fillable = [
        'site_id', 'source', 'external_id', 'category_id', 'slug', 'name', 'seo', 'is_published', 'sort_order',
    ];

    protected function casts(): array
    {
        return ['seo' => 'array', 'is_published' => 'boolean'];
    }

    public function scopePublished(Builder $query): Builder
    {
        return $query->where('is_published', true);
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    public function category(): BelongsTo
    {
        return $this->belongsTo(Category::class);
    }

    public function products(): BelongsToMany
    {
        return $this->belongsToMany(SiteProduct::class, 'site_category_product')
            ->using(SiteCategoryProduct::class)
            ->withPivot('site_id')
            ->withTimestamps();
    }

    protected static function booted(): void
    {
        static::saved(function (self $siteCategory): void {
            if (! $siteCategory->is_published && ! $siteCategory->wasChanged('is_published')) {
                return;
            }

            $paths = self::revalidationPaths($siteCategory->site_id, [$siteCategory->id]);
            if ($siteCategory->is_published || $siteCategory->wasChanged('is_published')) {
                $paths[] = '/catalog';
                $paths = array_values(array_unique($paths));
            }

            SiteContentChanged::dispatch($siteCategory->site, $paths === [] ? ['/'] : $paths);
        });
    }

    /** @param  list<int>  $siteCategoryIds
     * @return list<string>
     */
    public static function revalidationPaths(int $siteId, array $siteCategoryIds): array
    {
        if ($siteCategoryIds === []) {
            return [];
        }

        $categories = self::query()
            ->with('category')
            ->published()
            ->where('site_id', $siteId)
            ->get();
        $byId = $categories->keyBy('id');
        $byCanonicalId = $categories->keyBy('category_id');
        $targetIds = [];

        foreach ($siteCategoryIds as $siteCategoryId) {
            $current = $byId->get($siteCategoryId);
            while ($current !== null) {
                $targetIds[] = $current->id;
                $parentCanonicalId = $current->category?->parent_id;
                $current = $parentCanonicalId === null ? null : $byCanonicalId->get($parentCanonicalId);
            }
        }

        return SiteUrl::query()
            ->where('site_id', $siteId)
            ->where('target_type', 'category')
            ->whereIn('target_id', array_values(array_unique($targetIds)))
            ->pluck('path')
            ->unique()
            ->values()
            ->all();
    }
}
