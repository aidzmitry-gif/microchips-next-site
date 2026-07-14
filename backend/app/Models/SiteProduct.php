<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

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

    protected static function booted(): void
    {
        static::saved(function (self $siteProduct): void {
            $paths = SiteUrl::query()
                ->where('site_id', $siteProduct->site_id)
                ->where('target_type', 'product')
                ->where('target_id', $siteProduct->id)
                ->pluck('path')
                ->all();

            SiteContentChanged::dispatch($siteProduct->site, $paths === [] ? ['/'] : $paths);
        });
    }
}
