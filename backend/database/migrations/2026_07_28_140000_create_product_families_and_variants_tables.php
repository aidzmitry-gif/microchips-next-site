<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('product_families', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('canonical_product_id')->unique()->constrained('products')->cascadeOnDelete();
            $table->string('family_key')->unique();
            $table->string('name');
            $table->string('manufacturer')->nullable()->index();
            $table->string('model_core')->nullable()->index();
            $table->string('selector_label')->default('Исполнение');
            $table->json('shared_attributes')->nullable();
            $table->text('source_url');
            $table->string('status')->default('verified')->index();
            $table->timestamps();
        });

        Schema::create('product_variants', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('product_family_id')->constrained()->cascadeOnDelete();
            $table->foreignId('product_id')->unique()->constrained('products')->cascadeOnDelete();
            $table->string('variant_key');
            $table->string('label');
            $table->json('attributes')->nullable();
            $table->text('source_url');
            $table->boolean('is_active')->default(true)->index();
            $table->timestamps();
            $table->unique(['product_family_id', 'variant_key']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('product_variants');
        Schema::dropIfExists('product_families');
    }
};
