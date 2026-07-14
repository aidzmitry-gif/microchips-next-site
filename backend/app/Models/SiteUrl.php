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
        static::saved(fn (self $url) => SiteContentChanged::dispatch($url->site, [$url->path]));
    }
}
