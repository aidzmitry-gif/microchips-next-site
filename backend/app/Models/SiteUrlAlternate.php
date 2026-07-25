<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SiteUrlAlternate extends Model
{
    protected $fillable = ['source_url_id', 'alternate_url_id', 'locale'];

    public function sourceUrl(): BelongsTo
    {
        return $this->belongsTo(SiteUrl::class, 'source_url_id');
    }

    public function alternateUrl(): BelongsTo
    {
        return $this->belongsTo(SiteUrl::class, 'alternate_url_id');
    }

    protected static function booted(): void
    {
        static::saved(fn (self $alternate) => self::revalidate($alternate));
        static::deleted(fn (self $alternate) => self::revalidate($alternate));
    }

    private static function revalidate(self $alternate): void
    {
        $urlIds = array_values(array_unique(array_filter([
            $alternate->source_url_id,
            $alternate->alternate_url_id,
            $alternate->getOriginal('source_url_id'),
            $alternate->getOriginal('alternate_url_id'),
        ], static fn (mixed $id): bool => is_int($id) || ctype_digit((string) $id))));

        SiteUrl::query()
            ->with('site')
            ->whereIn('id', $urlIds)
            ->get()
            ->groupBy('site_id')
            ->each(function ($urls): void {
                $site = $urls->first()?->site;
                if ($site === null) {
                    return;
                }

                SiteContentChanged::dispatch($site, array_values(array_unique([
                    ...$urls->pluck('path')->all(),
                    '/sitemap.xml',
                ])));
            });
    }
}
