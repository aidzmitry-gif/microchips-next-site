<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('product_media', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('product_id')->constrained()->cascadeOnDelete();
            $table->string('kind')->default('image');
            $table->string('role')->default('gallery');
            $table->string('source_page_url');
            $table->string('source_asset_url')->nullable();
            $table->string('source_kind')->nullable();
            $table->string('rights_basis')->nullable();
            $table->string('storage_path')->nullable();
            $table->string('content_sha256', 64)->nullable();
            $table->string('verification_status')->default('pending');
            $table->text('verification_note')->nullable();
            $table->timestamp('verified_at')->nullable();
            $table->boolean('is_published')->default(false);
            $table->unsignedInteger('sort_order')->default(0);
            $table->timestamps();

            $table->index(['product_id', 'kind', 'verification_status', 'is_published'], 'product_media_public_lookup');
            $table->unique(['product_id', 'content_sha256'], 'product_media_product_hash_unique');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('product_media');
    }
};
