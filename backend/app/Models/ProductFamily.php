<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class ProductFamily extends Model
{
    public const STATUS_VERIFIED = 'verified';

    protected $fillable = [
        'site_id', 'canonical_product_id', 'family_key', 'name', 'manufacturer', 'model_core', 'selector_label',
        'canonical_label', 'canonical_attributes', 'shared_attributes', 'source_url', 'status',
    ];

    protected function casts(): array
    {
        return ['canonical_attributes' => 'array', 'shared_attributes' => 'array'];
    }

    public function canonicalProduct(): BelongsTo
    {
        return $this->belongsTo(Product::class, 'canonical_product_id');
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    public function variants(): HasMany
    {
        return $this->hasMany(ProductVariant::class);
    }
}
