<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('catalog_draft_materializations', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('materialization_run_id')->constrained('import_runs')->cascadeOnDelete();
            $table->foreignId('source_import_run_id')->constrained('import_runs')->restrictOnDelete();
            $table->foreignId('staged_import_record_id')->constrained('staged_import_records')->restrictOnDelete();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->foreignId('product_id')->constrained()->cascadeOnDelete();
            $table->foreignId('site_product_id')->constrained()->cascadeOnDelete();
            $table->string('source_namespace', 32);
            $table->string('source_external_id');
            $table->char('source_checksum', 64);
            $table->string('materialization_kind', 64);
            $table->string('target_category_external_id')->nullable();
            $table->timestamps();

            $table->unique(['site_id', 'source_namespace', 'source_external_id'], 'catalog_draft_source_unique');
            $table->unique(['site_id', 'staged_import_record_id'], 'catalog_draft_staged_row_unique');
            $table->index(['source_import_run_id', 'materialization_kind'], 'catalog_draft_source_kind_index');
            $table->index('materialization_run_id');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('catalog_draft_materializations');
    }
};
