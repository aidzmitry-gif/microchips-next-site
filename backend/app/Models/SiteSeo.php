<?php

namespace App\Models;

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
}
