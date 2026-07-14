<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Product extends Model
{
    protected $fillable = [
        'external_id', 'sku', 'mpn', 'manufacturer', 'slug', 'name', 'short_description', 'technical_attributes', 'status',
    ];

    protected function casts(): array
    {
        return ['technical_attributes' => 'array'];
    }

    public function sites(): HasMany
    {
        return $this->hasMany(SiteProduct::class);
    }
}
