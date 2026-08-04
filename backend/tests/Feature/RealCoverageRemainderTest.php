<?php

namespace Tests\Feature;

use App\Domain\Imports\StagedProductPublisher;
use App\Domain\Imports\StageProductValidator;
use App\Models\Category;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use App\Models\StagedImportRecord;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * Closes the last genuinely-real uncovered branches identified from the CI
 * clover report (SiteResolver not-found payloads, two StageProductValidator
 * required-field errors, the publisher review-status guard). Model relation
 * one-liners and unreachable defensive branches are intentionally left out.
 */
class RealCoverageRemainderTest extends TestCase
{
    use RefreshDatabase;

    public function test_resolve_returns_not_found_when_a_product_url_points_to_an_unpublished_site_product(): void
    {
        $site = $this->site();
        $product = Product::create(['sku' => 'X-1', 'name' => 'Hidden', 'slug' => 'hidden', 'status' => 'active']);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id, 'product_id' => $product->id, 'slug' => 'hidden',
            'is_published' => false, 'availability' => 'on_request', 'price' => '1.00',
        ]);
        SiteUrl::create(['site_id' => $site->id, 'path' => '/catalog/hidden', 'locale' => 'ru-BY', 'target_type' => 'product', 'target_id' => $siteProduct->id]);

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/catalog/hidden')
            ->assertOk()
            ->assertJsonPath('kind', 'not_found');
    }

    public function test_resolve_returns_not_found_when_a_page_url_points_to_a_missing_page(): void
    {
        $site = $this->site();
        SiteUrl::create(['site_id' => $site->id, 'path' => '/o-kompanii', 'locale' => 'ru-BY', 'target_type' => 'page', 'target_id' => 999999]);

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/o-kompanii')
            ->assertOk()
            ->assertJsonPath('kind', 'not_found');
    }

    public function test_resolve_returns_not_found_when_a_category_url_points_to_an_unpublished_category(): void
    {
        $site = $this->site();
        $category = Category::create(['slug' => 'c', 'name' => 'C', 'sort_order' => 1]);
        $siteCategory = SiteCategory::create([
            'site_id' => $site->id, 'category_id' => $category->id, 'slug' => 'skrytaya',
            'name' => 'Скрытая', 'is_published' => false, 'sort_order' => 1,
        ]);
        SiteUrl::create(['site_id' => $site->id, 'path' => '/catalog/skrytaya', 'locale' => 'ru-BY', 'target_type' => 'category', 'target_id' => $siteCategory->id]);

        $this->getJson('/api/v1/sites/microchips.by/resolve?path=/catalog/skrytaya')
            ->assertOk()
            ->assertJsonPath('kind', 'not_found');
    }

    public function test_validator_flags_a_missing_external_id(): void
    {
        $result = (new StageProductValidator)->normalizeAndValidate(['name' => 'No 1C id', 'sku' => 'S-1']);

        $this->assertArrayHasKey('external_id', $result['errors']);
    }

    public function test_validator_flags_a_row_with_neither_sku_nor_mpn(): void
    {
        $result = (new StageProductValidator)->normalizeAndValidate(['name' => 'No identifier']);

        $this->assertArrayHasKey('identifier', $result['errors']);
    }

    public function test_a_record_that_is_not_ready_for_review_cannot_be_reviewed(): void
    {
        $run = ImportRun::create(['source' => '1c_csv', 'status' => 'ready_for_review']);
        $record = StagedImportRecord::create([
            'import_run_id' => $run->id,
            'row_number' => 2,
            'entity_type' => 'product',
            'external_id' => '1c-x',
            'payload' => ['external_id' => '1c-x', 'name' => 'X', 'sku' => 'X-1'],
            'normalized_payload' => ['external_id' => '1c-x', 'name' => 'X', 'sku' => 'X-1', 'slug' => 'x'],
            'validation_errors' => [],
            'status' => 'invalid',
        ]);

        $this->expectException(DomainException::class);
        $this->expectExceptionMessage('has not yet been reviewed');

        app(StagedProductPublisher::class)->review($record, null);
    }

    private function site(): Site
    {
        return Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips.by', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'microchips-by', 'is_active' => true,
        ]);
    }
}
