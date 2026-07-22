<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('one_c_nomenclature_items', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('import_run_id')->constrained()->restrictOnDelete();
            $table->string('source_key')->default('1c_nomenclature');
            $table->string('external_id');
            $table->boolean('is_group')->default(false);
            $table->string('parent_external_id')->nullable()->index();
            $table->string('article')->nullable()->index();
            $table->string('name');
            $table->text('full_path')->nullable();
            $table->string('unit')->nullable();
            $table->decimal('price', 14, 4)->nullable();
            $table->char('currency', 3)->nullable();
            $table->string('price_type')->nullable();
            $table->string('classification_status')->index();
            $table->json('classification_flags')->nullable();
            $table->json('source_payload');
            $table->char('source_checksum', 64);
            $table->timestamps();

            $table->unique(
                ['source_key', 'external_id', 'is_group'],
                'one_c_nomenclature_source_identity_unique'
            );
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('one_c_nomenclature_items');
    }
};
