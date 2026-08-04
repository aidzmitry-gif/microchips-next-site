<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SiteRedirect extends Model
{
    public const PURPOSE_SEO = 'seo';

    public const PURPOSE_PREVIEW = 'preview';

    protected $fillable = ['site_id', 'source_path', 'target_path', 'status_code', 'purpose', 'is_active'];

    protected function casts(): array
    {
        return ['is_active' => 'boolean'];
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    protected static function booted(): void
    {
        static::saved(function (self $redirect): void {
            self::revalidate($redirect, [$redirect->source_path, $redirect->target_path, $redirect->getOriginal('source_path'), $redirect->getOriginal('target_path')]);
        });
        static::deleted(fn (self $redirect) => self::revalidate($redirect, [$redirect->source_path, $redirect->target_path]));
    }

    /** @param array<int, mixed> $paths */
    private static function revalidate(self $redirect, array $paths): void
    {
        $paths = array_values(array_unique(array_filter([
            ...$paths,
            '/sitemap.xml',
        ], static fn (mixed $path): bool => is_string($path) && str_starts_with($path, '/'))));

        SiteContentChanged::dispatch($redirect->site, $paths);
    }
}
