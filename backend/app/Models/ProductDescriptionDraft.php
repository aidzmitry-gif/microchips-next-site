<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class ProductDescriptionDraft extends Model
{
    protected $fillable = [
        'product_id', 'staged_import_record_id', 'locale', 'title', 'content',
        'verified_fields', 'source_urls', 'status', 'rejection_reason',
        'submitted_by', 'submitted_at',
    ];

    protected function casts(): array
    {
        return [
            'verified_fields' => 'array',
            'source_urls' => 'array',
            'submitted_at' => 'datetime',
        ];
    }

    public function product(): BelongsTo
    {
        return $this->belongsTo(Product::class);
    }

    public function stagedImportRecord(): BelongsTo
    {
        return $this->belongsTo(StagedImportRecord::class);
    }

    public function submittedBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'submitted_by');
    }
}
