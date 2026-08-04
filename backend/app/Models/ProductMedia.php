<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

/**
 * A source and verification ledger for product media.
 *
 * Remote source URLs are evidence only: storefronts may expose a local asset
 * only after the model match and rights basis have been recorded as verified.
 */
class ProductMedia extends Model
{
    public const STATUS_VERIFIED = 'verified';

    public const STATUS_LEGACY_EXACT_PREVIEW = 'legacy_exact_preview';

    public const STATUS_NEEDS_REVIEW = 'needs_review';

    protected $fillable = [
        'product_id', 'kind', 'role', 'source_page_url', 'source_asset_url',
        'source_kind', 'rights_basis', 'storage_path', 'content_sha256',
        'verification_status', 'verification_note', 'verified_at', 'is_published', 'sort_order',
    ];

    protected function casts(): array
    {
        return ['verified_at' => 'datetime', 'is_published' => 'boolean'];
    }

    public function product(): BelongsTo
    {
        return $this->belongsTo(Product::class);
    }

    public function scopeStorefrontReady(Builder $query): Builder
    {
        return $query
            ->where('kind', 'image')
            ->where('verification_status', self::STATUS_VERIFIED)
            ->where('is_published', true)
            ->whereNotNull('storage_path')
            ->whereNotNull('rights_basis');
    }

    /**
     * Noindex catalogue previews may also show the exact image attached to
     * the very same legacy Bitrix element. It remains visibly distinguishable
     * from visually verified media and therefore does not increase the strict
     * storefront-ready/SEO-complete counter.
     */
    public function scopePreviewReady(Builder $query): Builder
    {
        return $query
            ->where('kind', 'image')
            ->whereIn('verification_status', [self::STATUS_VERIFIED, self::STATUS_LEGACY_EXACT_PREVIEW])
            ->where('is_published', true)
            ->whereNotNull('storage_path')
            ->whereNotNull('rights_basis');
    }
}
