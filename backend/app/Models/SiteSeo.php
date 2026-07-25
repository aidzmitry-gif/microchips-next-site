<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SiteSeo extends Model
{
    protected $fillable = [
        'site_id', 'locale', 'resource_type', 'resource_id', 'canonical_path', 'title', 'description',
        'is_indexable', 'schema',
    ];

    protected function casts(): array
    {
        return ['is_indexable' => 'boolean', 'schema' => 'array'];
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    protected static function booted(): void
    {
        static::saved(fn (self $seo) => self::revalidate($seo));
        static::deleted(fn (self $seo) => self::revalidate($seo));
    }

    private static function revalidate(self $seo): void
    {
        $paths = SiteUrl::query()
            ->where('site_id', $seo->site_id)
            ->where('target_type', $seo->resource_type)
            ->where('target_id', $seo->resource_id)
            ->pluck('path')
            ->all();

        SiteContentChanged::dispatch($seo->site, array_values(array_unique([
            ...$paths,
            '/sitemap.xml',
        ])));
    }
}
