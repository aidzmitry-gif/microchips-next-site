<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\ImportRun;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteCategoryProduct;
use App\Models\SiteProduct;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class AssignSiteProductCategoriesTest extends TestCase
{
    use RefreshDatabase;

    public function test_dry_run_validates_without_writing_assignments_or_chemistry_attributes(): void
    {
        $site = $this->site('microchips-by');
        $siteProduct = $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $agmCategory = $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,AGM
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
        ])->assertSuccessful();

        $this->assertDatabaseCount('site_category_product', 0);
        $this->assertNull($siteProduct->fresh()->product->technical_attributes['chemistry'] ?? null);
        $run = ImportRun::query()->sole();
        $this->assertSame('dry_run_complete', $run->status);
        // D5: a dry run must never look "processed" even though validation
        // passed and would-be counters are populated for preview purposes.
        $this->assertSame(0, $run->processed_records);
        $this->assertSame(1, $run->summary['accepted_records']);
        $this->assertSame(1, $run->summary['assignments_created']);
        $this->assertSame(1, $run->summary['chemistry_attributes_set']);
        $this->assertSame(0, $run->summary['is_published_changed']);
        $this->assertNotNull($agmCategory);
    }

    public function test_apply_creates_assignment_sets_chemistry_attribute_and_never_publishes(): void
    {
        $site = $this->site('microchips-by');
        $siteProduct = $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $agmCategory = $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,AGM
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertSuccessful();

        $pivot = SiteCategoryProduct::query()->sole();
        $this->assertSame($agmCategory->id, $pivot->site_category_id);
        $this->assertSame($siteProduct->id, $pivot->site_product_id);
        $this->assertSame($site->id, $pivot->site_id);

        $attributes = $siteProduct->product->fresh()->technical_attributes;
        $this->assertSame('AGM', $attributes['chemistry']);
        // D2 (honesty fix): the provenance marker must say only what actually
        // happened -- the value came from this CSV's chemistry column -- and
        // must NOT claim it was "derived" from category placement or checked
        // against it, since this class never performs that comparison.
        $this->assertSame('operator_supplied_csv_column', $attributes['chemistry_provenance']['source']);
        $this->assertArrayNotHasKey('confidence', $attributes['chemistry_provenance']);
        $this->assertFalse($siteProduct->fresh()->is_published);

        // D3: per-product before/after audit trail on the ImportRun.
        $run = ImportRun::query()->sole();
        $this->assertSame(1, $run->processed_records);
        $update = collect($run->summary['chemistry_updates'])->sole();
        $this->assertSame('acb-1', $update['product_external_id']);
        $this->assertNull($update['before']['chemistry']);
        $this->assertSame('AGM', $update['after']['chemistry']);

        // D4: identifiers of the created site_category_product link(s) on the
        // ImportRun, not just a count -- an erroneous run must be traceable
        // back to specific rows from the log alone.
        $creation = collect($run->summary['assignment_creations'])->sole();
        $this->assertSame($pivot->id, $creation['site_category_product_id']);
        $this->assertSame($agmCategory->id, $creation['site_category_id']);
        $this->assertSame($siteProduct->id, $creation['site_product_id']);
        $this->assertSame('acb-1', $creation['product_external_id']);
        $this->assertSame('agm', $creation['category_external_id']);

        // D4 (prior): the cross-site, canonical-table nature of the write
        // must be explicit in the summary, not only in the class docblock.
        $this->assertTrue($run->summary['writes_canonical_product_attributes']);
        $this->assertIsString($run->summary['canonical_write_note']);
        $this->assertStringContainsString('products table', $run->summary['canonical_write_note']);
    }

    public function test_apply_is_idempotent_and_does_not_duplicate_assignments_or_re_touch_chemistry(): void
    {
        $site = $this->site('microchips-by');
        $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,AGM
CSV);
        $arguments = ['site' => $site->key, 'file' => $file, '--apply' => true];

        $this->artisan('catalog:assign-site-product-categories', $arguments)->assertSuccessful();
        $this->artisan('catalog:assign-site-product-categories', $arguments)->assertSuccessful();

        $this->assertSame(1, SiteCategoryProduct::query()->count());
        $latestRun = ImportRun::query()->latest('id')->firstOrFail();
        $this->assertSame(0, $latestRun->summary['assignments_created']);
        $this->assertSame(1, $latestRun->summary['assignments_unchanged']);
        $this->assertSame(0, $latestRun->summary['chemistry_attributes_set']);
        $this->assertSame(1, $latestRun->summary['chemistry_attributes_unchanged']);
        $this->assertSame([], $latestRun->summary['chemistry_updates']);
        $this->assertSame([], $latestRun->summary['assignment_creations']);
    }

    public function test_preserves_chemistry_as_a_structural_attribute_alongside_the_specific_category_not_a_generic_one(): void
    {
        $site = $this->site('microchips-by');
        $agmProduct = $this->stagedSiteProduct($site, 'acb-agm', 'agm-battery');
        $gelProduct = $this->stagedSiteProduct($site, 'acb-gel', 'gel-battery');
        $agmCategory = $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $gelCategory = $this->siteCategory($site, 'gel', 'Гелевые АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-agm,agm,AGM
acb-gel,gel,GEL
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertSuccessful();

        $this->assertSame($agmCategory->id, $agmProduct->categories()->sole()->id);
        $this->assertSame($gelCategory->id, $gelProduct->categories()->sole()->id);
        $this->assertSame('AGM', $agmProduct->product->fresh()->technical_attributes['chemistry']);
        $this->assertSame('GEL', $gelProduct->product->fresh()->technical_attributes['chemistry']);
    }

    public function test_lowercase_and_mixed_case_chemistry_values_are_case_normalized(): void
    {
        $site = $this->site('microchips-by');
        $siteProduct = $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,agm
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertSuccessful();

        $this->assertSame('AGM', $siteProduct->product->fresh()->technical_attributes['chemistry']);
    }

    public function test_a_chemistry_value_outside_the_agm_gel_enum_blocks_the_run(): void
    {
        $site = $this->site('microchips-by');
        $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,АГМ
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertFailed();

        $this->assertDatabaseCount('site_category_product', 0);
        $reasons = collect(ImportRun::query()->sole()->summary['validation_errors'])->pluck('reason')->all();
        $this->assertContains('invalid_chemistry_value', $reasons);
    }

    public function test_csv_value_conflicting_with_a_previously_confirmed_chemistry_attribute_blocks_the_run(): void
    {
        $site = $this->site('microchips-by');
        $siteProduct = $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        // Simulate a value confirmed by the staging pipeline (no provenance
        // marker => treated as a trusted, confirmed source, per StageProductValidator).
        $product = $siteProduct->product;
        $product->technical_attributes = ['chemistry' => 'GEL'];
        $product->save();
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,AGM
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertFailed();

        $this->assertDatabaseCount('site_category_product', 0);
        $reasons = collect(ImportRun::query()->sole()->summary['validation_errors'])->pluck('reason')->all();
        $this->assertContains('chemistry_conflict_with_confirmed_attribute', $reasons);
        $this->assertSame('GEL', $product->fresh()->technical_attributes['chemistry']);
    }

    public function test_a_correction_to_a_value_this_tool_previously_set_is_allowed_to_overwrite(): void
    {
        $site = $this->site('microchips-by');
        $siteProduct = $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $this->siteCategory($site, 'gel', 'Гелевые АКБ для ИБП');
        $firstFile = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,AGM
CSV);
        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $firstFile,
            '--apply' => true,
        ])->assertSuccessful();
        $this->assertSame('AGM', $siteProduct->product->fresh()->technical_attributes['chemistry']);

        $correctionFile = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,gel,GEL
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $correctionFile,
            '--apply' => true,
        ])->assertSuccessful();

        $attributes = $siteProduct->product->fresh()->technical_attributes;
        $this->assertSame('GEL', $attributes['chemistry']);
        $this->assertSame('operator_supplied_csv_column', $attributes['chemistry_provenance']['source']);
    }

    public function test_a_technology_value_longer_than_255_characters_blocks_the_run_instead_of_being_silently_dropped(): void
    {
        // Round-2 regression: clean() collapsed both "absent" and "too long"
        // to null, so an oversized garbage value used to be treated as "no
        // technology column supplied" and the run completed cleanly.
        $site = $this->site('microchips-by');
        $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(
            "product_external_id,category_external_id,technology\nacb-1,agm,".str_repeat('A', 260)."\n"
        );

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertFailed();

        $this->assertDatabaseCount('site_category_product', 0);
        $reasons = collect(ImportRun::query()->sole()->summary['validation_errors'])->pluck('reason')->all();
        $this->assertContains('invalid_chemistry_value', $reasons);
    }

    public function test_a_case_only_difference_from_a_confirmed_chemistry_value_does_not_block_the_run_or_rewrite_it(): void
    {
        // Round-2 regression: the cross-check compared the CSV's normalized
        // (uppercase) value against the confirmed value's RAW case, so a
        // confirmed 'agm' (lowercase, as staging might store it) plus a CSV
        // 'AGM' produced a false chemistry_conflict_with_confirmed_attribute.
        $site = $this->site('microchips-by');
        $siteProduct = $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $product = $siteProduct->product;
        $product->technical_attributes = ['chemistry' => 'agm'];
        $product->save();
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,AGM
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertSuccessful();

        $this->assertSame(1, SiteCategoryProduct::query()->count());
        // The confirmed value is left exactly as it was -- not overwritten,
        // not re-tagged with this tool's provenance marker.
        $attributes = $product->fresh()->technical_attributes;
        $this->assertSame('agm', $attributes['chemistry']);
        $this->assertArrayNotHasKey('chemistry_provenance', $attributes);
    }

    public function test_unknown_category_product_and_duplicate_rows_block_all_writes_with_audit_details(): void
    {
        $site = $this->site('microchips-by');
        $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,AGM
acb-1,agm,AGM
acb-missing,agm,AGM
acb-1,missing-category,AGM
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
        ])->assertFailed();

        $this->assertDatabaseCount('site_category_product', 0);
        $run = ImportRun::query()->sole();
        $this->assertSame('needs_review', $run->status);
        $reasons = collect($run->summary['validation_errors'])->pluck('reason')->all();
        $this->assertContains('duplicate_assignment_row', $reasons);
        $this->assertContains('unknown_product', $reasons);
        $this->assertContains('unknown_category', $reasons);
    }

    public function test_product_not_yet_linked_to_the_site_blocks_the_run_instead_of_creating_a_site_product(): void
    {
        $site = $this->site('microchips-by');
        Product::create(['external_id' => 'acb-1', 'slug' => 'agm-battery', 'name' => 'AGM Battery', 'status' => 'active']);
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,AGM
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertFailed();

        $this->assertDatabaseCount('site_products', 0);
        $this->assertDatabaseCount('site_category_product', 0);
        $reasons = collect(ImportRun::query()->sole()->summary['validation_errors'])->pluck('reason')->all();
        $this->assertContains('product_not_linked_to_site', $reasons);
    }

    public function test_a_category_that_belongs_to_a_different_site_is_treated_as_unknown_not_cross_linked(): void
    {
        $belarus = $this->site('microchips-by');
        $russia = $this->site('microchips-ru');
        $this->stagedSiteProduct($belarus, 'acb-1', 'agm-battery');
        $this->siteCategory($russia, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,AGM
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $belarus->key,
            'file' => $file,
            '--apply' => true,
        ])->assertFailed();

        $this->assertDatabaseCount('site_category_product', 0);
        $reasons = collect(ImportRun::query()->sole()->summary['validation_errors'])->pluck('reason')->all();
        $this->assertContains('unknown_category', $reasons);
    }

    public function test_conflicting_chemistry_values_for_the_same_product_within_one_csv_block_the_run(): void
    {
        $site = $this->site('microchips-by');
        $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $this->siteCategory($site, 'gel', 'Гелевые АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,AGM
acb-1,gel,GEL
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertFailed();

        $this->assertDatabaseCount('site_category_product', 0);
        $reasons = collect(ImportRun::query()->sole()->summary['validation_errors'])->pluck('reason')->all();
        $this->assertContains('chemistry_conflict_in_csv', $reasons);
    }

    public function test_assignment_without_a_technology_column_only_links_the_category(): void
    {
        $site = $this->site('microchips-by');
        $siteProduct = $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id
acb-1,agm
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertSuccessful();

        $this->assertSame(1, SiteCategoryProduct::query()->count());
        $this->assertNull($siteProduct->product->fresh()->technical_attributes['chemistry'] ?? null);
    }

    public function test_an_unrecognized_column_header_blocks_the_run_instead_of_being_silently_ignored(): void
    {
        // D3 regression: a column like 'Тип' with a value of 'ГЕЛЬ' used to
        // be accepted and simply never read anywhere -- the run completed
        // with exit=0 and no errors, silently discarding an operator's data.
        $site = $this->site('microchips-by');
        $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,Тип
acb-1,agm,ГЕЛЬ
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertFailed();

        $this->assertDatabaseCount('site_category_product', 0);
        $run = ImportRun::query()->sole();
        $this->assertSame('failed', $run->status);
        $this->assertStringContainsString('Unrecognized column header', $run->summary['error']);
    }

    public function test_an_empty_string_existing_chemistry_attribute_is_treated_as_absent_not_confirmed(): void
    {
        // D5 regression: an existing 'chemistry' => '' (e.g. a staging
        // pipeline that wrote an empty placeholder) used to be treated as a
        // genuine confirmed value, falsely conflicting with any CSV value and
        // blocking the whole run.
        $site = $this->site('microchips-by');
        $siteProduct = $this->stagedSiteProduct($site, 'acb-1', 'agm-battery');
        $product = $siteProduct->product;
        $product->technical_attributes = ['chemistry' => ''];
        $product->save();
        $this->siteCategory($site, 'agm', 'AGM АКБ для ИБП');
        $file = $this->csv(<<<'CSV'
product_external_id,category_external_id,technology
acb-1,agm,AGM
CSV);

        $this->artisan('catalog:assign-site-product-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertSuccessful();

        $this->assertSame('AGM', $product->fresh()->technical_attributes['chemistry']);
    }

    private function site(string $key): Site
    {
        return Site::create([
            'key' => $key,
            'domain' => $key.'.test',
            'country_code' => $key === 'microchips-by' ? 'BY' : 'RU',
            'currency_code' => $key === 'microchips-by' ? 'BYN' : 'RUB',
            'default_locale' => $key === 'microchips-by' ? 'ru-BY' : 'ru-RU',
            'name' => $key,
        ]);
    }

    private function stagedSiteProduct(Site $site, string $externalId, string $slug): SiteProduct
    {
        $product = Product::create([
            'external_id' => $externalId,
            'slug' => $slug,
            'name' => $slug,
            'status' => 'active',
        ]);

        return SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => $slug,
            'is_published' => false,
            'availability' => 'on_request',
        ]);
    }

    private function siteCategory(Site $site, string $externalId, string $name): SiteCategory
    {
        $category = Category::create(['slug' => $externalId.'-'.$site->id, 'name' => $name]);

        return SiteCategory::create([
            'site_id' => $site->id,
            'source' => 'bitrix_sections',
            'external_id' => $externalId,
            'category_id' => $category->id,
            'slug' => 'catalog/akkumulyatory/dlya-ibp/'.$externalId,
            'name' => $name,
            'is_published' => false,
        ]);
    }

    private function csv(string $contents): string
    {
        $file = storage_path('framework/testing/assign-categories-'.uniqid().'.csv');
        file_put_contents($file, $contents);

        return $file;
    }
}
