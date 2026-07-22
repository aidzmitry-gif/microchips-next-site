<?php

namespace App\Domain\Imports;

use App\Models\CatalogIdentityCandidate;
use App\Models\User;
use Illuminate\Support\Facades\DB;
use Illuminate\Validation\ValidationException;

class IdentityCandidateReviewer
{
    /** @param array<string, mixed> $data */
    public function approve(CatalogIdentityCandidate $candidate, User $reviewer, array $data): CatalogIdentityCandidate
    {
        if ($candidate->review_status !== 'pending') {
            throw ValidationException::withMessages(['review_status' => 'Only a pending candidate can be approved.']);
        }

        $sku = $this->clean($data['confirmed_sku'] ?? null);
        $mpn = $this->clean($data['confirmed_mpn'] ?? null);
        if ($sku === null && $mpn === null) {
            throw ValidationException::withMessages(['identifier' => 'Confirm at least one SKU or MPN.']);
        }

        return DB::transaction(function () use ($candidate, $reviewer, $data, $sku, $mpn): CatalogIdentityCandidate {
            $locked = CatalogIdentityCandidate::query()->lockForUpdate()->findOrFail($candidate->id);
            if ($locked->review_status !== 'pending') {
                throw ValidationException::withMessages(['review_status' => 'Candidate status changed during review.']);
            }

            $normalizedSku = ProductIdentity::normalize($sku);
            $normalizedMpn = ProductIdentity::normalize($mpn);
            $identities = array_values(array_unique(array_filter([$normalizedSku, $normalizedMpn])));
            if ($identities === []) {
                throw ValidationException::withMessages(['identifier' => 'SKU or MPN must contain letters or digits.']);
            }

            $identityExists = CatalogIdentityCandidate::query()
                ->whereKeyNot($locked->id)
                ->where(function ($query) use ($identities): void {
                    $query->whereIn('confirmed_sku_normalized', $identities)
                        ->orWhereIn('confirmed_mpn_normalized', $identities);
                })
                ->exists();
            if ($identityExists) {
                throw ValidationException::withMessages(['identifier' => 'This SKU or MPN is already confirmed for another candidate.']);
            }

            try {
                app(ProductIdentityGuard::class)->assertCanPersist(['sku' => $sku, 'mpn' => $mpn]);
            } catch (ProductIdentityConflict) {
                throw ValidationException::withMessages(['identifier' => 'This SKU or MPN already belongs to a catalog product.']);
            }

            $locked->update([
                'review_status' => 'approved_for_staging',
                'confirmed_sku' => $sku,
                'confirmed_sku_normalized' => $normalizedSku,
                'confirmed_mpn' => $mpn,
                'confirmed_mpn_normalized' => $normalizedMpn,
                'confirmed_manufacturer' => $this->clean($data['confirmed_manufacturer'] ?? null),
                'confirmed_category' => $this->clean($data['confirmed_category'] ?? null),
                'review_note' => $this->clean($data['review_note'] ?? null),
                'reviewed_by' => $reviewer->id,
                'reviewed_at' => now(),
            ]);

            return $locked->refresh();
        });
    }

    public function reject(CatalogIdentityCandidate $candidate, User $reviewer, string $note): CatalogIdentityCandidate
    {
        if ($candidate->review_status !== 'pending') {
            throw ValidationException::withMessages(['review_status' => 'Only a pending candidate can be rejected.']);
        }

        $note = trim($note);
        if ($note === '') {
            throw ValidationException::withMessages(['review_note' => 'A rejection reason is required.']);
        }

        $candidate->update([
            'review_status' => 'rejected',
            'review_note' => $note,
            'reviewed_by' => $reviewer->id,
            'reviewed_at' => now(),
        ]);

        return $candidate->refresh();
    }

    private function clean(mixed $value): ?string
    {
        return is_scalar($value) && trim((string) $value) !== '' ? trim((string) $value) : null;
    }
}
