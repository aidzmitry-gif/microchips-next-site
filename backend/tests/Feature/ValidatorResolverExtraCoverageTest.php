<?php

namespace Tests\Feature;

use App\Domain\Imports\StageProductValidator;
use App\Domain\Sites\SiteResolver;
use App\Models\Product as ProductModel;
use App\Models\Site;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use App\Models\SiteUrlAlternate;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

/**
 * Targets the remaining uncovered branches in:
 *  - App\Domain\Imports\StageProductValidator::technicalAttributes() /
 *    normalizeAndValidate()'s slug fallback ternary
 *  - App\Domain\Sites\SiteResolver::seoPayload() / hreflangPayload()
 *
 * Not already exercised by StageProductValidatorAliasesTest or
 * SeoAuditorResolverCoverageTest.
 */
class ValidatorResolverExtraCoverageTest extends TestCase
{
    use RefreshDatabase;

    // -----------------------------------------------------------------
    // StageProductValidator::technicalAttributes()
    // -----------------------------------------------------------------

    public function test_technical_attributes_captures_dimensions_and_weight_when_no_electrical_specs_are_present(): void
    {
        $validator = new StageProductValidator;

        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-physical-1',
            'name' => 'Battery Enclosure Only',
            'sku' => 'ENCLOSURE-1',
            'dimensions' => '260x168x211 mm',
            'weight' => '21.5 kg',
        ]);

        $this->assertSame([], $result['errors']);
        $this->assertSame(
            [
                'dimensions' => '260x168x211 mm',
                'weight' => '21.5 kg',
            ],
            $result['data']['technical_attributes']
        );
    }

    // -----------------------------------------------------------------
    // StageProductValidator::normalizeAndValidate() — slug fallback ternary
    // -----------------------------------------------------------------

    public function test_slug_error_is_reported_when_the_name_collapses_to_an_empty_slug_and_no_explicit_slug_is_given(): void
    {
        $validator = new StageProductValidator;

        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-slug-blank-1',
            'name' => '***???!!!',
            'sku' => 'BLANK-SLUG-SKU',
        ]);

        $this->assertArrayHasKey('slug', $result['errors']);
        $this->assertSame(
            'A URL slug is required when the product name cannot be safely transliterated.',
            $result['errors']['slug']
        );
        // The name did transliterate down to a real (blank) string, so the
        // generated slug is still carried through in the data payload.
        $this->assertSame('', $result['data']['slug']);
    }

    public function test_slug_is_entirely_absent_from_data_when_the_name_itself_is_missing(): void
    {
        // Distinct branch from the "unslugifiable name" case above: when
        // $name === null, the ternary in normalizeAndValidate() short-circuits
        // to a literal null (never calls Str::slug()), and array_filter()
        // then drops the null slug from the data payload entirely — unlike
        // the blank-but-non-null string produced when a name is present.
        $validator = new StageProductValidator;

        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-no-name-1',
            'sku' => 'NO-NAME-SKU',
        ]);

        $this->assertArrayHasKey('name', $result['errors']);
        $this->assertArrayHasKey('slug', $result['errors']);
        $this->assertArrayNotHasKey('name', $result['data']);
        $this->assertArrayNotHasKey('slug', $result['data']);
    }

    // -----------------------------------------------------------------
    // SiteResolver::seoPayload() / hreflangPayload()
    // -----------------------------------------------------------------

    public function test_hreflang_payload_includes_a_declared_alternate_url_alongside_the_self_entry(): void
    {
        $belarus = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');
        $russia = $this->site('microchips-ru', 'microchips.ru', 'RU', 'ru-RU');

        $sourcePage = SitePage::create([
            'site_id' => $belarus->id,
            'locale' => 'ru-BY',
            'slug' => 'industrial-batteries',
            'title' => 'Industrial Batteries BY',
            'h1' => 'Industrial Batteries',
            'is_published' => true,
        ]);
        $sourceUrl = SiteUrl::create([
            'site_id' => $belarus->id,
            'path' => '/industrial-batteries',
            'locale' => 'ru-BY',
            'target_type' => 'page',
            'target_id' => $sourcePage->id,
            'is_indexable' => true,
        ]);
        SiteSeo::create([
            'site_id' => $belarus->id,
            'locale' => 'ru-BY',
            'resource_type' => 'page',
            'resource_id' => $sourcePage->id,
            'canonical_path' => '/industrial-batteries',
            'title' => 'Industrial Batteries BY',
            'is_indexable' => true,
        ]);

        $alternatePage = SitePage::create([
            'site_id' => $russia->id,
            'locale' => 'ru-RU',
            'slug' => 'promyshlennye-akkumulyatory',
            'title' => 'Industrial Batteries RU',
            'h1' => 'Industrial Batteries',
            'is_published' => true,
        ]);
        $alternateUrl = SiteUrl::create([
            'site_id' => $russia->id,
            'path' => '/promyshlennye-akkumulyatory',
            'locale' => 'ru-RU',
            'target_type' => 'page',
            'target_id' => $alternatePage->id,
            'is_indexable' => true,
        ]);

        SiteUrlAlternate::create([
            'source_url_id' => $sourceUrl->id,
            'alternate_url_id' => $alternateUrl->id,
            'locale' => 'ru-RU',
        ]);

        $result = (new SiteResolver)->resolvePath($belarus, '/industrial-batteries');

        $this->assertSame('page', $result['kind']);
        $this->assertSame(
            [
                'ru-RU' => 'https://microchips.ru/promyshlennye-akkumulyatory',
                'ru-BY' => 'https://microchips.by/industrial-batteries',
            ],
            $result['seo']['hreflang']
        );
    }

    public function test_hreflang_self_entry_falls_back_to_the_seo_locale_when_the_url_has_no_declared_locale(): void
    {
        // site_urls.locale is nullable. When it is null, hreflangPayload()
        // must key the self entry by the resolved SEO locale argument
        // instead ("$url->locale ?? $locale"), not by a literal null.
        $site = $this->site('microchips-by', 'microchips.by', 'BY', 'ru-BY');

        $product = ProductModel::create([
            'sku' => 'LOCALE-FALLBACK-01',
            'slug' => 'locale-fallback-battery',
            'name' => 'Locale Fallback Battery',
            'status' => 'active',
        ]);
        $siteProduct = SiteProduct::create([
            'site_id' => $site->id,
            'product_id' => $product->id,
            'slug' => 'locale-fallback-battery',
            'is_published' => true,
            'availability' => 'in_stock',
        ]);
        $url = SiteUrl::create([
            'site_id' => $site->id,
            'path' => '/catalog/locale-fallback-battery',
            'locale' => null,
            'target_type' => 'product',
            'target_id' => $siteProduct->id,
            'is_indexable' => true,
        ]);

        $result = (new SiteResolver)->resolvePath($site, '/catalog/locale-fallback-battery');

        $this->assertSame('product', $result['kind']);
        $this->assertSame(
            ['ru-BY' => 'https://microchips.by/catalog/locale-fallback-battery'],
            $result['seo']['hreflang']
        );
        // No SiteSeo row exists for this product, exercising the
        // seoPayload() defaults simultaneously with the locale fallback.
        $this->assertSame('Locale Fallback Battery', $result['seo']['title']);
        $this->assertNull($result['seo']['description']);
        $this->assertSame('/catalog/locale-fallback-battery', $result['seo']['canonicalPath']);
        $this->assertTrue($result['seo']['isIndexable']);
        $this->assertNull($result['seo']['schema']);

        $url->refresh();
        $this->assertNull($url->locale);
    }

    // -----------------------------------------------------------------
    // Fixture helpers
    // -----------------------------------------------------------------

    private function site(string $key, string $domain, string $country, string $locale): Site
    {
        $site = Site::create([
            'key' => $key,
            'domain' => $domain,
            'country_code' => $country,
            'currency_code' => $country === 'RU' ? 'RUB' : 'BYN',
            'default_locale' => $locale,
            'name' => $key,
            'is_active' => true,
        ]);
        $site->locales()->create([
            'locale' => $locale,
            'language' => 'ru',
            'is_default' => true,
            'is_enabled' => true,
        ]);

        return $site;
    }
}
