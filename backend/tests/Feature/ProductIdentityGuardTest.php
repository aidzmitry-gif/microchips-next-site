<?php

namespace Tests\Feature;

use App\Domain\Imports\ProductIdentityConflict;
use App\Models\Product;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

class ProductIdentityGuardTest extends TestCase
{
    use RefreshDatabase;

    public function test_manual_catalog_entry_cannot_reuse_an_existing_identifier_with_spacing_or_punctuation_changes(): void
    {
        Product::create([
            'external_id' => 'manual-1',
            'sku' => 'FGL-120',
            'slug' => 'fiamm-fgl-120',
            'name' => 'Fiamm FGL 120',
            'status' => 'draft',
        ]);

        $this->expectException(ProductIdentityConflict::class);

        Product::create([
            'external_id' => 'manual-2',
            'sku' => 'fgl 120',
            'slug' => 'fiamm-fgl-120-duplicate',
            'name' => 'Fiamm FGL 120 duplicate',
            'status' => 'draft',
        ]);
    }

    public function test_manual_catalog_entry_cannot_change_a_persisted_identity(): void
    {
        $product = Product::create([
            'external_id' => 'manual-1',
            'sku' => 'FGL-120',
            'slug' => 'fiamm-fgl-120',
            'name' => 'Fiamm FGL 120',
            'status' => 'draft',
        ]);

        $product->sku = 'FGL-121';

        $this->expectException(ProductIdentityConflict::class);
        $product->save();
    }
}
