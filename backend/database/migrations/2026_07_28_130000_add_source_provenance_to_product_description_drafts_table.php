<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('product_description_drafts', function (Blueprint $table): void {
            $table->string('source_kind')->nullable()->after('source_urls');
            $table->string('source_tier')->nullable()->after('source_kind');
            $table->string('source_publisher')->nullable()->after('source_tier');
            $table->boolean('manufacturer_primary')->nullable()->after('source_publisher');
            $table->string('identity_scope', 32)->nullable()->after('manufacturer_primary');
            $table->date('source_checked_at')->nullable()->after('identity_scope');
            $table->index(['source_tier', 'source_kind'], 'product_description_drafts_source_tier_kind');
        });
    }

    public function down(): void
    {
        Schema::table('product_description_drafts', function (Blueprint $table): void {
            $table->dropIndex('product_description_drafts_source_tier_kind');
            $table->dropColumn([
                'source_kind', 'source_tier', 'source_publisher', 'manufacturer_primary',
                'identity_scope', 'source_checked_at',
            ]);
        });
    }
};
