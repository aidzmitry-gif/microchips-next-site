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

    public function test_a_technical_attribute_carrying_a_provenance_marker_is_never_printed_as_confirmed(): void
    {
        // Round-2 regression: if a Product's raw technical_attributes
        // (including a `chemistry_provenance` marker set by
        // SiteProductCategoryAssigner) is ever passed through wholesale, the
        // composer must not label the derived fact "Подтверждённые
        // характеристики" alongside genuinely operator-verified facts.
        $product = Product::create([
            'external_id' => '1c-101',
            'sku' => 'RBC-124',
            'slug' => 'rbc-124',
            'name' => 'RBC 124',
            'status' => 'active',
        ]);

        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'RBC 124',
            'technical_attributes' => [
                'voltage' => '12 В',
                'chemistry' => 'AGM',
                'chemistry_provenance' => [
                    'source' => 'site_product_category_assignment_csv',
                    'confidence' => 'derived_from_category',
                ],
            ],
        ], ['https://example.test/1c/products/1c-101'], $product);

        $this->assertSame('draft', $draft->status);
        $this->assertStringContainsString('voltage: 12 В', $draft->content);
        $this->assertStringNotContainsString('chemistry: AGM', $draft->content);
        $this->assertStringNotContainsString('chemistry_provenance', $draft->content);
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

    public function test_it_dereferences_a_clean_internal_bitrix_link_in_verified_fields(): void
    {
        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'APC RBC124 12V/9Ah',
            'manufacturer' => 'APC',
            'technology' => 'AGM',
            'applications' => [
                '<p>Подходит для <a href="/catalog/akkumulyatory/dlya_ibp/agm/123/">ИБП APC</a>.</p>',
            ],
        ], ['https://example.test/1c/products/apc-rbc124']);

        $this->assertSame('draft', $draft->status);

        $normalizedApplication = $draft->verified_fields['applications'][0];
        $this->assertStringNotContainsString('<a', $normalizedApplication);
        $this->assertStringNotContainsString('/catalog/', $normalizedApplication);
        $this->assertStringContainsString('<p>Подходит для ИБП APC.</p>', $normalizedApplication);

        // The audit trail records what the normalizer changed, for editorial review.
        $this->assertSame(1, $draft->verified_fields['_sanitization']['links_dereferenced']);
        $this->assertSame(0, $draft->verified_fields['_sanitization']['needs_manual_review']);
        $this->assertSame(0, $draft->verified_fields['_sanitization']['tags_repaired']);

        // The normalizer never fabricates a new-site URL for the dereferenced link.
        $this->assertStringNotContainsString('/catalog/', $draft->content);
    }

    /**
     * DescriptionHtmlNormalizer auto-repairs an unbalanced <p> again (see
     * docs/product-description-draft-workflow.md), but only via a proven
     * safe structural repair: every character of the fragment still appears,
     * in order, in the parser's re-serialization — the round trip only
     * inserted closing-tag syntax, it never removed or rewrote a single
     * original character. The legacy link elsewhere in the same string is
     * dereferenced in the same pass, and both facts are recorded in the
     * audit trail.
     */
    public function test_it_repairs_an_unbalanced_legacy_fragment_and_dereferences_its_legacy_link(): void
    {
        $original = '<p>Подходит для <a href="/catalog/akkumulyatory/dlya_ibp/agm/123/">ИБП APC</a>.'
            .'<p>Поставляется в картонной упаковке.';

        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'APC RBC124 12V/9Ah',
            'manufacturer' => 'APC',
            'technology' => 'AGM',
            'applications' => [$original],
        ], ['https://example.test/1c/products/apc-rbc124']);

        $this->assertSame('draft', $draft->status);
        $this->assertSame(
            '<p>Подходит для ИБП APC.</p><p>Поставляется в картонной упаковке.</p>',
            $draft->verified_fields['applications'][0],
        );
        $this->assertSame(1, $draft->verified_fields['_sanitization']['links_dereferenced']);
        $this->assertSame(0, $draft->verified_fields['_sanitization']['needs_manual_review']);
        $this->assertSame(1, $draft->verified_fields['_sanitization']['tags_repaired']);
    }

    public function test_it_adds_no_sanitization_audit_trail_when_verified_fields_have_no_markup(): void
    {
        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'APC RBC124 12V/9Ah',
            'technology' => 'AGM',
            'applications' => ['ИБП, охранные системы'],
        ], ['https://example.test/1c/products/apc-rbc124']);

        $this->assertSame('draft', $draft->status);
        $this->assertArrayNotHasKey('_sanitization', $draft->verified_fields);
    }

    /**
     * D3 (P1): identity/attribution fields (name, sku, mpn, manufacturer)
     * must never be routed through the HTML normalizer. Before the fix,
     * normalizeValue() recursed into every allowed field including these, so
     * a real SKU/MPN containing "<"/">" (not unheard of in legacy exports)
     * came out entity-escaped — no longer the same identifier.
     */
    public function test_it_never_normalizes_name_sku_mpn_or_manufacturer(): void
    {
        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'RBC<124> replacement',
            'manufacturer' => 'APC<Schneider>',
            'sku' => 'RBC<124>',
            'mpn' => 'RBC<124>-MPN',
            'technology' => 'AGM',
        ], ['https://example.test/1c/products/rbc124']);

        $this->assertSame('draft', $draft->status);
        $this->assertSame('RBC<124> replacement', $draft->verified_fields['name']);
        $this->assertSame('APC<Schneider>', $draft->verified_fields['manufacturer']);
        $this->assertSame('RBC<124>', $draft->verified_fields['sku']);
        $this->assertSame('RBC<124>-MPN', $draft->verified_fields['mpn']);
        $this->assertArrayNotHasKey('_sanitization', $draft->verified_fields);
    }

    /**
     * Exercised through the whole drafting pipeline rather than the
     * normalizer in isolation: a bare "<" used as a comparison operator in a
     * technical_attributes value must survive byte-for-byte untouched (the
     * DOM round trip cannot losslessly reproduce it, so the normalizer
     * leaves it alone) but IS flagged for manual review — the pipeline must
     * not silently swallow that flag either.
     */
    public function test_it_leaves_bare_comparison_operators_in_technical_attributes_untouched_but_flags_manual_review(): void
    {
        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'APC RBC124 12V/9Ah',
            'technology' => 'AGM',
            'technical_attributes' => [
                'self_discharge' => 'Саморазряд <3%/мес',
                'max_charge_current' => 'Ток заряда <max 10A',
            ],
        ], ['https://example.test/1c/products/apc-rbc124']);

        $this->assertSame('draft', $draft->status);
        $this->assertSame('Саморазряд <3%/мес', $draft->verified_fields['technical_attributes']['self_discharge']);
        $this->assertSame('Ток заряда <max 10A', $draft->verified_fields['technical_attributes']['max_charge_current']);
        $this->assertSame(2, $draft->verified_fields['_sanitization']['needs_manual_review']);
        $this->assertSame(0, $draft->verified_fields['_sanitization']['links_dereferenced']);
        $this->assertSame(0, $draft->verified_fields['_sanitization']['tags_repaired']);
        $this->assertStringContainsString('Ток заряда <max 10A', $draft->content);
    }

    /**
     * D6 (P2): the "_rejected_fields" branch used to return the allowed
     * subset of fields straight from Arr::only(), bypassing normalization
     * entirely — a rejected draft's verified_fields was a second, unaudited
     * code path. Both branches must now behave identically for the fields
     * they share: a fragment that cannot be trusted (a bare "<" comparison
     * operator) is left untouched and flagged here too, not repaired on
     * some second code path.
     */
    public function test_the_rejected_fields_branch_flags_an_untrustworthy_fragment_the_same_way_as_the_accepted_branch(): void
    {
        $original = 'Саморазряд <3%/мес';

        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'Battery A',
            'technology' => 'AGM',
            'applications' => [$original],
            'guaranteed_savings' => '50%',
        ], ['https://example.test/catalog/a']);

        $this->assertSame('rejected', $draft->status);
        $this->assertStringContainsString('guaranteed_savings', $draft->rejection_reason);
        $this->assertSame($original, $draft->verified_fields['applications'][0]);
        $this->assertSame(1, $draft->verified_fields['_sanitization']['needs_manual_review']);
        $this->assertSame(0, $draft->verified_fields['_sanitization']['tags_repaired']);
    }

    /**
     * D6 companion: the "_rejected_fields" branch must also apply the
     * auto-repair path identically to the accepted branch — an unbalanced
     * `<p>` is repaired (not merely flagged) regardless of which branch a
     * submission ultimately falls into.
     */
    public function test_the_rejected_fields_branch_repairs_an_unbalanced_paragraph_the_same_way_as_the_accepted_branch(): void
    {
        $original = '<p>Первый абзац.<p>Второй абзац.';

        $draft = app(ProductDescriptionDrafter::class)->createDraft([
            'name' => 'Battery A',
            'technology' => 'AGM',
            'applications' => [$original],
            'guaranteed_savings' => '50%',
        ], ['https://example.test/catalog/a']);

        $this->assertSame('rejected', $draft->status);
        $this->assertSame(
            '<p>Первый абзац.</p><p>Второй абзац.</p>',
            $draft->verified_fields['applications'][0],
        );
        $this->assertSame(0, $draft->verified_fields['_sanitization']['needs_manual_review']);
        $this->assertSame(1, $draft->verified_fields['_sanitization']['tags_repaired']);
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
