<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Lead extends Model
{
    protected $fillable = [
        'site_id', 'locale', 'type', 'company', 'contact_name', 'email', 'phone', 'message', 'page_url',
        'cart', 'utm', 'status', 'external_id', 'external_error',
    ];

    protected function casts(): array
    {
        return ['cart' => 'array', 'utm' => 'array'];
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }
}
