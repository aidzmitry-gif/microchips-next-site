<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SiteUrl extends Model
{
    protected $fillable = ['site_id', 'path', 'locale', 'target_type', 'target_id', 'is_indexable'];

    protected function casts(): array
    {
        return ['is_indexable' => 'boolean'];
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    protected static function booted(): void
    {
        static::saved(function (self $url): void {
            self::revalidate($url, [$url->path, $url->getOriginal('path')]);
        });

        static::deleted(function (self $url): void {
            self::revalidate($url, [$url->path]);
        });
    }

    /** @param array<int, mixed> $paths */
    private static function revalidate(self $url, array $paths): void
    {
        $paths = array_values(array_unique(array_filter([
            ...$paths,
            '/sitemap.xml',
        ], static fn (mixed $path): bool => is_string($path) && str_starts_with($path, '/'))));

        SiteContentChanged::dispatch($url->site, $paths);
    }
}
