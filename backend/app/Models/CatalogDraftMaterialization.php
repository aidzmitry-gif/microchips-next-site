<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class CatalogDraftMaterialization extends Model
{
    public const KIND_NAMESPACED_DRAFT = 'namespaced_draft';

    public const KIND_EXISTING_EXACT_LINK = 'existing_exact_link';

    protected $fillable = [
        'materialization_run_id', 'source_import_run_id', 'staged_import_record_id',
        'site_id', 'product_id', 'site_product_id', 'source_namespace',
        'source_external_id', 'source_checksum', 'materialization_kind',
        'target_category_external_id',
    ];

    public function materializationRun(): BelongsTo
    {
        return $this->belongsTo(ImportRun::class, 'materialization_run_id');
    }

    public function sourceImportRun(): BelongsTo
    {
        return $this->belongsTo(ImportRun::class, 'source_import_run_id');
    }

    public function stagedImportRecord(): BelongsTo
    {
        return $this->belongsTo(StagedImportRecord::class);
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    public function product(): BelongsTo
    {
        return $this->belongsTo(Product::class);
    }

    public function siteProduct(): BelongsTo
    {
        return $this->belongsTo(SiteProduct::class);
    }
}
