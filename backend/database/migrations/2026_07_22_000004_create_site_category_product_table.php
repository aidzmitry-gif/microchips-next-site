<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('site_categories', function (Blueprint $table): void {
            $table->unique(['site_id', 'id'], 'site_categories_site_id_id_unique');
        });
        Schema::table('site_products', function (Blueprint $table): void {
            $table->unique(['site_id', 'id'], 'site_products_site_id_id_unique');
        });

        Schema::create('site_category_product', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->foreignId('site_category_id')->constrained()->cascadeOnDelete();
            $table->foreignId('site_product_id')->constrained()->cascadeOnDelete();
            $table->timestamps();
            $table->unique(['site_category_id', 'site_product_id']);
            $table->foreign(['site_id', 'site_category_id'], 'site_category_product_category_site_fk')
                ->references(['site_id', 'id'])
                ->on('site_categories')
                ->cascadeOnDelete();
            $table->foreign(['site_id', 'site_product_id'], 'site_category_product_product_site_fk')
                ->references(['site_id', 'id'])
                ->on('site_products')
                ->cascadeOnDelete();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('site_category_product');
        Schema::table('site_products', function (Blueprint $table): void {
            $table->dropUnique('site_products_site_id_id_unique');
        });
        Schema::table('site_categories', function (Blueprint $table): void {
            $table->dropUnique('site_categories_site_id_id_unique');
        });
    }
};
