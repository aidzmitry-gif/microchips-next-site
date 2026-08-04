<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('site_product_price_evidences', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->foreignId('site_product_id')->constrained()->cascadeOnDelete();
            $table->string('source', 32);
            $table->decimal('source_price', 14, 4);
            $table->decimal('multiplier', 8, 4);
            $table->decimal('calculated_price', 14, 2);
            $table->char('currency', 3);
            $table->string('price_type')->nullable();
            $table->string('source_external_id')->nullable();
            $table->text('source_reference');
            $table->timestampTz('observed_at');
            $table->string('evidence_key', 64)->unique();
            $table->json('evidence')->nullable();
            $table->boolean('is_current')->default(false);
            $table->timestamps();

            $table->index(['site_id', 'source', 'is_current']);
            $table->index(['site_product_id', 'is_current']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('site_product_price_evidences');
    }
};
