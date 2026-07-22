<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('product_description_drafts', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('product_id')->nullable()->constrained()->nullOnDelete();
            $table->foreignId('staged_import_record_id')->nullable()->constrained()->nullOnDelete();
            $table->string('locale', 16)->default('ru-BY');
            $table->string('title');
            $table->text('content')->nullable();
            $table->json('verified_fields');
            $table->json('source_urls');
            $table->string('status', 32)->default('draft');
            $table->text('rejection_reason')->nullable();
            $table->foreignId('submitted_by')->nullable()->constrained('users')->nullOnDelete();
            $table->timestamp('submitted_at')->nullable();
            $table->timestamps();

            $table->index(['status', 'locale']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('product_description_drafts');
    }
};
