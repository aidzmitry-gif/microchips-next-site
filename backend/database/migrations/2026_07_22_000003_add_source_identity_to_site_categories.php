<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('site_categories', function (Blueprint $table): void {
            $table->string('source')->nullable()->after('site_id');
            $table->string('external_id')->nullable()->after('source');
            $table->unique(['site_id', 'source', 'external_id'], 'site_categories_source_identity_unique');
        });
    }

    public function down(): void
    {
        Schema::table('site_categories', function (Blueprint $table): void {
            $table->dropUnique('site_categories_source_identity_unique');
            $table->dropColumn(['source', 'external_id']);
        });
    }
};
