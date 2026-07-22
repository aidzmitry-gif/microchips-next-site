<?php

namespace Tests\Feature;

use App\Domain\Content\ProductDescriptionDrafter;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\StagedImportRecord;
use App\Models\User;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ProductDescriptionDraftWorkflowTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_creates_a_non_published_draft_from_verified_facts_and_sources(): void
    {
        $product = Product::create([
            'external_id' => '1c-100',
            'sku' => 'FGL120',
            'slug' => 'fiamm-12fgl120',
            'name' => 'Fiamm 12FGL120',
            'short_description' => null,
            'status' => 'active',
        ]);

        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'Fiamm 12FGL120',
            'manufacturer' => 'Fiamm',
            'technology' => 'AGM',
            'technical_attributes' => ['voltage' => '12 V', 'capacity' => '120 Ah'],
        ], ['https://example.test/1c/products/1c-100'], $product);

        $this->assertSame('draft', $draft->status);
        $this->assertStringContainsString('AGM', $draft->content);
        $this->assertStringContainsString('voltage: 12 V', $draft->content);
        $this->assertSame(['https://example.test/1c/products/1c-100'], $draft->source_urls);
        $this->assertNull($product->refresh()->short_description);
    }

    public function test_title_only_data_is_persisted_as_rejected_with_a_reason(): void
    {
        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'Battery KM-300 P',
            'sku' => 'KM-300-P',
        ], ['https://example.test/catalog/km-300-p']);

        $this->assertSame('rejected', $draft->status);
        $this->assertNull($draft->content);
        $this->assertStringContainsString('Title-only', $draft->rejection_reason);
    }

    public function test_missing_or_invalid_source_url_is_rejected(): void
    {
        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'Battery A',
            'technology' => 'GEL',
        ], ['relative/catalog/a', 'ftp://example.test/a']);

        $this->assertSame('rejected', $draft->status);
        $this->assertStringContainsString('source URL', $draft->rejection_reason);
    }

    public function test_unapproved_top_level_fields_are_rejected_instead_of_being_written(): void
    {
        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'Battery A',
            'technology' => 'AGM',
            'guaranteed_savings' => '50%',
        ], ['https://example.test/catalog/a']);

        $this->assertSame('rejected', $draft->status);
        $this->assertStringContainsString('guaranteed_savings', $draft->rejection_reason);
        $this->assertNull($draft->content);
    }

    public function test_a_draft_can_be_submitted_for_review_but_not_published(): void
    {
        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'Battery A',
            'technology' => 'LiFePO4',
        ], ['https://example.test/catalog/a']);
        $user = User::factory()->create();

        $submitted = app(ProductDescriptionDrafter::class)->submitForReview($draft, $user);

        $this->assertSame('review', $submitted->status);
        $this->assertSame($user->id, $submitted->submitted_by);
        $this->assertNotNull($submitted->submitted_at);
        $this->assertDatabaseCount('products', 0);

        $this->expectException(DomainException::class);
        app(ProductDescriptionDrafter::class)->submitForReview($submitted, $user);
    }

    public function test_a_duplicate_import_record_cannot_receive_a_migrated_description(): void
    {
        $run = ImportRun::create(['source' => '1c_csv', 'status' => 'needs_review']);
        $duplicate = StagedImportRecord::create([
            'import_run_id' => $run->id,
            'row_number' => 2,
            'entity_type' => 'product',
            'external_id' => '1c-duplicate',
            'payload' => ['external_id' => '1c-duplicate', 'name' => 'Duplicate Battery'],
            'normalized_payload' => ['external_id' => '1c-duplicate', 'name' => 'Duplicate Battery'],
            'status' => 'duplicate',
            'error' => 'Duplicate conflict: mpn:duplicate-battery.',
        ]);

        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'Duplicate Battery',
            'technology' => 'AGM',
        ], ['https://manufacturer.example.test/duplicate-battery'], null, $duplicate);

        $this->assertSame('rejected', $draft->status);
        $this->assertNull($draft->content);
        $this->assertStringContainsString('duplicate catalogue record', $draft->rejection_reason);
    }
}
