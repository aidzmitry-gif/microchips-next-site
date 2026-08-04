<?php

namespace Tests\Unit;

use App\Domain\Content\ModelCoreIdentityMatcher;
use PHPUnit\Framework\Attributes\DataProvider;
use PHPUnit\Framework\TestCase;

class ModelCoreIdentityMatcherTest extends TestCase
{
    /** @return array<string, array{string, string}> */
    public static function matchingNames(): array
    {
        return [
            'spaced model core' => ['LS 14500 (SAFT)', 'LS14500'],
            'attached Latin suffix' => ['SAFT LS14250CNR lithium cell', 'LS14250'],
            'attached Cyrillic lookalike suffix' => ['LS 14250СNA 3,6 В', 'LS14250'],
            'hyphenated suffix' => ['SAFT LS14500 E-STD', 'LS14500'],
        ];
    }

    #[DataProvider('matchingNames')]
    public function test_it_accepts_exact_model_cores_and_allowlisted_suffixes(string $name, string $modelCore): void
    {
        $this->assertTrue(ModelCoreIdentityMatcher::nameContains($name, $modelCore));
    }

    /** @return array<string, array{string, string}> */
    public static function nonMatchingNames(): array
    {
        return [
            'numeric continuation' => ['SAFT LSH200 lithium cell', 'LSH20'],
            'alphabetic prefix' => ['XLS14250 lithium cell', 'LS14250'],
            'unknown attached suffix' => ['SAFT LS14250OEM lithium cell', 'LS14250'],
            'different model' => ['SAFT LS14500 lithium cell', 'LS14250'],
        ];
    }

    #[DataProvider('nonMatchingNames')]
    public function test_it_rejects_non_boundary_or_non_allowlisted_matches(string $name, string $modelCore): void
    {
        $this->assertFalse(ModelCoreIdentityMatcher::nameContains($name, $modelCore));
    }

    public function test_exact_model_accepts_a_trailing_non_identity_battery_summary(): void
    {
        $this->assertTrue(ModelCoreIdentityMatcher::nameEndsWith(
            'Аккумулятор Delta HR 12-4.5 (AGM, 4.5Ah)',
            'HR 12-4.5',
        ));
        $this->assertTrue(ModelCoreIdentityMatcher::nameEndsWith(
            'Аккумулятор Delta LFP12100 (LiFePO4, 12.8V, 100Ah)',
            'LFP12100',
        ));
    }

    public function test_exact_model_does_not_drop_identity_bearing_terminal_or_variant_suffixes(): void
    {
        $this->assertFalse(ModelCoreIdentityMatcher::nameEndsWith(
            'Аккумулятор Delta DTM 12008 (T9)',
            'DTM 12008',
        ));
        $this->assertFalse(ModelCoreIdentityMatcher::nameEndsWith(
            'Аккумулятор Delta HRL 12-100 X',
            'HRL 12-100',
        ));
    }
}
