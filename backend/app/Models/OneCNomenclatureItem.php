<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class OneCNomenclatureItem extends Model
{
    protected $fillable = [
        'import_run_id', 'source_key', 'external_id', 'is_group', 'parent_external_id',
        'article', 'name', 'full_path', 'unit', 'price', 'currency', 'price_type',
        'classification_status', 'classification_flags', 'source_payload', 'source_checksum',
    ];

    protected function casts(): array
    {
        return [
            'is_group' => 'boolean',
            'price' => 'decimal:4',
            'classification_flags' => 'array',
            'source_payload' => 'array',
        ];
    }

    public function importRun(): BelongsTo
    {
        return $this->belongsTo(ImportRun::class);
    }
}
