<?php

namespace Tests\Feature;

use App\Models\ImportRun;
use App\Models\OneCNomenclatureItem;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class InventoryOneCNomenclatureTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_inventories_groups_and_products_without_making_them_publishable(): void
    {
        $file = $this->csvFile(<<<'CSV'
ЭтоГруппа;Код;Артикул;Наименование;РодительКод;РодительНаименование;ПолныйПуть;Единица;Цена;Валюта;ВидЦены
ИСТИНА;GROUP-1;;Аккумуляторы;;;Аккумуляторы;;;;
ЛОЖЬ;GROUP-1;;Товар с совпадающим кодом группы;;;Товар с совпадающим кодом группы;;;;
ЛОЖЬ;ITEM-2;Г3.2.18.56.;Складской артикул;GROUP-1;Аккумуляторы;Аккумуляторы / Складской артикул;шт;10,50;BYN;Розничная
ЛОЖЬ;ITEM-3;;Доставка курьером;GROUP-1;Аккумуляторы;Аккумуляторы / Доставка курьером;;;;
CSV, 'complete-one-c.csv');

        $this->artisan('catalog:inventory-1c', ['file' => $file])->assertSuccessful();

        $run = ImportRun::query()->sole();
        $this->assertSame('inventory_ready', $run->status);
        $this->assertSame(4, $run->total_records);
        $this->assertSame(1, $run->summary['groups']);
        $this->assertSame(3, $run->summary['products']);
        $this->assertSame(1, $run->summary['storage_location_articles']);
        $this->assertSame(1, $run->summary['suspected_non_products']);
        $this->assertSame([
            'source_group' => 1,
            'needs_identity_review' => 1,
            'needs_article_review' => 1,
            'needs_catalog_classification' => 1,
        ], $run->summary['classification_status_counts']);
        $this->assertSame('not_publishable_inventory_only', $run->summary['publication_status']);

        $this->assertDatabaseCount('one_c_nomenclature_items', 4);
        $this->assertDatabaseHas('one_c_nomenclature_items', [
            'external_id' => 'GROUP-1',
            'is_group' => true,
            'classification_status' => 'source_group',
        ]);
        $this->assertDatabaseHas('one_c_nomenclature_items', [
            'external_id' => 'GROUP-1',
            'is_group' => false,
            'classification_status' => 'needs_identity_review',
        ]);

        $storageArticle = OneCNomenclatureItem::query()->where('external_id', 'ITEM-2')->sole();
        $this->assertSame('needs_article_review', $storageArticle->classification_status);
        $this->assertContains('article_looks_like_storage_location', $storageArticle->classification_flags);
        $this->assertSame('10.5000', $storageArticle->price);

        $delivery = OneCNomenclatureItem::query()->where('external_id', 'ITEM-3')->sole();
        $this->assertSame('needs_catalog_classification', $delivery->classification_status);
        $this->assertContains('suspected_non_product', $delivery->classification_flags);
    }

    public function test_a_second_inventory_run_updates_source_rows_without_duplicating_them(): void
    {
        $first = $this->csvFile(<<<'CSV'
ЭтоГруппа;Код;Артикул;Наименование
ЛОЖЬ;ITEM-1;SKU-1;Первое название
CSV, 'one-c-first.csv');
        $second = $this->csvFile(<<<'CSV'
ЭтоГруппа;Код;Артикул;Наименование
ЛОЖЬ;ITEM-1;SKU-1;Обновлённое название
CSV, 'one-c-second.csv');

        $this->artisan('catalog:inventory-1c', ['file' => $first])->assertSuccessful();
        $this->artisan('catalog:inventory-1c', ['file' => $second])->assertSuccessful();

        $this->assertDatabaseCount('one_c_nomenclature_items', 1);
        $item = OneCNomenclatureItem::query()->sole();
        $this->assertSame('Обновлённое название', $item->name);
        $latestRun = ImportRun::query()->latest('id')->firstOrFail();
        $this->assertSame($latestRun->id, $item->import_run_id);
        $this->assertSame(1, $latestRun->summary['updated']);
    }

    public function test_duplicate_source_identity_is_reported_and_not_overwritten(): void
    {
        $file = $this->csvFile(<<<'CSV'
ЭтоГруппа;Код;Артикул;Наименование
ЛОЖЬ;ITEM-1;SKU-1;Первое название
ЛОЖЬ;ITEM-1;SKU-2;Конфликтующее название
CSV, 'one-c-duplicate.csv');

        $this->artisan('catalog:inventory-1c', ['file' => $file])->assertSuccessful();

        $run = ImportRun::query()->sole();
        $this->assertSame('needs_review', $run->status);
        $this->assertSame(1, $run->summary['duplicate_source_rows']);
        $this->assertSame(1, $run->failed_records);
        $this->assertDatabaseCount('one_c_nomenclature_items', 1);
        $this->assertSame('Первое название', OneCNomenclatureItem::query()->sole()->name);
    }

    public function test_missing_required_headers_fails_before_an_import_run_is_created(): void
    {
        $file = $this->csvFile("Код;Наименование\nITEM-1;Без признака группы\n", 'one-c-invalid-header.csv');

        $this->artisan('catalog:inventory-1c', ['file' => $file])->assertFailed();

        $this->assertDatabaseCount('import_runs', 0);
        $this->assertDatabaseCount('one_c_nomenclature_items', 0);
    }

    public function test_backslash_before_a_closing_quote_does_not_merge_source_rows(): void
    {
        $file = $this->csvFile(<<<'CSV'
"Код";"Артикул";"Наименование";"ЭтоГруппа"
"ITEM-1";"";"ER34615M/S FANSO БАТАРЕЯ \Китай\";"ЛОЖЬ"
"ITEM-2";"";"Следующий отдельный товар";"ЛОЖЬ"
CSV, 'one-c-backslash-quote.csv');

        $this->artisan('catalog:inventory-1c', ['file' => $file])->assertSuccessful();

        $run = ImportRun::query()->sole();
        $this->assertSame(2, $run->summary['csv_records']);
        $this->assertSame(0, $run->summary['invalid_rows']);
        $this->assertDatabaseCount('one_c_nomenclature_items', 2);
        $this->assertDatabaseHas('one_c_nomenclature_items', [
            'external_id' => 'ITEM-2',
            'name' => 'Следующий отдельный товар',
        ]);
    }

    private function csvFile(string $contents, string $name): string
    {
        $directory = storage_path('framework/testing');
        if (! is_dir($directory)) {
            mkdir($directory, 0777, true);
        }

        $file = $directory.'/'.$name;
        file_put_contents($file, $contents);

        return $file;
    }
}
