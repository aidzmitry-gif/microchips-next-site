<?php

namespace Tests\Feature;

use App\Models\Category;
use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteProductPriceEvidence;
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

    public function test_catalog_exposes_and_applies_source_backed_first_wave_facets(): void
    {
        $site = $this->site('microchips-by');
        [$category] = $this->categoryTree($site);
        $delta = $this->siteProduct($site, 'DELTA-7', 'delta-7');
        $fiamm = $this->siteProduct($site, 'FIAMM-12', 'fiamm-12');
        $category->products()->attach([$delta->id, $fiamm->id]);
        $delta->product->update([
            'manufacturer' => 'Delta',
            'mpn' => 'DTM1207',
            'technical_attributes' => [
                'chemistry' => 'AGM',
                'Номинальное напряжение' => '12 V',
                'Номинальная ёмкость C10' => '7 Ah',
            ],
        ]);
        $fiamm->product->update([
            'manufacturer' => 'FIAMM',
            'mpn' => 'FG20121',
            'technical_attributes' => [
                'Технология' => 'VRLA AGM',
                'Номинальное напряжение' => '12 V',
                'Номинальная ёмкость' => '12 Ah',
            ],
        ]);

        $query = http_build_query([
            'category' => $category->slug,
            'manufacturer' => 'Delta',
            'technology' => 'AGM',
            'nominal_voltage' => '12 V',
            'capacity' => '7 Ah',
        ]);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.$query)
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.manufacturer', 'Delta')
            ->assertJsonPath('data.0.summary_attributes.technology', 'AGM')
            ->assertJsonPath('data.0.summary_attributes.nominal_voltage', '12 V')
            ->assertJsonPath('data.0.summary_attributes.capacity', '7 Ah')
            ->assertJsonPath('meta.total', 1)
            ->assertJsonPath('meta.applied_filters.manufacturer', 'Delta')
            ->assertJsonPath('meta.facets.manufacturer.0.value', 'Delta')
            ->assertJsonPath('meta.facets.manufacturer.0.count', 1)
            ->assertJsonPath('meta.facets.manufacturer.1.value', 'FIAMM')
            ->assertJsonPath('meta.facets.technology.0.value', 'AGM')
            ->assertJsonPath('meta.facets.technology.0.count', 2);
    }

    public function test_catalog_collapses_equivalent_manufacturer_voltage_capacity_and_technology_facets(): void
    {
        $site = $this->site('microchips-by');
        [$category] = $this->categoryTree($site);

        for ($index = 1; $index <= 10; $index++) {
            $siteProduct = $this->siteProduct($site, "NORMALIZED-{$index}", "normalized-{$index}");
            $category->products()->attach($siteProduct);
            $siteProduct->product->update([
                'manufacturer' => $index % 2 === 0 ? 'APC' : 'APC by Schneider Electric',
                'technical_attributes' => [
                    'Технология' => $index <= 5
                        ? 'VRLA AGM'
                        : 'герметизированная свинцово-кислотная батарея с клапанным регулированием',
                    'Номинальное напряжение' => $index % 2 === 0 ? '12 V' : '12 В',
                    'Номинальная ёмкость' => $index % 2 === 0 ? '7.2 Ah' : '7,2 А·ч (C20)',
                ],
            ]);
        }

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $category->slug,
        ]))
            ->assertOk()
            ->assertJsonPath('meta.facets.manufacturer.0.value', 'APC')
            ->assertJsonPath('meta.facets.manufacturer.0.count', 10)
            ->assertJsonPath('meta.facets.nominal_voltage.0.value', '12 V')
            ->assertJsonPath('meta.facets.nominal_voltage.0.count', 10)
            ->assertJsonPath('meta.facets.capacity.0.value', '5–10 Ah')
            ->assertJsonPath('meta.facets.capacity.0.count', 10)
            ->assertJsonPath('meta.facets.technology.0.value', 'AGM')
            ->assertJsonPath('meta.facets.technology.0.count', 5)
            ->assertJsonPath('meta.facets.technology.1.value', 'VRLA')
            ->assertJsonPath('meta.facets.technology.1.count', 5);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $category->slug,
            'manufacturer' => 'APC by Schneider Electric',
            'nominal_voltage' => '12 В',
            'capacity' => '7,2 А·ч',
        ]))
            ->assertOk()
            ->assertJsonPath('meta.total', 10)
            ->assertJsonPath('meta.applied_filters.manufacturer', 'APC')
            ->assertJsonPath('meta.applied_filters.nominal_voltage', '12 V')
            ->assertJsonPath('meta.applied_filters.capacity', '5–10 Ah');
    }

    public function test_catalog_exposes_only_recognized_chemistry_as_technology_facets(): void
    {
        $site = $this->site('microchips-by');
        [$category] = $this->categoryTree($site);
        $values = [
            'Li-ion аккумулятор в жёстком корпусе',
            'никель-кадмиевый аккумулятор с карманными пластинами',
            'Внешний батарейный модуль для ИБП',
            'аккумулятор для мобильного принтера',
        ];

        for ($index = 1; $index <= 20; $index++) {
            $siteProduct = $this->siteProduct($site, "TECHNOLOGY-GATE-{$index}", "technology-gate-{$index}");
            $category->products()->attach($siteProduct);
            $siteProduct->product->update([
                'technical_attributes' => ['Технология' => $values[($index - 1) % count($values)]],
            ]);
        }

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $category->slug,
        ]))
            ->assertOk()
            ->assertJsonPath('meta.total', 20)
            ->assertJsonCount(2, 'meta.facets.technology')
            ->assertJsonPath('meta.facets.technology.0.value', 'Li-ion')
            ->assertJsonPath('meta.facets.technology.0.count', 5)
            ->assertJsonPath('meta.facets.technology.1.value', 'Ni-Cd')
            ->assertJsonPath('meta.facets.technology.1.count', 5)
            ->assertJsonMissing(['value' => 'Внешний батарейный модуль для ИБП'])
            ->assertJsonMissing(['value' => 'аккумулятор для мобильного принтера']);
    }

    public function test_catalog_hides_sparse_facets_but_retains_a_currently_applied_sparse_facet(): void
    {
        $site = $this->site('microchips-by');
        [$category] = $this->categoryTree($site);

        for ($index = 1; $index <= 20; $index++) {
            $siteProduct = $this->siteProduct($site, "SPARSE-{$index}", "sparse-{$index}");
            $category->products()->attach($siteProduct);
            if ($index <= 9) {
                $siteProduct->product->update(['manufacturer' => 'Sparse Brand']);
            }
        }

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $category->slug,
        ]))
            ->assertOk()
            ->assertJsonPath('meta.total', 20)
            ->assertJsonMissingPath('meta.facets.manufacturer');

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $category->slug,
            'manufacturer' => 'Sparse Brand',
        ]))
            ->assertOk()
            ->assertJsonPath('meta.total', 9)
            ->assertJsonPath('meta.applied_filters.manufacturer', 'Sparse Brand')
            ->assertJsonPath('meta.facets.manufacturer.0.value', 'Sparse Brand')
            ->assertJsonPath('meta.facets.manufacturer.0.count', 9);
    }

    public function test_catalog_filters_both_wave239_fiamm_verbose_capacity_keys(): void
    {
        $site = $this->site('microchips-by');
        [$category] = $this->categoryTree($site);
        $c10 = $this->siteProduct($site, 'FIAMM-SLA-800', 'fiamm-sla-800');
        $c20 = $this->siteProduct($site, 'FIAMM-FLB-400', 'fiamm-flb-400');
        $category->products()->attach([$c10->id, $c20->id]);
        $c10->product->update(['technical_attributes' => [
            'Номинальная ёмкость (10 ч, 1,80 В/эл., 20 °C)' => '820 А·ч',
        ]]);
        $c20->product->update(['technical_attributes' => [
            'Номинальная ёмкость (20 ч, 1,75 В/эл., 25 °C)' => '109 А·ч',
        ]]);

        foreach ([['820 А·ч', 'fiamm-sla-800'], ['109 А·ч', 'fiamm-flb-400']] as [$capacity, $slug]) {
            $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
                'category' => $category->slug,
                'capacity' => $capacity,
            ]))
                ->assertOk()
                ->assertJsonCount(1, 'data')
                ->assertJsonPath('data.0.slug', $slug)
                ->assertJsonPath('data.0.summary_attributes.capacity', str_starts_with($capacity, '820') ? '820 Ah' : '109 Ah')
                ->assertJsonPath('meta.facets.capacity.0.value', '100–200 Ah')
                ->assertJsonPath('meta.facets.capacity.1.value', 'Более 200 Ah');
        }
    }

    public function test_catalog_exposes_and_filters_exact_c120_capacity(): void
    {
        $site = $this->site('microchips-by');
        [$category] = $this->categoryTree($site);
        $battery = $this->siteProduct($site, 'EXIDE-4600', 'exide-4600');
        $category->products()->attach($battery);
        $battery->product->update([
            'manufacturer' => 'Exide',
            'mpn' => 'NVSL024600WC0FA',
            'technical_attributes' => [
                'Технология' => 'OPzS flooded lead-acid',
                'Номинальное напряжение' => '2 В',
                'Номинальная ёмкость C120' => '4600 А·ч',
            ],
        ]);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $category->slug,
            'manufacturer' => 'Exide',
            'capacity' => '4600 А·ч',
        ]))
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.mpn', 'NVSL024600WC0FA')
            ->assertJsonPath('data.0.summary_attributes.capacity', '4600 Ah')
            ->assertJsonPath('meta.total', 1)
            ->assertJsonPath('meta.facets.capacity.0.value', 'Более 200 Ah');
    }

    public function test_catalog_exposes_and_filters_exact_c5_capacity(): void
    {
        $site = $this->site('microchips-by');
        [$category] = $this->categoryTree($site);
        $battery = $this->siteProduct($site, 'ENERSYS-RM-400', 'enersys-rm-400');
        $category->products()->attach($battery);
        $battery->product->update([
            'manufacturer' => 'EnerSys',
            'mpn' => 'RM 400',
            'technical_attributes' => [
                'Технология' => 'Ni-Cd pocket plate',
                'Номинальная ёмкость C5' => '400 А·ч',
            ],
        ]);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $category->slug,
            'manufacturer' => 'EnerSys',
            'capacity' => '400 А·ч',
        ]))
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.mpn', 'RM 400')
            ->assertJsonPath('data.0.summary_attributes.capacity', '400 Ah')
            ->assertJsonPath('meta.total', 1);
    }

    public function test_power_category_facets_use_only_explicit_technical_attributes(): void
    {
        $site = $this->site('microchips-by');
        $categories = [];
        foreach (['power-supplies', 'power-converters', 'ups-systems'] as $leaf) {
            $canonical = Category::create([
                'slug' => 'microchips-by-'.$leaf,
                'name' => $leaf,
            ]);
            $categories[$leaf] = SiteCategory::create([
                'site_id' => $site->id,
                'category_id' => $canonical->id,
                'slug' => 'catalog/power-systems/'.$leaf,
                'name' => $leaf,
                'is_published' => true,
            ]);
        }

        $supply = $this->siteProduct($site, 'SUPPLY-1', 'supply-1');
        $supply->product->update(['technical_attributes' => [
            'Мощность' => '156 Вт',
            'Входное напряжение' => '100–240 В',
            'Выходное напряжение' => '24 В',
            'Входной ток' => '2 А',
            'Максимальный выходной ток' => '6,5 А',
            'Тип устройства' => 'Блок питания на DIN-рейку',
        ]]);
        $categories['power-supplies']->products()->attach($supply);

        $converter = $this->siteProduct($site, 'CONVERTER-1', 'converter-1');
        $converter->product->update(['technical_attributes' => [
            'rated_power' => '120 W',
            'input_voltage_range' => '67.2–154 V',
            'output_voltage' => '24 V',
            'max_input_current' => '2.1 A',
            'output_current' => '5 A',
            'device_type' => 'DC/DC converter',
        ]]);
        $categories['power-converters']->products()->attach($converter);

        $ups = $this->siteProduct($site, 'UPS-1', 'ups-1');
        $ups->product->update(['technical_attributes' => [
            'Активная мощность' => '6 кВт',
            'Диапазон входного напряжения' => '110–288 В',
            'Фазность' => '1 фаза на входе / 1 фаза на выходе',
            'Топология' => 'On-line (двойное преобразование)',
            'Тип' => 'Источник бесперебойного питания',
        ]]);
        $categories['ups-systems']->products()->attach($ups);

        $nameOnly = $this->siteProduct($site, 'NAME-ONLY', 'name-only');
        $nameOnly->product->update(['name' => 'Блок питания 1000 Вт, 48 В, 20 А']);
        $categories['power-supplies']->products()->attach($nameOnly);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $categories['power-supplies']->slug,
            'power' => '156 Вт',
            'output_current' => '6,5 А',
            'device_type' => 'Блок питания на DIN-рейку',
        ]))
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('data.0.slug', 'supply-1')
            ->assertJsonPath('meta.facets.power.0.value', '156 Вт')
            ->assertJsonPath('meta.facets.power.0.count', 1)
            ->assertJsonCount(1, 'meta.facets.power')
            ->assertJsonPath('meta.facets.output_current.0.value', '6,5 А')
            ->assertJsonPath('meta.facets.device_type.0.value', 'Блок питания на DIN-рейку')
            ->assertJsonPath('data.0.summary_attributes.input_voltage', '100–240 В')
            ->assertJsonPath('data.0.summary_attributes.output_voltage', '24 В')
            ->assertJsonPath('data.0.summary_attributes.input_current', '2 А')
            ->assertJsonMissingPath('meta.facets.input_voltage')
            ->assertJsonMissingPath('meta.facets.output_voltage')
            ->assertJsonMissingPath('meta.facets.input_current');

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $categories['power-converters']->slug,
            'output_current' => '5 A',
        ]))
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('meta.applied_filters.output_current', '5 A')
            ->assertJsonPath('data.0.summary_attributes.power', '120 W')
            ->assertJsonPath('data.0.summary_attributes.device_type', 'DC/DC converter')
            ->assertJsonMissingPath('meta.facets.power')
            ->assertJsonMissingPath('meta.facets.device_type');

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $categories['ups-systems']->slug,
            'phase' => '1 фаза на входе / 1 фаза на выходе',
            'topology' => 'On-line (двойное преобразование)',
        ]))
            ->assertOk()
            ->assertJsonCount(1, 'data')
            ->assertJsonPath('meta.applied_filters.phase', '1 фаза на входе / 1 фаза на выходе')
            ->assertJsonPath('meta.facets.topology.0.value', 'On-line (двойное преобразование)')
            ->assertJsonPath('data.0.summary_attributes.power', '6 кВт');
    }

    public function test_power_filters_are_inactive_outside_the_three_power_categories(): void
    {
        $site = $this->site('microchips-by');
        [$batteryCategory] = $this->categoryTree($site);
        $first = $this->siteProduct($site, 'BATTERY-POWER-1', 'battery-power-1');
        $second = $this->siteProduct($site, 'BATTERY-POWER-2', 'battery-power-2');
        $first->product->update(['technical_attributes' => ['Мощность' => '100 Вт']]);
        $batteryCategory->products()->attach([$first->id, $second->id]);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $batteryCategory->slug,
            'power' => '100 Вт',
        ]))
            ->assertOk()
            ->assertJsonCount(2, 'data')
            ->assertJsonPath('meta.applied_filters.power', null)
            ->assertJsonMissingPath('data.0.summary_attributes.power')
            ->assertJsonMissingPath('meta.facets.power');
    }

    public function test_catalog_search_ranks_exact_identity_before_name_and_manufacturer_matches(): void
    {
        $site = $this->site('microchips-by');
        $manufacturer = $this->siteProduct($site, 'MFR-1', 'manufacturer');
        $name = $this->siteProduct($site, 'NAME-1', 'name');
        $identity = $this->siteProduct($site, 'IDENTITY-1', 'identity');
        $manufacturer->product->update(['name' => 'Industrial battery', 'manufacturer' => 'DTM6012']);
        $name->product->update(['name' => 'DTM6012 compatible battery']);
        $identity->product->update(['name' => 'Delta battery', 'mpn' => 'DTM6012']);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?q=DTM6012')
            ->assertOk()
            ->assertJsonCount(3, 'data')
            ->assertJsonPath('data.0.slug', 'identity')
            ->assertJsonPath('data.1.slug', 'name')
            ->assertJsonPath('data.2.slug', 'manufacturer');
    }

    public function test_catalog_rejects_price_sort_until_confirmed_prices_exist(): void
    {
        $this->site('microchips-by');

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?sort=price_asc')
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['sort']);
    }

    public function test_catalog_sorts_source_backed_prices_and_places_missing_prices_last(): void
    {
        $site = $this->site('microchips-by');
        $cheap = $this->siteProduct($site, 'CHEAP-1', 'cheap');
        $expensive = $this->siteProduct($site, 'EXPENSIVE-1', 'expensive');
        $missing = $this->siteProduct($site, 'MISSING-1', 'missing');
        $cheap->update(['price' => '10.00']);
        $expensive->update(['price' => '30.00']);
        foreach ([[$cheap, '10.00'], [$expensive, '30.00']] as [$siteProduct, $price]) {
            SiteProductPriceEvidence::create([
                'site_id' => $site->id,
                'site_product_id' => $siteProduct->id,
                'source' => 'legacy_site',
                'source_price' => $price,
                'multiplier' => 1,
                'calculated_price' => $price,
                'currency' => 'BYN',
                'source_reference' => 'https://microchips.by/catalog/'.$siteProduct->slug.'/',
                'observed_at' => '2026-07-27T10:00:00+03:00',
                'evidence_key' => hash('sha256', $siteProduct->slug),
                'is_current' => true,
            ]);
        }

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?sort=price_asc')
            ->assertOk()
            ->assertJsonPath('meta.price_sort_enabled', true)
            ->assertJsonPath('data.0.slug', 'cheap')
            ->assertJsonPath('data.0.price_observed_at', '2026-07-27T10:00:00+00:00')
            ->assertJsonPath('data.1.slug', 'expensive')
            ->assertJsonPath('data.2.slug', 'missing')
            ->assertJsonPath('data.2.price_observed_at', null);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?sort=price_desc')
            ->assertOk()
            ->assertJsonPath('data.0.slug', 'expensive')
            ->assertJsonPath('data.1.slug', 'cheap')
            ->assertJsonPath('data.2.slug', 'missing');
    }

    public function test_price_sort_requires_current_evidence_inside_the_category_and_search_scope(): void
    {
        $site = $this->site('microchips-by');
        [$parent, $child] = $this->categoryTree($site);
        $priced = $this->siteProduct($site, 'SCOPED-PRICE', 'scoped-price');
        $unpriced = $this->siteProduct($site, 'SCOPED-NO-PRICE', 'scoped-no-price');
        $parent->products()->attach($priced);
        $child->products()->attach($unpriced);
        $priced->update(['price' => '20.00']);
        SiteProductPriceEvidence::create([
            'site_id' => $site->id,
            'site_product_id' => $priced->id,
            'source' => 'legacy_site',
            'source_price' => '20.00',
            'multiplier' => 1,
            'calculated_price' => '20.00',
            'currency' => 'BYN',
            'source_reference' => 'https://microchips.by/catalog/scoped-price/',
            'observed_at' => '2026-07-29T10:00:00+03:00',
            'evidence_key' => hash('sha256', 'scoped-price'),
            'is_current' => true,
        ]);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $parent->slug,
        ]))
            ->assertOk()
            ->assertJsonPath('meta.price_sort_enabled', true);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $child->slug,
        ]))
            ->assertOk()
            ->assertJsonPath('meta.price_sort_enabled', false);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'category' => $child->slug,
            'sort' => 'price_asc',
        ]))
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['sort']);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'q' => 'SCOPED-NO-PRICE',
            'sort' => 'price_desc',
        ]))
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['sort']);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products?'.http_build_query([
            'q' => 'SCOPED-PRICE',
            'sort' => 'price_asc',
        ]))
            ->assertOk()
            ->assertJsonPath('meta.price_sort_enabled', true)
            ->assertJsonPath('data.0.slug', 'scoped-price');
    }

    public function test_default_catalog_order_prefers_displayable_media_after_explicit_sort_order(): void
    {
        $site = $this->site('microchips-by');
        $placeholder = $this->siteProduct($site, 'NO-MEDIA-1', 'no-media');
        $imaged = $this->siteProduct($site, 'WITH-MEDIA-1', 'with-media');

        ProductMedia::create([
            'product_id' => $imaged->product_id,
            'source_page_url' => 'bitrix-backup://element/10',
            'source_kind' => 'legacy_bitrix_exact_element_preview',
            'rights_basis' => 'Company-owned legacy backup.',
            'storage_path' => 'legacy-staging/rb/bitrix-10-100.jpg',
            'content_sha256' => str_repeat('a', 64),
            'verification_status' => ProductMedia::STATUS_LEGACY_EXACT_PREVIEW,
            'is_published' => true,
        ]);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products')
            ->assertOk()
            ->assertJsonPath('data.0.slug', 'with-media')
            ->assertJsonPath('data.0.image_path', fn (mixed $path): bool => is_string($path) && str_starts_with($path, '/api/v1/media/'))
            ->assertJsonPath('data.1.slug', 'no-media')
            ->assertJsonPath('data.1.image_path', null);

        $placeholder->update(['sort_order' => -1]);

        $this->getJson('/api/v1/sites/microchips-by/catalog/products')
            ->assertOk()
            ->assertJsonPath('data.0.slug', 'no-media');
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

    public function test_catalog_paths_follow_the_requested_enabled_locale(): void
    {
        $site = $this->site('microchips-uz');
        $site->locales()->create(['locale' => 'ru-UZ', 'language' => 'ru', 'is_default' => true, 'is_enabled' => true]);
        $site->locales()->create(['locale' => 'uz-UZ', 'language' => 'uz', 'is_default' => false, 'is_enabled' => true]);
        [$parent] = $this->categoryTree($site);
        $product = $this->siteProduct($site, 'UZ-01', 'battery');
        $parent->products()->attach($product);
        SiteUrl::create(['site_id' => $site->id, 'path' => '/uz/catalog/akkumulyatory', 'locale' => 'uz-UZ', 'target_type' => 'category', 'target_id' => $parent->id]);
        SiteUrl::create(['site_id' => $site->id, 'path' => '/uz/catalog/akkumulyatory/battery', 'locale' => 'uz-UZ', 'target_type' => 'product', 'target_id' => $product->id]);

        $this->getJson('/api/v1/sites/microchips-uz/catalog/categories?locale=uz-UZ')
            ->assertOk()
            ->assertJsonPath('data.0.path', '/uz/catalog/akkumulyatory');
        $this->getJson('/api/v1/sites/microchips-uz/catalog/products?locale=uz-UZ')
            ->assertOk()
            ->assertJsonPath('data.0.path', '/uz/catalog/akkumulyatory/battery');
        $this->getJson('/api/v1/sites/microchips-uz/catalog/products?locale=ru-BY')
            ->assertUnprocessable()
            ->assertJsonValidationErrors(['locale']);
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
