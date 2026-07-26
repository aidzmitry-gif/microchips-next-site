<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\ImportRun;
use App\Models\Site;
use App\Models\SiteCategory;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ImportSiteCategoryTaxonomyTest extends TestCase
{
    use RefreshDatabase;

    public function test_canonical_csv_headers_are_accepted_for_category_imports(): void
    {
        $site = $this->site('microchips-by');
        $file = $this->csv(<<<'CSV'
external_id,parent_external_id,name,path
root,,Root,catalog
CSV);

        $this->artisan('catalog:import-site-categories', [
            'site' => $site->key,
            'file' => $file,
        ])->assertSuccessful();

        $this->assertSame('dry_run_complete', ImportRun::query()->sole()->status);
    }

    public function test_missing_parent_header_is_rejected_even_though_root_values_may_be_blank(): void
    {
        $site = $this->site('microchips-by');
        $file = $this->csv(<<<'CSV'
external_id,name,path
root,Root,catalog
CSV);

        $this->artisan('catalog:import-site-categories', [
            'site' => $site->key,
            'file' => $file,
        ])->assertFailed();

        $this->assertDatabaseCount('site_categories', 0);
        $this->assertSame('failed', ImportRun::query()->sole()->status);
    }

    public function test_root_category_remains_a_root_after_apply_and_reapply(): void
    {
        $site = $this->site('microchips-by');
        $file = $this->csv(<<<'CSV'
external_id,parent_external_id,name,path
root,,Root,catalog
child,root,Child,catalog/child
CSV);
        $arguments = ['site' => $site->key, 'file' => $file, '--apply' => true];

        $this->artisan('catalog:import-site-categories', $arguments)->assertSuccessful();
        $this->artisan('catalog:import-site-categories', $arguments)->assertSuccessful();

        $root = SiteCategory::query()->where('site_id', $site->id)->where('external_id', 'root')->sole();
        $child = SiteCategory::query()->where('site_id', $site->id)->where('external_id', 'child')->sole();
        $this->assertNull($root->category->parent_id);
        $this->assertSame($root->category_id, $child->category->parent_id);
    }

    public function test_dry_run_resolves_children_before_parents_without_writing_categories(): void
    {
        $site = $this->site('microchips-by');
        $file = $this->csv(<<<'CSV'
Bitrix ID раздела,Родитель ID,Название,Путь на сайте
child,parent,Дочерняя,catalog/parent/child
parent,boundary,Родительская,catalog/parent
CSV);

        $this->artisan('catalog:import-site-categories', [
            'site' => $site->key,
            'file' => $file,
            '--allow-missing-parent' => ['boundary'],
        ])->assertSuccessful();

        $this->assertDatabaseCount('categories', 0);
        $this->assertDatabaseCount('site_categories', 0);
        $run = ImportRun::query()->sole();
        $this->assertSame('dry_run_complete', $run->status);
        $this->assertSame(2, $run->summary['created']);
        $this->assertSame(['boundary'], $run->summary['external_boundary_parent_ids']);
    }

    public function test_apply_is_site_scoped_idempotent_and_never_publishes_new_records(): void
    {
        $belarus = $this->site('microchips-by');
        $russia = $this->site('microchips-ru');
        $otherCategory = Category::create(['slug' => 'other', 'name' => 'Не менять']);
        SiteCategory::create([
            'site_id' => $russia->id,
            'category_id' => $otherCategory->id,
            'slug' => 'catalog/parent',
            'name' => 'Не менять',
            'is_published' => true,
        ]);
        $file = $this->csv(<<<'CSV'
Bitrix ID раздела,Родитель ID,Название,Путь на сайте
child,parent,Дочерняя,catalog/parent/child
parent,boundary,Родительская,catalog/parent
CSV);
        $arguments = [
            'site' => $belarus->key,
            'file' => $file,
            '--allow-missing-parent' => ['boundary'],
            '--apply' => true,
        ];

        $this->artisan('catalog:import-site-categories', $arguments)->assertSuccessful();
        $this->artisan('catalog:import-site-categories', $arguments)->assertSuccessful();

        $this->assertSame(2, SiteCategory::query()->where('site_id', $belarus->id)->count());
        $this->assertSame(1, SiteCategory::query()->where('site_id', $russia->id)->count());
        $this->assertSame('Не менять', $otherCategory->fresh()->name);
        $this->assertFalse(SiteCategory::query()->where('site_id', $belarus->id)->where('external_id', 'parent')->sole()->is_published);
        $parent = SiteCategory::query()->where('site_id', $belarus->id)->where('external_id', 'parent')->sole();
        $child = SiteCategory::query()->where('site_id', $belarus->id)->where('external_id', 'child')->sole();
        $this->assertSame($parent->category_id, $child->category->parent_id);
        $latestRun = ImportRun::query()->latest('id')->firstOrFail();
        $this->assertSame(0, $latestRun->summary['created']);
        $this->assertSame(0, $latestRun->summary['updated']);
        $this->assertSame(2, $latestRun->summary['unchanged']);
    }

    public function test_unknown_parent_duplicates_and_cycles_block_all_writes_with_audit_details(): void
    {
        $site = $this->site('microchips-by');
        $file = $this->csv(<<<'CSV'
Bitrix ID раздела,Родитель ID,Название,Путь на сайте
a,b,A,catalog/a
b,a,B,catalog/b
a,missing,Duplicate A,catalog/a-copy
c,unknown,C,catalog/c
d,unknown,D,catalog/c
CSV);

        $this->artisan('catalog:import-site-categories', [
            'site' => $site->key,
            'file' => $file,
        ])->assertFailed();

        $this->assertDatabaseCount('categories', 0);
        $this->assertDatabaseCount('site_categories', 0);
        $run = ImportRun::query()->sole();
        $this->assertSame('needs_review', $run->status);
        $reasons = collect($run->summary['validation_errors'])->pluck('reason')->all();
        $this->assertContains('duplicate_external_id', $reasons);
        $this->assertContains('duplicate_path', $reasons);
        $this->assertContains('unknown_parent', $reasons);
        $this->assertContains('cyclic_hierarchy', $reasons);
    }

    public function test_existing_parent_outside_the_csv_is_resolved_for_the_same_site_and_source(): void
    {
        $site = $this->site('microchips-by');
        $parentCategory = Category::create(['slug' => 'existing-parent', 'name' => 'Родитель']);
        $parent = SiteCategory::create([
            'site_id' => $site->id,
            'source' => 'bitrix_sections',
            'external_id' => 'parent',
            'category_id' => $parentCategory->id,
            'slug' => 'catalog/parent',
            'name' => 'Родитель',
            'is_published' => true,
        ]);
        $file = $this->csv(<<<'CSV'
Bitrix ID раздела,Родитель ID,Название,Путь на сайте
child,parent,Дочерняя,catalog/parent/child
CSV);

        $this->artisan('catalog:import-site-categories', [
            'site' => $site->key,
            'file' => $file,
            '--apply' => true,
        ])->assertSuccessful();

        $child = SiteCategory::query()->where('external_id', 'child')->sole();
        $this->assertSame($parent->category_id, $child->category->parent_id);
        $this->assertTrue($parent->fresh()->is_published);
        $this->assertSame(1, ImportRun::query()->sole()->summary['existing_parent_resolutions']);
    }

    public function test_shared_canonical_category_blocks_import_instead_of_creating_an_orphan_clone(): void
    {
        $belarus = $this->site('microchips-by');
        $russia = $this->site('microchips-ru');
        $canonical = Category::create(['slug' => 'shared', 'name' => 'Shared']);
        SiteCategory::create([
            'site_id' => $belarus->id,
            'source' => 'bitrix_sections',
            'external_id' => 'shared',
            'category_id' => $canonical->id,
            'slug' => 'catalog/shared',
            'name' => 'Shared',
            'is_published' => false,
        ]);
        SiteCategory::create([
            'site_id' => $russia->id,
            'source' => 'bitrix_sections',
            'external_id' => 'shared',
            'category_id' => $canonical->id,
            'slug' => 'catalog/shared',
            'name' => 'Shared',
            'is_published' => false,
        ]);
        $file = $this->csv(<<<'CSV'
Bitrix ID раздела,Родитель ID,Название,Путь на сайте
shared,boundary,Shared,catalog/shared
CSV);

        $this->artisan('catalog:import-site-categories', [
            'site' => $belarus->key,
            'file' => $file,
            '--allow-missing-parent' => ['boundary'],
            '--apply' => true,
        ])->assertFailed();

        $this->assertDatabaseCount('categories', 1);
        $this->assertSame('needs_review', ImportRun::query()->sole()->status);
        $this->assertSame(
            'shared_canonical_category',
            ImportRun::query()->sole()->summary['validation_errors'][0]['reason'],
        );
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

    private function csv(string $contents): string
    {
        $file = storage_path('framework/testing/categories-'.uniqid().'.csv');
        file_put_contents($file, $contents);

        return $file;
    }
}
