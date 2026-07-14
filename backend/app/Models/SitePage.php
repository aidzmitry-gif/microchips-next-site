<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SitePage extends Model
{
    protected $fillable = ['site_id', 'locale', 'slug', 'title', 'h1', 'content', 'is_published'];

    protected function casts(): array
    {
        return ['is_published' => 'boolean'];
    }

    public function scopePublished(Builder $query): Builder
    {
        return $query->where('is_published', true);
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    protected static function booted(): void
    {
        static::saved(function (self $page): void {
            $paths = SiteUrl::query()
                ->where('site_id', $page->site_id)
                ->where('target_type', 'page')
                ->where('target_id', $page->id)
                ->pluck('path')
                ->all();

            SiteContentChanged::dispatch($page->site, $paths === [] ? ['/'] : $paths);
        });
    }
}
