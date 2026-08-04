<?php

namespace Tests\Feature;

use App\Events\SiteContentChanged;
use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\Artisan;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Event;
use Tests\TestCase;

class RecoverWave133SiteProductsTest extends TestCase
{
    use RefreshDatabase;

    private string $snapshotPath;

    protected function setUp(): void
    {
        parent::setUp();
        Event::fake([SiteContentChanged::class]);
        $this->snapshotPath = base_path('../docs/audits/generated/rb-applied-site-product-state-wave133.json');
        $this->seedSiteAndSnapshotCategories();
    }

    public function test_recovery_is_guarded_unpublished_idempotent_and_conflict_refusing(): void
    {
        $this->assertSame(
            '19cadbd298f6326e8675e0b834730af7f198a203e05ec55027f554eabf408985',
            hash_file('sha256', $this->snapshotPath),
        );

        $exit = Artisan::call('catalog:recover-wave133-site-products', [
            'site' => 'microchips-by', 'file' => $this->snapshotPath,
        ]);
        $this->assertSame(0, $exit, Artisan::output());
        $this->assertDatabaseCount('products', 0);
        $this->assertDatabaseCount('site_products', 0);
        $this->assertDatabaseCount('site_category_product', 0);

        $exit = Artisan::call('catalog:recover-wave133-site-products', [
            'site' => 'microchips-by', 'file' => $this->snapshotPath, '--apply' => true,
        ]);
        $this->assertSame(0, $exit, Artisan::output());

        $this->assertDatabaseCount('products', 558);
        $this->assertDatabaseCount('site_products', 558);
        $this->assertDatabaseCount('site_category_product', 558);
        $this->assertDatabaseCount('site_urls', 0);
        $this->assertSame(0, DB::table('site_products')->where('is_published', true)->count());
        $this->assertSame(0, DB::table('site_products')->whereNotNull('price')->count());
        $this->assertSame(0, DB::table('site_products')->whereNotNull('seo')->count());
        $this->assertSnapshotContentWasPreserved();

        $exit = Artisan::call('catalog:recover-wave133-site-products', [
            'site' => 'microchips-by', 'file' => $this->snapshotPath, '--apply' => true,
        ]);
        $this->assertSame(0, $exit, Artisan::output());
        $this->assertDatabaseCount('products', 558);
        $this->assertDatabaseCount('site_products', 558);
        $this->assertDatabaseCount('site_category_product', 558);

        $first = Product::query()->orderBy('id')->firstOrFail();
        $first->name = 'conflicting recovery name';
        $first->saveQuietly();
        $exit = Artisan::call('catalog:recover-wave133-site-products', [
            'site' => 'microchips-by', 'file' => $this->snapshotPath, '--apply' => true,
        ]);
        $this->assertSame(1, $exit);
        $this->assertDatabaseCount('products', 558);
        $this->assertDatabaseCount('site_products', 558);
        $this->assertDatabaseCount('site_category_product', 558);
    }

    public function test_recovery_refuses_wrong_site_and_any_snapshot_hash_drift(): void
    {
        $exit = Artisan::call('catalog:recover-wave133-site-products', [
            'site' => 'wrong-site', 'file' => $this->snapshotPath,
        ]);
        $this->assertSame(1, $exit);
        $this->assertDatabaseCount('products', 0);

        $tampered = tempnam(sys_get_temp_dir(), 'wave133-tampered-');
        $this->assertNotFalse($tampered);
        file_put_contents($tampered, (string) file_get_contents($this->snapshotPath)."\n");
        try {
            $exit = Artisan::call('catalog:recover-wave133-site-products', [
                'site' => 'microchips-by', 'file' => $tampered,
            ]);
            $this->assertSame(1, $exit);
            $this->assertDatabaseCount('products', 0);
        } finally {
            unlink($tampered);
        }
    }

    private function seedSiteAndSnapshotCategories(): void
    {
        $site = Site::create([
            'key' => 'microchips-by', 'domain' => 'microchips-by.test', 'country_code' => 'BY',
            'currency_code' => 'BYN', 'default_locale' => 'ru-BY', 'name' => 'RB', 'is_active' => true,
        ]);
        $rows = json_decode((string) file_get_contents($this->snapshotPath), true, 512, JSON_THROW_ON_ERROR);
        $categories = [];
        foreach ($rows as $row) {
            $category = $row['categories'][0];
            $categories[$category['external_id']] = $category;
        }
        foreach (array_values($categories) as $offset => $source) {
            $category = Category::create([
                'slug' => 'wave133-recovery-category-'.$offset,
                'name' => $source['name'],
                'sort_order' => $source['sort_order'],
            ]);
            SiteCategory::create([
                'site_id' => $site->id,
                'category_id' => $category->id,
                'source' => $source['source'],
                'external_id' => $source['external_id'],
                'slug' => $source['slug'],
                'name' => $source['name'],
                'seo' => null,
                'is_published' => false,
                'sort_order' => $source['sort_order'],
            ]);
        }
    }

    private function assertSnapshotContentWasPreserved(): void
    {
        $rows = json_decode((string) file_get_contents($this->snapshotPath), true, 512, JSON_THROW_ON_ERROR);
        foreach ($rows as $row) {
            $source = $row['product'];
            $product = Product::query()->where('external_id', $source['external_id'])->sole();
            $this->assertSame($source['sku'], $product->sku);
            $this->assertSame($source['mpn'], $product->mpn);
            $this->assertSame($source['manufacturer'], $product->manufacturer);
            $this->assertSame($source['slug'], $product->slug);
            $this->assertSame($source['name'], $product->name);
            $this->assertSame($source['short_description'], $product->short_description);
            $this->assertSame($source['technical_attributes'], $product->technical_attributes);
            $siteProduct = $product->sites()->sole();
            $this->assertSame($row['slug'], $siteProduct->slug);
            $this->assertFalse($siteProduct->is_published);
            $this->assertNull($siteProduct->price);
            $this->assertSame($row['categories'][0]['external_id'], $siteProduct->categories()->sole()->external_id);
        }
    }
}
