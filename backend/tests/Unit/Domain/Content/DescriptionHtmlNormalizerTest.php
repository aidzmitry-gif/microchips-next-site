<?php

namespace Tests\Unit\Domain\Content;

use App\Domain\Content\DescriptionHtmlNormalizer;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class DescriptionHtmlNormalizerTest extends TestCase
{
    private DescriptionHtmlNormalizer $normalizer;

    protected function setUp(): void
    {
        parent::setUp();

        $this->normalizer = new DescriptionHtmlNormalizer;
    }

    public function test_it_returns_empty_output_for_empty_or_null_or_whitespace_only_input(): void
    {
        foreach (['', null, '   ', "\n\t "] as $input) {
            $result = $this->normalizer->normalize($input);

            $this->assertSame('', $result->html);
            $this->assertSame(0, $result->linksDereferenced);
            $this->assertFalse($result->needsManualReview);
            $this->assertTrue($result->isNoop());
        }
    }

    public function test_it_leaves_plain_text_without_any_markup_completely_unchanged(): void
    {
        $plain = 'Аккумулятор 12V/7Ah, срок службы 5 лет. Бренд & модель указаны в паспорте.';

        $result = $this->normalizer->normalize($plain);

        $this->assertSame($plain, $result->html);
        $this->assertSame(0, $result->linksDereferenced);
        $this->assertFalse($result->needsManualReview);
        $this->assertTrue($result->isNoop());
    }

    public function test_it_leaves_already_balanced_markup_untouched(): void
    {
        $result = $this->normalizer->normalize('<p>Ёмкость 7 Ач, напряжение 12 В.</p>');

        $this->assertSame('<p>Ёмкость 7 Ач, напряжение 12 В.</p>', $result->html);
        $this->assertSame(0, $result->linksDereferenced);
        $this->assertFalse($result->needsManualReview);
        $this->assertFalse($result->tagsRepaired);
        $this->assertTrue($result->isNoop());
    }

    public function test_it_dereferences_a_clean_internal_legacy_bitrix_link_but_keeps_the_words(): void
    {
        $result = $this->normalizer->normalize(
            '<p>Подходит для <a href="/catalog/akkumulyatory/dlya_ibp/agm/123/">ИБП APC</a>.</p>',
        );

        $this->assertSame('<p>Подходит для ИБП APC.</p>', $result->html);
        $this->assertSame(1, $result->linksDereferenced);
        $this->assertFalse($result->needsManualReview);
        $this->assertStringNotContainsString('<a', $result->html);
        $this->assertStringNotContainsString('/catalog/', $result->html);
        $this->assertTrue($result->isChanged());
    }

    public function test_it_keeps_an_external_manufacturer_link_and_mailto_link_untouched(): void
    {
        $external = $this->normalizer->normalize(
            '<p>Даташит: <a href="https://apc.com/specs">apc.com/specs</a>.</p>',
        );
        $this->assertSame(0, $external->linksDereferenced);
        $this->assertTrue($external->isNoop());
        $this->assertStringContainsString('<a href="https://apc.com/specs">apc.com/specs</a>', $external->html);

        $mailto = $this->normalizer->normalize(
            '<p>Пишите на <a href="mailto:info@example.test">info@example.test</a>.</p>',
        );
        $this->assertSame(0, $mailto->linksDereferenced);
        $this->assertTrue($mailto->isNoop());
        $this->assertStringContainsString('mailto:info@example.test', $mailto->html);
    }

    public function test_it_does_not_touch_a_same_page_anchor_link(): void
    {
        $result = $this->normalizer->normalize('<p>См. <a href="#specs">характеристики ниже</a>.</p>');

        $this->assertSame(0, $result->linksDereferenced);
        $this->assertTrue($result->isNoop());
        $this->assertStringContainsString('href="#specs"', $result->html);
    }

    public function test_it_does_not_touch_a_relative_link_outside_the_legacy_catalog_route(): void
    {
        $result = $this->normalizer->normalize('<p>См. <a href="/blog/agm-vs-gel">статью</a>.</p>');

        $this->assertSame(0, $result->linksDereferenced);
        $this->assertTrue($result->isNoop());
        $this->assertStringContainsString('href="/blog/agm-vs-gel"', $result->html);
    }

    /**
     * The single most common legacy Bitrix defect (P2-2): DETAIL_TEXT
     * reopens <p> without closing the previous one. The first two
     * auto-repair rounds tried to fix this (and similar) with regex/DOM
     * string surgery and each round shipped a new way to mangle adjacent
     * content, so a later rewrite stopped repairing anything and only
     * flagged it. This third round brings auto-repair back, but gates it on
     * an objective safety proof rather than pattern-matching "<p>" by name:
     * the round trip (parse + re-serialize) does not reproduce the input
     * byte-for-byte (the parser auto-closes the first <p>), but every
     * character of the input still appears, in order, in the re-serialized
     * output — nothing was removed or rewritten, only closing-tag syntax
     * was inserted — so the parser's own serialization is safe to accept.
     */
    public function test_an_unbalanced_paragraph_is_auto_repaired_and_flagged_as_repaired(): void
    {
        $original = '<p>Первый абзац.<p>Второй абзац.';

        $result = $this->normalizer->normalize($original);

        $this->assertSame('<p>Первый абзац.</p><p>Второй абзац.</p>', $result->html);
        $this->assertNotSame($original, $result->html);
        $this->assertSame($original, $result->original);
        $this->assertTrue($result->tagsRepaired);
        $this->assertFalse($result->needsManualReview);
        $this->assertSame(0, $result->linksDereferenced);
        $this->assertTrue($result->isChanged());
        $this->assertFalse($result->isNoop());
    }

    /**
     * The auto-repair from the test above must compose with the existing
     * legacy-link dereference transform rather than short-circuiting it: a
     * fragment with both defects (an unbalanced <p> AND a dead legacy
     * Bitrix link) gets the tag structure repaired and the link
     * dereferenced in the same pass, with both facts recorded in the audit
     * trail.
     */
    public function test_an_unbalanced_paragraph_containing_a_legacy_link_is_repaired_and_dereferenced_together(): void
    {
        $original = '<p>Подходит для <a href="/catalog/akkumulyatory/dlya_ibp/agm/123/">ИБП APC</a>.'
            .'<p>Поставляется в картонной упаковке.';

        $result = $this->normalizer->normalize($original);

        $this->assertSame(
            '<p>Подходит для ИБП APC.</p><p>Поставляется в картонной упаковке.</p>',
            $result->html,
        );
        $this->assertTrue($result->tagsRepaired);
        $this->assertSame(1, $result->linksDereferenced);
        $this->assertFalse($result->needsManualReview);
        $this->assertTrue($result->isChanged());
    }

    /**
     * Nested/repeated reopening (not just a single pair) must repair the
     * same way: every original character still appears in order in the
     * re-serialized output, only closing tags were inserted.
     */
    public function test_repeatedly_unbalanced_paragraphs_are_all_repaired(): void
    {
        $result = $this->normalizer->normalize('<p>a<p>b<p>c');

        $this->assertSame('<p>a</p><p>b</p><p>c</p>', $result->html);
        $this->assertTrue($result->tagsRepaired);
        $this->assertFalse($result->needsManualReview);
    }

    /**
     * P0 (round 1 finding): a bare "<" used as a comparison operator in a
     * battery spec ("<max 10A", "<5A") is common and is not markup. The
     * previous string-regex layer read it as an unterminated tag and
     * silently discarded everything up to the next "<"/end of string
     * (reproduced 2026-07-26: 'Ток разряда <max 10A...' -> '<max></max>').
     * The DOM round trip does not reproduce the input either (the parser
     * closes a bogus "<max>" tag or entity-escapes a lone "<"), but — unlike
     * an unbalanced `<p>` — this is NOT a safe structural repair: an
     * entity-escaped "<"/">" no longer appears as that literal character
     * anywhere in the re-serialized output (that is what escaping means), so
     * `isSafeStructuralRepair()` correctly reports "no" even though the
     * *decoded* textContent would misleadingly look unchanged. The untouched
     * original is returned and flagged instead of shipping the parser's
     * mangled guess.
     */
    public function test_a_bare_less_than_comparison_operator_is_never_silently_lost(): void
    {
        $cases = [
            'Саморазряд <3%/мес, ток <5A',
            'Ток разряда <max 10A, напряжение 12 В, ёмкость 7 Ач',
            'Ток разряда <C20 = 0.35 A при 25 °C',
        ];

        foreach ($cases as $original) {
            $result = $this->normalizer->normalize($original);

            $this->assertSame($original, $result->html, "text was lost or altered: {$original}");
            $this->assertTrue($result->needsManualReview, "not flagged for review: {$original}");
            $this->assertFalse($result->tagsRepaired, "must not be reported as repaired: {$original}");
            $this->assertTrue($result->isChanged());
        }
    }

    /**
     * Round-2 finding: '<img src="x" onerror="if(1<2)alert(1)>' has an
     * unterminated attribute value containing a "<" — a string-regex
     * allowlist ('[^<>]*') does not match a tag with "<" inside an
     * attribute and let the whole payload through untouched as if it were
     * safe. This class makes no safety claim about it either, but it must
     * never mangle it into something else: the round trip fails (the
     * malformed attribute confuses the parser), the entity-escaped "<"/">"
     * inside the attribute value breaks the subsequence safety check too, so
     * the original is returned byte-for-byte and flagged — never repaired.
     */
    public function test_a_malformed_attribute_value_is_left_untouched_and_flagged_not_silently_passed_through_mangled(): void
    {
        $original = '<img src="x" onerror="if(1<2)alert(1)>';

        $result = $this->normalizer->normalize($original);

        $this->assertSame($original, $result->html);
        $this->assertTrue($result->needsManualReview);
        $this->assertFalse($result->tagsRepaired);
    }

    /**
     * Round-2 finding: '<a href="/catalog/akb/" onclick="return w>0">АКБ</a>'
     * previously came out as '0"&gt;АКБ' — a fragment of the onclick
     * attribute value glued into visible text. Here the raw ">" inside the
     * quoted onclick value gets re-escaped to "&gt;" by DOMDocument's
     * serializer, so the round trip does not reproduce the input; the
     * escaped ">" also fails the subsequence safety check (it no longer
     * appears as a literal ">" at that position), so nothing is
     * dereferenced or repaired, and the whole tag (attribute included) is
     * left completely untouched, flagged for manual review — no attribute
     * value fragment ever reaches visible text.
     */
    public function test_a_legacy_link_with_a_raw_gt_inside_a_quoted_attribute_is_left_untouched_not_glued_into_text(): void
    {
        $original = '<a href="/catalog/akb/" onclick="return w>0">АКБ</a>';

        $result = $this->normalizer->normalize($original);

        $this->assertSame($original, $result->html);
        $this->assertTrue($result->needsManualReview);
        $this->assertFalse($result->tagsRepaired);
        $this->assertStringNotContainsString('0"&gt;', $result->html);
    }

    /**
     * Prose containing a bare "<" followed by a CDATA element name is parsed
     * as a real <style>/<script>/<title>/<textarea>, and everything after it
     * is swallowed as that element's raw content — it stops rendering as
     * visible text even though every character is still present in the
     * serialized string.
     *
     * That is why the character-order gate alone is not enough:
     * 'Габариты <style h> 151х65х94 мм' re-serializes to
     * 'Габариты <style h> 151х65х94 мм</style>', which the order gate
     * happily accepts (only a closing tag was inserted) while the browser
     * renders just 'Габариты '. A second gate compares the text that
     * actually renders, so these inputs are returned untouched and flagged.
     *
     * Note the '<style 5>' spelling used to fail the order gate by accident
     * — libxml drops "5" as an invalid attribute name, so a character went
     * missing. Any letter-led token has no such accident, so the letter-led
     * cases below are the ones that actually prove the second gate works.
     *
     * @return iterable<string, array{0: string}>
     */
    public static function invisibleContentProvider(): iterable
    {
        yield 'style with letter-led token' => ['Габариты <style h> 151х65х94 мм, вес 2,1 кг'];
        yield 'script with letter-led token' => ['Ток <script i> 10A, ёмкость 7 Ач'];
        yield 'title with letter-led token' => ['Ресурс <title t> 5 лет при 20 °C'];
        yield 'textarea with letter-led token' => ['Клемма <textarea b> M6, момент 8 Н·м'];
        yield 'style with digit-led token' => ['Корпус <style 5> мм'];
    }

    #[DataProvider('invisibleContentProvider')]
    public function test_prose_swallowed_into_an_invisible_element_is_never_auto_repaired(string $original): void
    {
        $result = $this->normalizer->normalize($original);

        $this->assertSame($original, $result->html);
        $this->assertTrue($result->needsManualReview);
        $this->assertFalse($result->tagsRepaired);
    }

    /**
     * General invariant every case above is an instance of: whatever the
     * input, the normalizer must never ship visible text that differs from
     * the input without recording that fact in the audit trail. Either the
     * output is byte-identical to the input, or `isChanged()` is true.
     *
     * @return iterable<string, array{0: string}>
     */
    public static function assortedInputProvider(): iterable
    {
        yield 'plain text' => ['Аккумулятор 12V/7Ah, срок службы 5 лет.'];
        yield 'balanced markup' => ['<p>Ёмкость 7 Ач.</p>'];
        yield 'unbalanced p' => ['<p>Первый абзац.<p>Второй абзац.'];
        yield 'bare lt' => ['Ток <5A, напряжение 12 В'];
        yield 'legacy link' => ['<p><a href="/catalog/a">текст</a></p>'];
        yield 'malformed attribute' => ['<img src="x" onerror="if(1<2)alert(1)>'];
        yield 'style-like token' => ['Корпус <style 5> мм'];
        yield 'letter-led style token' => ['Габариты <style h> 151х65х94 мм'];
    }

    #[DataProvider('assortedInputProvider')]
    public function test_visible_text_is_never_silently_lost_or_altered(string $original): void
    {
        $result = $this->normalizer->normalize($original);

        $this->assertTrue(
            $result->html === $original || $result->isChanged(),
            'output differs from input but the change was not recorded in the audit trail',
        );
    }
}
