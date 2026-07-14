<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('sites', function (Blueprint $table): void {
            $table->id();
            $table->string('key')->unique();
            $table->string('domain')->unique();
            $table->char('country_code', 2);
            $table->char('currency_code', 3);
            $table->string('default_locale', 10);
            $table->string('name');
            $table->string('legal_name')->nullable();
            $table->text('legal_address')->nullable();
            $table->string('phone')->nullable();
            $table->string('email')->nullable();
            $table->text('delivery_terms')->nullable();
            $table->text('payment_terms')->nullable();
            $table->boolean('is_active')->default(true);
            $table->timestamps();
        });

        Schema::create('site_locales', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->string('locale', 10);
            $table->string('language', 5);
            $table->boolean('is_default')->default(false);
            $table->boolean('is_enabled')->default(true);
            $table->timestamps();
            $table->unique(['site_id', 'locale']);
        });

        Schema::create('categories', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('parent_id')->nullable()->constrained('categories')->nullOnDelete();
            $table->string('slug')->unique();
            $table->string('name');
            $table->unsignedInteger('sort_order')->default(0);
            $table->timestamps();
        });

        Schema::create('products', function (Blueprint $table): void {
            $table->id();
            $table->string('sku')->nullable()->index();
            $table->string('mpn')->nullable()->index();
            $table->string('manufacturer')->nullable()->index();
            $table->string('slug')->unique();
            $table->string('name');
            $table->text('short_description')->nullable();
            $table->json('technical_attributes')->nullable();
            $table->string('status')->default('draft')->index();
            $table->timestamps();
        });

        Schema::create('site_categories', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->foreignId('category_id')->constrained()->cascadeOnDelete();
            $table->string('slug');
            $table->string('name')->nullable();
            $table->json('seo')->nullable();
            $table->boolean('is_published')->default(false);
            $table->unsignedInteger('sort_order')->default(0);
            $table->timestamps();
            $table->unique(['site_id', 'category_id']);
            $table->unique(['site_id', 'slug']);
        });

        Schema::create('site_products', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->foreignId('product_id')->constrained()->cascadeOnDelete();
            $table->string('slug');
            $table->boolean('is_published')->default(false);
            $table->string('availability')->default('on_request');
            $table->decimal('price', 14, 2)->nullable();
            $table->json('seo')->nullable();
            $table->unsignedInteger('sort_order')->default(0);
            $table->timestamps();
            $table->unique(['site_id', 'product_id']);
            $table->unique(['site_id', 'slug']);
        });

        Schema::create('site_pages', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->string('locale', 10);
            $table->string('slug');
            $table->string('title');
            $table->string('h1');
            $table->longText('content')->nullable();
            $table->boolean('is_published')->default(false);
            $table->timestamps();
            $table->unique(['site_id', 'locale', 'slug']);
        });

        Schema::create('site_seos', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->string('locale', 10);
            $table->string('resource_type');
            $table->unsignedBigInteger('resource_id')->nullable();
            $table->string('canonical_path');
            $table->string('title')->nullable();
            $table->text('description')->nullable();
            $table->boolean('is_indexable')->default(true);
            $table->json('schema')->nullable();
            $table->timestamps();
            $table->unique(['site_id', 'locale', 'resource_type', 'resource_id'], 'site_seo_resource_unique');
        });

        Schema::create('site_urls', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->string('path');
            $table->string('locale', 10)->nullable();
            $table->string('target_type');
            $table->unsignedBigInteger('target_id')->nullable();
            $table->boolean('is_indexable')->default(true);
            $table->timestamps();
            $table->unique(['site_id', 'path']);
        });

        Schema::create('site_redirects', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->string('source_path');
            $table->string('target_path');
            $table->unsignedSmallInteger('status_code')->default(301);
            $table->boolean('is_active')->default(true);
            $table->timestamps();
            $table->unique(['site_id', 'source_path']);
        });

        Schema::create('site_url_alternates', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('source_url_id')->constrained('site_urls')->cascadeOnDelete();
            $table->foreignId('alternate_url_id')->constrained('site_urls')->cascadeOnDelete();
            $table->string('locale', 10);
            $table->timestamps();
            $table->unique(['source_url_id', 'alternate_url_id']);
        });

        Schema::create('site_contacts', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->string('locale', 10)->nullable();
            $table->string('city')->nullable();
            $table->string('type');
            $table->string('label');
            $table->text('value');
            $table->boolean('is_primary')->default(false);
            $table->timestamps();
        });

        Schema::create('site_integrations', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->string('driver');
            $table->json('settings')->nullable();
            $table->boolean('is_enabled')->default(false);
            $table->timestamps();
            $table->unique(['site_id', 'driver']);
        });

        Schema::create('leads', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->restrictOnDelete();
            $table->string('locale', 10);
            $table->string('type');
            $table->string('company');
            $table->string('contact_name');
            $table->string('email')->nullable();
            $table->string('phone')->nullable();
            $table->text('message')->nullable();
            $table->string('page_url');
            $table->json('cart')->nullable();
            $table->json('utm')->nullable();
            $table->string('status')->default('new');
            $table->string('external_id')->nullable();
            $table->text('external_error')->nullable();
            $table->timestamps();
        });

        Schema::create('import_runs', function (Blueprint $table): void {
            $table->id();
            $table->string('source');
            $table->string('status')->default('queued');
            $table->string('source_file')->nullable();
            $table->unsignedInteger('total_records')->default(0);
            $table->unsignedInteger('processed_records')->default(0);
            $table->unsignedInteger('failed_records')->default(0);
            $table->json('summary')->nullable();
            $table->timestamp('started_at')->nullable();
            $table->timestamp('finished_at')->nullable();
            $table->timestamps();
        });

        Schema::create('staged_import_records', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('import_run_id')->constrained()->cascadeOnDelete();
            $table->unsignedInteger('row_number');
            $table->string('entity_type');
            $table->string('external_id')->nullable();
            $table->json('payload');
            $table->string('status')->default('staged');
            $table->text('error')->nullable();
            $table->timestamps();
            $table->index(['import_run_id', 'status']);
        });

        Schema::create('duplicate_conflicts', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('import_run_id')->nullable()->constrained()->nullOnDelete();
            $table->string('entity_type');
            $table->string('match_key');
            $table->json('candidate_ids');
            $table->string('status')->default('open');
            $table->text('resolution_note')->nullable();
            $table->timestamps();
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('duplicate_conflicts');
        Schema::dropIfExists('staged_import_records');
        Schema::dropIfExists('import_runs');
        Schema::dropIfExists('leads');
        Schema::dropIfExists('site_integrations');
        Schema::dropIfExists('site_contacts');
        Schema::dropIfExists('site_url_alternates');
        Schema::dropIfExists('site_redirects');
        Schema::dropIfExists('site_urls');
        Schema::dropIfExists('site_seos');
        Schema::dropIfExists('site_pages');
        Schema::dropIfExists('site_products');
        Schema::dropIfExists('site_categories');
        Schema::dropIfExists('products');
        Schema::dropIfExists('categories');
        Schema::dropIfExists('site_locales');
        Schema::dropIfExists('sites');
    }
};
