<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class CatalogIdentityCandidate extends Model
{
    protected $fillable = [
        'import_run_id', 'one_c_nomenclature_item_id', 'legacy_source', 'legacy_id',
        'legacy_name', 'legacy_url', 'review_priority', 'review_batch', 'confidence',
        'match_method', 'signature', 'comparison_status', 'review_status',
        'confirmed_sku', 'confirmed_sku_normalized', 'confirmed_mpn',
        'confirmed_mpn_normalized', 'confirmed_manufacturer', 'confirmed_category',
        'review_note', 'reviewed_by', 'reviewed_at', 'source_payload', 'source_checksum',
    ];

    protected function casts(): array
    {
        return [
            'confidence' => 'decimal:4',
            'reviewed_at' => 'datetime',
            'source_payload' => 'array',
        ];
    }

    public function importRun(): BelongsTo
    {
        return $this->belongsTo(ImportRun::class);
    }

    public function oneCItem(): BelongsTo
    {
        return $this->belongsTo(OneCNomenclatureItem::class, 'one_c_nomenclature_item_id');
    }

    public function reviewedBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'reviewed_by');
    }
}
