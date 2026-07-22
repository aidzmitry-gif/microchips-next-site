<?php

namespace App\Models;

use App\Domain\Imports\ProductIdentity;
use App\Domain\Imports\ProductIdentityGuard;
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

    protected static function booted(): void
    {
        static::saving(function (Product $product): void {
            foreach (ProductIdentity::FIELDS as $field) {
                $product->setAttribute($field.'_normalized', ProductIdentity::normalize($product->getAttribute($field)));
            }

            app(ProductIdentityGuard::class)->assertManualProductCanPersist($product);
        });
    }

    public function sites(): HasMany
    {
        return $this->hasMany(SiteProduct::class);
    }
}
