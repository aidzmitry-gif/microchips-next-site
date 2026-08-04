<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('product_families', function (Blueprint $table): void {
            $table->foreignId('site_id')->nullable()->after('id')->constrained()->cascadeOnDelete();
        });

        $families = DB::table('product_families')->select(['id', 'canonical_product_id'])->get();
        foreach ($families as $family) {
            $siteIds = DB::table('site_products')
                ->where('product_id', $family->canonical_product_id)
                ->distinct()
                ->pluck('site_id');
            if ($siteIds->count() !== 1) {
                throw new RuntimeException("Existing product family {$family->id} cannot be assigned to exactly one site.");
            }
            DB::table('product_families')->where('id', $family->id)->update(['site_id' => $siteIds->first()]);
        }

        DB::statement('ALTER TABLE product_families ALTER COLUMN site_id SET NOT NULL');

        Schema::table('product_families', function (Blueprint $table): void {
            $table->dropUnique('product_families_canonical_product_id_unique');
            $table->dropUnique('product_families_family_key_unique');
            $table->unique(['site_id', 'canonical_product_id']);
            $table->unique(['site_id', 'family_key']);
        });
        Schema::table('product_variants', function (Blueprint $table): void {
            $table->dropUnique('product_variants_product_id_unique');
            $table->unique(['product_family_id', 'product_id']);
        });
    }

    public function down(): void
    {
        Schema::table('product_variants', function (Blueprint $table): void {
            $table->dropUnique(['product_family_id', 'product_id']);
            $table->unique('product_id');
        });
        Schema::table('product_families', function (Blueprint $table): void {
            $table->dropUnique(['site_id', 'canonical_product_id']);
            $table->dropUnique(['site_id', 'family_key']);
            $table->unique('canonical_product_id');
            $table->unique('family_key');
            $table->dropConstrainedForeignId('site_id');
        });
    }
};
