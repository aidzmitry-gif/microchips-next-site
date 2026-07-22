<?php

namespace Tests\Feature;

use App\Domain\Imports\StageProductValidator;
use Illuminate\Support\Str;
use Tests\TestCase;

class StageProductValidatorAliasesTest extends TestCase
{
    public function test_cyrillic_column_aliases_are_resolved_for_name_sku_mpn_and_manufacturer(): void
    {
        $validator = new StageProductValidator;

        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-cyr-1',
            'наименование' => 'Аккумулятор AGM 12В 100Ач',
            'артикул' => 'AGM-100-12',
            'номер_производителя' => 'CSB-GP12100',
            'производитель' => 'CSB Battery',
        ]);

        $this->assertSame([], $result['errors']);
        $this->assertSame('Аккумулятор AGM 12В 100Ач', $result['data']['name']);
        $this->assertSame('AGM-100-12', $result['data']['sku']);
        $this->assertSame('CSB-GP12100', $result['data']['mpn']);
        $this->assertSame('CSB Battery', $result['data']['manufacturer']);
        // No explicit slug supplied, so it must fall back to a transliterated slug of the Cyrillic name.
        $this->assertSame(Str::slug('Аккумулятор AGM 12В 100Ач'), $result['data']['slug']);
        $this->assertNotSame('', $result['data']['slug']);
    }

    public function test_cyrillic_aliases_are_only_used_when_the_english_key_is_absent(): void
    {
        $validator = new StageProductValidator;

        // English keys take priority over Cyrillic ones per the value() key order.
        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-cyr-2',
            'name' => 'English Name Wins',
            'наименование' => 'Кириллическое имя проиграет',
            'sku' => 'ENG-SKU',
            'артикул' => 'CYR-SKU-IGNORED',
        ]);

        $this->assertSame('English Name Wins', $result['data']['name']);
        $this->assertSame('ENG-SKU', $result['data']['sku']);
    }

    public function test_only_mpn_alias_present_still_satisfies_the_identifier_requirement(): void
    {
        $validator = new StageProductValidator;

        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-cyr-3',
            'name' => 'Battery With Only MPN Alias',
            'номер_производителя' => 'GP1272-ALIAS',
            // No sku / артикул supplied at all.
        ]);

        $this->assertArrayNotHasKey('identifier', $result['errors']);
        $this->assertSame('GP1272-ALIAS', $result['data']['mpn']);
        $this->assertArrayNotHasKey('sku', $result['data']);
    }

    public function test_url_slug_alias_takes_priority_over_a_generated_slug_from_the_name(): void
    {
        $validator = new StageProductValidator;

        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-slug-1',
            'name' => 'Deep Cycle Battery 200Ah',
            'sku' => 'DCB-200',
            'url_slug' => 'custom-battery-slug-from-1c',
        ]);

        $this->assertSame([], $result['errors']);
        $this->assertSame('custom-battery-slug-from-1c', $result['data']['slug']);
        $this->assertNotSame(Str::slug('Deep Cycle Battery 200Ah'), $result['data']['slug']);
    }

    public function test_slug_key_takes_priority_over_url_slug_when_both_are_present(): void
    {
        $validator = new StageProductValidator;

        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-slug-2',
            'name' => 'Gel Battery 55Ah',
            'sku' => 'GEL-55',
            'slug' => 'primary-slug-wins',
            'url_slug' => 'secondary-slug-ignored',
        ]);

        $this->assertSame('primary-slug-wins', $result['data']['slug']);
    }

    public function test_an_explicit_slug_is_used_even_when_it_differs_from_the_name(): void
    {
        $validator = new StageProductValidator;

        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-slug-3',
            'name' => 'Совершенно другое название',
            'sku' => 'ANY-SKU',
            'slug' => 'stable-legacy-slug',
        ]);

        $this->assertSame([], $result['errors']);
        $this->assertSame('stable-legacy-slug', $result['data']['slug']);
    }

    public function test_slug_is_reported_as_an_error_when_the_name_cannot_be_transliterated_and_no_explicit_slug_is_given(): void
    {
        $validator = new StageProductValidator;

        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-slug-4',
            'name' => '###???',
            'sku' => 'PUNCT-SKU',
        ]);

        $this->assertArrayHasKey('slug', $result['errors']);
        $this->assertSame(
            'A URL slug is required when the product name cannot be safely transliterated.',
            $result['errors']['slug']
        );
        // The blank (but non-null) generated slug is still carried through in the data payload.
        $this->assertArrayHasKey('slug', $result['data']);
        $this->assertSame('', $result['data']['slug']);
    }

    public function test_technical_attributes_capture_dimensions_and_weight_alongside_other_known_fields(): void
    {
        $validator = new StageProductValidator;

        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-tech-1',
            'name' => 'AGM Battery With Full Spec Sheet',
            'sku' => 'AGM-SPEC-1',
            'dimensions' => '151x98x95 mm',
            'weight' => '4.8 kg',
            'voltage' => '12V',
        ]);

        $this->assertSame([], $result['errors']);
        $this->assertSame(
            [
                'voltage' => '12V',
                'dimensions' => '151x98x95 mm',
                'weight' => '4.8 kg',
            ],
            $result['data']['technical_attributes']
        );
    }

    public function test_technical_attributes_omit_dimensions_and_weight_when_blank_or_absent(): void
    {
        $validator = new StageProductValidator;

        $result = $validator->normalizeAndValidate([
            'external_id' => '1c-tech-2',
            'name' => 'Battery Without Physical Spec',
            'sku' => 'NO-SPEC-1',
            'dimensions' => '   ',
            'capacity' => '100Ah',
        ]);

        $this->assertSame([], $result['errors']);
        $this->assertArrayNotHasKey('dimensions', $result['data']['technical_attributes']);
        $this->assertArrayNotHasKey('weight', $result['data']['technical_attributes']);
        $this->assertSame(['capacity' => '100Ah'], $result['data']['technical_attributes']);
    }
}
