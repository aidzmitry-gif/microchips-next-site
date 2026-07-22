<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('catalog_identity_candidates', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('import_run_id')->constrained()->restrictOnDelete();
            $table->foreignId('one_c_nomenclature_item_id')->constrained()->restrictOnDelete();
            $table->string('legacy_source')->default('bitrix');
            $table->string('legacy_id');
            $table->string('legacy_name');
            $table->string('legacy_url')->nullable();
            $table->unsignedInteger('review_priority');
            $table->string('review_batch');
            $table->decimal('confidence', 5, 4);
            $table->string('match_method');
            $table->string('signature')->nullable();
            $table->string('comparison_status')->nullable();
            $table->string('review_status')->default('pending')->index();
            $table->string('confirmed_sku')->nullable();
            $table->string('confirmed_sku_normalized')->nullable()->unique();
            $table->string('confirmed_mpn')->nullable();
            $table->string('confirmed_mpn_normalized')->nullable()->unique();
            $table->string('confirmed_manufacturer')->nullable();
            $table->string('confirmed_category')->nullable();
            $table->text('review_note')->nullable();
            $table->foreignId('reviewed_by')->nullable()->constrained('users')->nullOnDelete();
            $table->timestamp('reviewed_at')->nullable();
            $table->json('source_payload');
            $table->char('source_checksum', 64);
            $table->timestamps();

            $table->unique(['legacy_source', 'legacy_id']);
            $table->unique('one_c_nomenclature_item_id');
            $table->index(['review_batch', 'review_priority']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('catalog_identity_candidates');
    }
};
