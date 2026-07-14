<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class StagedImportRecord extends Model
{
    protected $fillable = [
        'import_run_id', 'row_number', 'entity_type', 'external_id', 'payload', 'normalized_payload',
        'validation_errors', 'status', 'error', 'review_note', 'reviewed_by', 'reviewed_at',
        'published_by', 'published_product_id', 'published_site_id', 'published_at', 'publication_snapshot',
    ];

    protected function casts(): array
    {
        return [
            'payload' => 'array',
            'normalized_payload' => 'array',
            'validation_errors' => 'array',
            'publication_snapshot' => 'array',
            'reviewed_at' => 'datetime',
            'published_at' => 'datetime',
        ];
    }

    public function importRun(): BelongsTo
    {
        return $this->belongsTo(ImportRun::class);
    }

    public function reviewedBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'reviewed_by');
    }

    public function publishedBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'published_by');
    }

    public function publishedProduct(): BelongsTo
    {
        return $this->belongsTo(Product::class, 'published_product_id');
    }

    public function publishedSite(): BelongsTo
    {
        return $this->belongsTo(Site::class, 'published_site_id');
    }
}
