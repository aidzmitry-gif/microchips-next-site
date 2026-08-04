<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('product_families', function (Blueprint $table): void {
            $table->string('canonical_label')->default('Базовая модель')->after('selector_label');
            $table->json('canonical_attributes')->nullable()->after('canonical_label');
        });
    }

    public function down(): void
    {
        Schema::table('product_families', function (Blueprint $table): void {
            $table->dropColumn(['canonical_label', 'canonical_attributes']);
        });
    }
};
