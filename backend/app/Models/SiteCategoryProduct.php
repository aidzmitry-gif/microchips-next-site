<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Relations\Pivot;
use LogicException;

class SiteCategoryProduct extends Pivot
{
    protected $table = 'site_category_product';

    protected $fillable = ['site_id', 'site_category_id', 'site_product_id'];

    // The table has its own auto-increment `id` (see the migration); this is
    // not a composite-key pivot. Without this override, Pivot's default
    // `$incrementing = false` leaves `id` null on the in-memory model right
    // after create(), even though the row itself has a real one -- callers
    // that need to log which link was created (see SiteProductCategoryAssigner)
    // would otherwise log null.
    public $incrementing = true;

    protected static function booted(): void
    {
        static::creating(function (self $pivot): void {
            $categorySiteId = SiteCategory::query()->whereKey($pivot->site_category_id)->value('site_id');
            $productSiteId = SiteProduct::query()->whereKey($pivot->site_product_id)->value('site_id');

            if ($categorySiteId === null || $productSiteId === null || (int) $categorySiteId !== (int) $productSiteId) {
                throw new LogicException('A category can only contain a site product from the same site.');
            }

            $pivot->site_id = $categorySiteId;
        });

        static::saved(fn (self $pivot) => self::revalidateCategory($pivot));
        static::deleted(fn (self $pivot) => self::revalidateCategory($pivot));
    }

    private static function revalidateCategory(self $pivot): void
    {
        $category = SiteCategory::query()->with('site')->find($pivot->site_category_id);

        if ($category === null) {
            return;
        }

        $paths = SiteCategory::revalidationPaths($category->site_id, [$category->id]);

        SiteContentChanged::dispatch($category->site, $paths === [] ? ['/'] : $paths);
    }
}
