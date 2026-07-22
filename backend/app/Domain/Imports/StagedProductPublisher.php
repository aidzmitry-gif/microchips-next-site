<?php

namespace App\Domain\Imports;

use App\Models\DuplicateConflict;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use App\Models\User;
use DomainException;
use Illuminate\Support\Facades\DB;

class StagedProductPublisher
{
    public function __construct(
        private readonly StageProductValidator $validator,
        private readonly ProductIdentityGuard $identityGuard,
    ) {}

    public function review(StagedImportRecord $record, ?User $reviewer, ?string $note = null): StagedImportRecord
    {
        return DB::transaction(function () use ($record, $reviewer, $note): StagedImportRecord {
            $record = StagedImportRecord::query()->lockForUpdate()->findOrFail($record->id);
            $this->assertCanBeReviewed($record);

            $record->update([
                'status' => 'reviewed',
                'review_note' => filled($note) ? trim($note) : null,
                'reviewed_by' => $reviewer?->id,
                'reviewed_at' => now(),
            ]);

            return $record->refresh();
        });
    }

    public function publishToSite(StagedImportRecord $record, Site $site, ?User $publisher): StagedImportRecord
    {
        $identityConflict = null;

        $publishedRecord = DB::transaction(function () use ($record, $site, $publisher, &$identityConflict): ?StagedImportRecord {
            $record = StagedImportRecord::query()->lockForUpdate()->findOrFail($record->id);
            $this->assertCanBePublished($record);

            $validation = $this->validator->normalizeAndValidate($record->payload);
            if ($validation['errors'] !== []) {
                $record->update([
                    'status' => 'invalid',
                    'normalized_payload' => $validation['data'],
                    'validation_errors' => $validation['errors'],
                    'error' => 'Validation failed again before publication.',
                ]);

                return null;
            }

            /** @var array{external_id: string, sku?: string, mpn?: string, manufacturer?: string, name: string, slug: string, technical_attributes?: array<string, string>} $data */
            $data = $validation['data'];
            $product = $this->identityGuard->findByExternalId($data);

            try {
                $this->identityGuard->assertCanPersist($data, $product);
            } catch (ProductIdentityConflict $conflict) {
                $this->recordIdentityConflict($record, $conflict);
                $identityConflict = $conflict;

                return null;
            }

            $productBefore = $product?->only(['external_id', 'sku', 'mpn', 'manufacturer', 'name', 'slug', 'technical_attributes', 'status']);

            $product ??= new Product;
            $product->fill([...$data, 'status' => 'active']);
            $product->save();

            $conflictingSiteProduct = SiteProduct::query()
                ->where('site_id', $site->id)
                ->where('slug', $product->slug)
                ->where('product_id', '!=', $product->id)
                ->exists();

            if ($conflictingSiteProduct) {
                throw new DomainException('This site already uses the proposed URL slug for a different product. Resolve the URL conflict before publishing.');
            }

            $siteProduct = SiteProduct::query()->firstOrCreate(
                ['site_id' => $site->id, 'product_id' => $product->id],
                [
                    'slug' => $product->slug,
                    'is_published' => false,
                    'availability' => 'on_request',
                ],
            );

            $record->update([
                'status' => 'published',
                'published_by' => $publisher?->id,
                'published_product_id' => $product->id,
                'published_site_id' => $site->id,
                'published_at' => now(),
                'publication_snapshot' => [
                    'product_before' => $productBefore,
                    'product_after' => $product->only(['external_id', 'sku', 'mpn', 'manufacturer', 'name', 'slug', 'technical_attributes', 'status']),
                    'site_product' => $siteProduct->only(['id', 'site_id', 'product_id', 'slug', 'availability', 'is_published']),
                    'publicly_visible' => false,
                ],
            ]);

            return $record->refresh();
        });

        if ($identityConflict !== null) {
            throw $identityConflict;
        }

        if ($publishedRecord === null) {
            throw new DomainException('The staged record no longer passes validation. Review the errors before publishing.');
        }

        return $publishedRecord;
    }

    private function recordIdentityConflict(StagedImportRecord $record, ProductIdentityConflict $conflict): void
    {
        DuplicateConflict::query()->firstOrCreate(
            [
                'import_run_id' => $record->import_run_id,
                'entity_type' => 'product',
                'match_key' => $conflict->matchKey,
                'status' => 'open',
            ],
            [
                'candidate_ids' => [
                    'staged_record_ids' => [$record->id],
                    'product_ids' => $conflict->productIds,
                ],
            ],
        );

        $record->update([
            'status' => 'duplicate',
            'error' => "Duplicate conflict: {$conflict->matchKey}.",
        ]);
    }

    private function assertCanBeReviewed(StagedImportRecord $record): void
    {
        if ($record->status !== 'ready_for_review') {
            throw new DomainException('Only a valid record that has not yet been reviewed can be approved.');
        }

        $this->assertNoOpenConflict($record);
    }

    private function assertCanBePublished(StagedImportRecord $record): void
    {
        if ($record->status !== 'reviewed' || $record->reviewed_at === null) {
            throw new DomainException('A valid staged record must be explicitly reviewed before it can be published.');
        }

        $this->assertNoOpenConflict($record);
    }

    private function assertNoOpenConflict(StagedImportRecord $record): void
    {
        $hasConflict = DuplicateConflict::query()
            ->where('import_run_id', $record->import_run_id)
            ->where('status', 'open')
            ->whereJsonContains('candidate_ids->staged_record_ids', $record->id)
            ->exists();

        if ($hasConflict) {
            throw new DomainException('Resolve the duplicate conflict before approving or publishing this record.');
        }
    }
}
