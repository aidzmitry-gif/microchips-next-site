<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use Illuminate\Database\QueryException;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Support\Facades\DB;
use LogicException;
use Tests\TestCase;

class SiteCategoryCatalogApiTest extends TestCase
{
    use RefreshDatabase;

    public function test_catalog_can_be_scoped_to_a_category_and_its_descendants(): void
    {
        $site = $this->site('microchips-by');
        [$parent, $child] = $this->categoryTree($site);
        $direct = $this->siteProduct($site, 'DIRECT-1', 'direct');
        $descendant = $this->siteProduct($site, 'CHILD-1', 'child');
        $outside = $this->siteProduct($site, 'OUTSIDE-1', 'outside');
        $parent->products()->attach($direct);
        $child->products()->attach($descendant);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/direct',
            'locale' => 'ru-BY',
            'target_type' => 'product',
            'target_id' => $direct->id,
        ]);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?category=catalog/batteries')
            ->assertOk()
            ->assertJsonCount(2, 'data')
            ->assertJsonPath('meta.total', 2)
            ->assertJsonPath('data.0.path', '/catalog/direct')
            ->assertJsonPath('data.1.path', null)
            ->assertJsonMissing(['slug' => $outside->slug]);
    }

    public function test_public_category_tree_omits_unpublished_categories(): void
    {
        $site = $this->site('microchips-by');
        [$parent, $child] = $this->categoryTree($site);
        $hiddenCanonical = Category::create(['slug' => 'hidden', 'name' => 'Скрытая']);
        SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $hiddenCanonical->id,
            'slug' => 'catalog/hidden',
            'name' => 'Скрытая',
            'is_published' => false,
        ]);

        $this->getJson('/api/v1/sites/microchips-by/catalog/categories')
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.slug', $parent->slug)
            ->assertJsonPath('data.0.children.0.slug', $child->slug)
            ->assertJsonMissing(['slug' => 'catalog/hidden']);
    }

    public function test_pivot_does_not_publish_a_product_or_cross_site_boundaries(): void
    {
        $belarus = $this->site('microchips-by');
        $russia = $this->site('microchips-ru');
        [$category] = $this->categoryTree($belarus);
        $draft = $this->siteProduct($belarus, 'DRAFT-1', 'draft', false);
        $foreign = $this->siteProduct($russia, 'FOREIGN-1', 'foreign');
        $category->products()->attach($draft);

        try {
            $category->products()->attach($foreign);
            $this->fail('Cross-site category attachment must be rejected.');
        } catch (LogicException $error) {
            $this->assertSame('A category can only contain a site product from the same site.', $error->getMessage());
        }

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?category=catalog/batteries')
            ->assertOk()
            ->assertJsonCount(0, 'data');
        $this->assertFalse($draft->fresh()->is_published);
        $this->assertTrue($foreign->fresh()->is_published);
    }

    public function test_database_constraints_prevent_raw_cross_site_pivot_inserts(): void
    {
        $belarus = $this->site('microchips-by');
        $russia = $this->site('microchips-ru');
        [$category] = $this->categoryTree($belarus);
        $foreign = $this->siteProduct($russia, 'FOREIGN-RAW-1', 'foreign-raw');

        $this->expectException(QueryException::class);

        DB::table('site_category_product')->insert([
            'site_id' => $belarus->id,
            'site_category_id' => $category->id,
            'site_product_id' => $foreign->id,
            'created_at' => now(),
            'updated_at' => now(),
        ]);
    }

    /** @return array{SiteCategory, SiteCategory} */
    private function categoryTree(Site $site): array
    {
        $parentCanonical = Category::create(['slug' => $site->key.'-batteries', 'name' => 'Батареи']);
        $childCanonical = Category::create([
            'parent_id' => $parentCanonical->id,
            'slug' => $site->key.'-ups',
            'name' => 'Для ИБП',
        ]);
        $parent = SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $parentCanonical->id,
            'slug' => 'catalog/batteries',
            'name' => 'Батареи',
            'is_published' => true,
        ]);
        $child = SiteCategory::create([
            'site_id' => $site->id,
            'category_id' => $childCanonical->id,
            'slug' => 'catalog/batteries/ups',
            'name' => 'Для ИБП',
            'is_published' => true,
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/batteries',
            'locale' => $site->default_locale,
            'target_type' => 'category',
            'target_id' => $parent->id,
        ]);
        SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/batteries/ups',
            'locale' => $site->default_locale,
            'target_type' => 'category',
            'target_id' => $child->id,
        ]);

        return [$parent, $child];
    }

    private function siteProduct(Site $site, string $sku, string $slug, bool $published = true): SiteProduct
    {
        $product = Product::create([
            'sku' => $sku,
            'slug' => $site->key.'-'.$slug,
            'name' => $sku,
            'status' => 'draft',
        ]);

        return SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => $slug,
            'is_published' => $published,
        ]);
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
}
