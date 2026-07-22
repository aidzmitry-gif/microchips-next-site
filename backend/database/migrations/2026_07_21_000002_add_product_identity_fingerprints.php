<?php

use App\Domain\Imports\ProductIdentity;
use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('products', function (Blueprint $table): void {
            $table->string('external_id_normalized')->nullable()->after('external_id');
            $table->string('sku_normalized')->nullable()->after('sku');
            $table->string('mpn_normalized')->nullable()->after('mpn');
        });

        DB::table('products')->orderBy('id')->each(function (object $product): void {
            DB::table('products')->where('id', $product->id)->update([
                'external_id_normalized' => ProductIdentity::normalize($product->external_id),
                'sku_normalized' => ProductIdentity::normalize($product->sku),
                'mpn_normalized' => ProductIdentity::normalize($product->mpn),
            ]);
        });

        foreach (['external_id_normalized', 'sku_normalized', 'mpn_normalized'] as $column) {
            $duplicate = DB::table('products')
                ->select($column)
                ->whereNotNull($column)
                ->groupBy($column)
                ->havingRaw('count(*) > 1')
                ->first();

            if ($duplicate !== null) {
                throw new RuntimeException("Cannot create canonical product identity indexes: duplicate {$column} exists.");
            }
        }

        Schema::table('products', function (Blueprint $table): void {
            $table->unique('external_id_normalized');
            $table->unique('sku_normalized');
            $table->unique('mpn_normalized');
        });
    }

    public function down(): void
    {
        Schema::table('products', function (Blueprint $table): void {
            $table->dropUnique(['external_id_normalized']);
            $table->dropUnique(['sku_normalized']);
            $table->dropUnique(['mpn_normalized']);
            $table->dropColumn(['external_id_normalized', 'sku_normalized', 'mpn_normalized']);
        });
    }
};
