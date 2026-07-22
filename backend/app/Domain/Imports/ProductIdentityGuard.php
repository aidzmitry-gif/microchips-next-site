<?php

namespace App\Domain\Imports;

use App\Models\Product;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Support\Collection;
use Illuminate\Support\Facades\DB;

class ProductIdentityGuard
{
    /**
     * @param  array<string, mixed>  $data
     */
    public function findByExternalId(array $data): ?Product
    {
        $externalId = ProductIdentity::normalize($data['external_id'] ?? null);

        if ($externalId === null) {
            return null;
        }

        return Product::query()
            ->where('external_id_normalized', $externalId)
            ->lockForUpdate()
            ->first();
    }

    /**
     * Must run inside the publisher transaction. PostgreSQL transaction locks
     * serialize concurrent imports of the same canonical identifier.
     *
     * @param  array<string, mixed>  $data
     */
    public function assertCanPersist(array $data, ?Product $existingByExternalId = null): void
    {
        $fingerprints = ProductIdentity::fingerprints($data);
        $this->lockFingerprints($fingerprints);

        if ($existingByExternalId !== null) {
            $this->assertExistingIdentityIsStable($existingByExternalId, $data);
        }

        $conflictingProducts = $this->conflictingProducts($fingerprints, $existingByExternalId?->id);

        if ($conflictingProducts->isEmpty()) {
            return;
        }

        $matchingField = $this->matchingField($fingerprints, $conflictingProducts->first());
        $matchValue = $fingerprints[$matchingField] ?? 'unknown';

        throw new ProductIdentityConflict(
            $matchingField.':'.$matchValue,
            $conflictingProducts->pluck('id')->map(static fn (mixed $id): int => (int) $id)->all(),
            'A product with the same canonical SKU or MPN already exists. Resolve the duplicate conflict before publishing.',
        );
    }

    public function assertManualIdentityIsStable(Product $product): void
    {
        if (! $product->exists || ! $product->isDirty(['external_id', 'sku', 'mpn', 'manufacturer'])) {
            return;
        }

        $stored = Product::query()->find($product->id);

        if ($stored === null) {
            return;
        }

        foreach (['external_id', 'sku', 'mpn', 'manufacturer'] as $field) {
            $before = ProductIdentity::normalize($stored->getAttribute($field));
            $after = ProductIdentity::normalize($product->getAttribute($field));

            if ($before !== null && $after !== null && $before !== $after) {
                throw new ProductIdentityConflict(
                    $field.':'.$before,
                    [$product->id],
                    'Existing product identifiers cannot be changed outside the duplicate-resolution workflow.',
                );
            }
        }
    }

    public function assertManualProductCanPersist(Product $product): void
    {
        $this->assertManualIdentityIsStable($product);

        $conflictingProducts = $this->conflictingProducts(
            ProductIdentity::fingerprints($product->only(ProductIdentity::FIELDS)),
            $product->exists ? $product->id : null,
        );

        if ($conflictingProducts->isEmpty()) {
            return;
        }

        throw new ProductIdentityConflict(
            'identifier:manual',
            $conflictingProducts->pluck('id')->map(static fn (mixed $id): int => (int) $id)->all(),
            'A product with the same canonical SKU or MPN already exists.',
        );
    }

    /**
     * @param  array<string, string>  $fingerprints
     * @return Collection<int, Product>
     */
    private function conflictingProducts(array $fingerprints, ?int $exceptProductId): Collection
    {
        $identifierFingerprints = array_intersect_key($fingerprints, array_flip(['sku', 'mpn']));

        if ($identifierFingerprints === []) {
            return collect();
        }

        return Product::query()
            ->when($exceptProductId !== null, fn (Builder $query) => $query->whereKeyNot($exceptProductId))
            ->where(function (Builder $query) use ($identifierFingerprints): void {
                foreach ($identifierFingerprints as $fingerprint) {
                    $query->orWhere('sku_normalized', $fingerprint)
                        ->orWhere('mpn_normalized', $fingerprint);
                }
            })
            ->lockForUpdate()
            ->get();
    }

    /**
     * @param  array<string, string>  $fingerprints
     */
    private function lockFingerprints(array $fingerprints): void
    {
        if (DB::getDriverName() !== 'pgsql') {
            return;
        }

        foreach (array_unique(array_values($fingerprints)) as $fingerprint) {
            DB::select('select pg_advisory_xact_lock(hashtext(?))', ['product-identity:'.$fingerprint]);
        }
    }

    /** @param array<string, mixed> $data */
    private function assertExistingIdentityIsStable(Product $existing, array $data): void
    {
        foreach (['sku', 'mpn', 'manufacturer'] as $field) {
            $before = ProductIdentity::normalize($existing->getAttribute($field));
            $after = ProductIdentity::normalize($data[$field] ?? null);

            if ($before !== null && $after !== null && $before !== $after) {
                throw new ProductIdentityConflict(
                    'external_id:'.ProductIdentity::normalize($existing->external_id),
                    [$existing->id],
                    'Incoming identifiers conflict with the existing product for this external ID.',
                );
            }
        }
    }

    /**
     * @param  array<string, string>  $fingerprints
     */
    private function matchingField(array $fingerprints, Product $product): string
    {
        foreach (['sku', 'mpn'] as $field) {
            $fingerprint = $fingerprints[$field] ?? null;

            if ($fingerprint !== null && in_array($fingerprint, [$product->sku_normalized, $product->mpn_normalized], true)) {
                return $field;
            }
        }

        return 'identifier';
    }
}
