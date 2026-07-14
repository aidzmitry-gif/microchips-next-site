<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SiteIntegration extends Model
{
    protected $fillable = ['site_id', 'driver', 'settings', 'is_enabled'];

    protected function casts(): array
    {
        return ['settings' => 'array', 'is_enabled' => 'boolean'];
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }
}
