<?php

namespace Tests\Unit;

use App\Domain\Content\DescriptionSourceEvidencePolicy;
use PHPUnit\Framework\Attributes\DataProvider;
use RuntimeException;
use Tests\TestCase;

class DescriptionSourceEvidencePolicyTest extends TestCase
{
    public function test_it_accepts_exact_manufacturer_primary_product_page_evidence(): void
    {
        $evidence = DescriptionSourceEvidencePolicy::fromManifestRow($this->exactProductPageRow(), 0);

        $this->assertSame([
            'source_kind' => 'official_manufacturer_product_page',
            'source_tier' => 'manufacturer_primary',
            'source_publisher' => 'IPPON',
            'manufacturer_primary' => true,
            'identity_scope' => 'exact',
            'checked_at' => '2026-07-29',
        ], $evidence);
    }

    public function test_it_accepts_model_core_manufacturer_primary_product_page_evidence(): void
    {
        $row = $this->exactProductPageRow();
        unset($row['mpn']);
        $row['identity_scope'] = 'model_core';
        $row['evidence_scope'] = 'model_core';
        $row['model_core'] = 'Back Basic 650';

        $evidence = DescriptionSourceEvidencePolicy::fromManifestRow($row, 0);

        $this->assertSame('official_manufacturer_product_page', $evidence['source_kind']);
        $this->assertSame('model_core', $evidence['identity_scope']);
        $this->assertTrue($evidence['manufacturer_primary']);
    }

    #[DataProvider('invalidProductPageEvidence')]
    public function test_it_rejects_unknown_prohibited_or_incomplete_product_page_evidence(array $overrides): void
    {
        $this->expectException(RuntimeException::class);

        DescriptionSourceEvidencePolicy::fromManifestRow(array_replace($this->exactProductPageRow(), $overrides), 0);
    }

    /** @return iterable<string, array{array<string, mixed>}> */
    public static function invalidProductPageEvidence(): iterable
    {
        yield 'unknown source kind' => [['source_kind' => 'untrusted_product_page']];
        yield 'wrong manufacturer tier' => [['source_tier' => 'dealer_backed', 'manufacturer_primary' => false]];
        yield 'prohibited field' => [['price' => '1.00']];
        yield 'missing publisher' => [['source_publisher' => '']];
        yield 'missing attributes' => [['technical_attributes' => []]];
        yield 'non HTTPS source' => [['source_url' => 'http://manufacturer.example.test/back-basic-650']];
    }

    /** @return array<string, mixed> */
    private function exactProductPageRow(): array
    {
        return [
            'external_id' => 'bitrix:25109',
            'identity_scope' => 'exact',
            'manufacturer' => 'IPPON',
            'mpn' => 'Back Basic 650',
            'technology' => 'Line-interactive UPS',
            'source_url' => 'https://ippon.example.test/products/back-basic-650',
            'technical_attributes' => ['Topology' => 'Line-interactive'],
            'source_kind' => 'official_manufacturer_product_page',
            'source_tier' => 'manufacturer_primary',
            'source_publisher' => 'IPPON',
            'manufacturer_primary' => true,
            'evidence_scope' => 'exact_model',
            'checked_at' => '2026-07-29',
        ];
    }
}
