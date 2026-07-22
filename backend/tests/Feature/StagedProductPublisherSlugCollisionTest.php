<?php

namespace Tests\Feature;

use App\Domain\Imports\StagedProductPublisher;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use DomainException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class StagedProductPublisherSlugCollisionTest extends TestCase
{
    use RefreshDatabase;

    public function test_publishing_is_blocked_when_the_proposed_slug_is_already_used_by_a_different_product_on_the_site(): void
    {
        $site = $this->site();

        $existingProduct = Product::create([
            'external_id' => '1c-alpha',
            'sku' => 'ALPHA-01',
            'name' => 'Alpha Battery',
            'slug' => 'alpha-battery',
            'status' => 'active',
        ]);

        SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $existingProduct->id,
            'slug' => 'shared-slug',
            'is_published' => false,
            'availability' => 'on_request',
        ]);

        $record = $this->stagedRecordWithSlug('shared-slug');

        $publisher = app(StagedProductPublisher::class);
        $publisher->review($record, null);

        try {
            $publisher->publishToSite($record, $site, null);
            $this->fail('Publishing must be blocked when the slug is already used by a different product on this site.');
        } catch (DomainException $exception) {
            $this->assertStringContainsString('slug', $exception->getMessage());
        }

        $this->assertDatabaseHas('staged_import_records', [
            'id' => $record->id,
            'status' => 'reviewed',
        ]);
        $this->assertDatabaseCount('products', 1);
        $this->assertDatabaseMissing('products', [
            'external_id' => '1c-beta',
        ]);
        $this->assertDatabaseCount('site_products', 1);
    }

    private function stagedRecordWithSlug(string $slug): StagedImportRecord
    {
        $run = ImportRun::create(['source' => '1c_csv', 'status' => 'ready_for_review']);

        return StagedImportRecord::create([
            'import_run_id' => $run->id,
            'row_number' => 2,
            'entity_type' => 'product',
            'external_id' => '1c-beta',
            'payload' => [
                'external_id' => '1c-beta',
                'name' => 'Beta Battery',
                'sku' => 'BETA-01',
                'slug' => $slug,
            ],
            'normalized_payload' => [
                'external_id' => '1c-beta',
                'name' => 'Beta Battery',
                'sku' => 'BETA-01',
                'slug' => $slug,
            ],
            'validation_errors' => [],
            'status' => 'ready_for_review',
        ]);
    }

    private function site(): Site
    {
        return Site::create([
            'key' => 'microchips-by',
            'domain' => 'microchips.by',
            'country_code' => 'BY',
            'currency_code' => 'BYN',
            'default_locale' => 'ru-BY',
            'name' => 'Microchips Belarus',
            'is_active' => true,
        ]);
    }
}
