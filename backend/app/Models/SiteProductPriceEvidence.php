<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class SiteProductPriceEvidence extends Model
{
    protected $table = 'site_product_price_evidences';

    public const SOURCE_LEGACY_SITE = 'legacy_site';

    public const SOURCE_ONE_C_X2 = 'one_c_x2';

    protected $fillable = [
        'site_id', 'site_product_id', 'source', 'source_price', 'multiplier',
        'calculated_price', 'currency', 'price_type', 'source_external_id',
        'source_reference', 'observed_at', 'evidence_key', 'evidence', 'is_current',
    ];

    protected function casts(): array
    {
        return [
            'source_price' => 'decimal:4',
            'multiplier' => 'decimal:4',
            'calculated_price' => 'decimal:2',
            'observed_at' => 'immutable_datetime',
            'evidence' => 'array',
            'is_current' => 'boolean',
        ];
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    public function siteProduct(): BelongsTo
    {
        return $this->belongsTo(SiteProduct::class);
    }
}
