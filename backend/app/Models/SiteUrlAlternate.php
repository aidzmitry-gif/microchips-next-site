<?php

namespace App\Models;

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
}
