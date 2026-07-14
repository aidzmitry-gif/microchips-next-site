<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('products', function (Blueprint $table): void {
            $table->string('external_id')->nullable()->unique()->after('id');
        });

        Schema::table('staged_import_records', function (Blueprint $table): void {
            $table->json('normalized_payload')->nullable()->after('payload');
            $table->json('validation_errors')->nullable()->after('normalized_payload');
            $table->text('review_note')->nullable()->after('error');
            $table->foreignId('reviewed_by')->nullable()->after('review_note')->constrained('users')->nullOnDelete();
            $table->timestamp('reviewed_at')->nullable()->after('reviewed_by');
            $table->foreignId('published_by')->nullable()->after('reviewed_at')->constrained('users')->nullOnDelete();
            $table->foreignId('published_product_id')->nullable()->after('published_by')->constrained('products')->nullOnDelete();
            $table->foreignId('published_site_id')->nullable()->after('published_product_id')->constrained('sites')->nullOnDelete();
            $table->timestamp('published_at')->nullable()->after('published_site_id');
            $table->json('publication_snapshot')->nullable()->after('published_at');
        });
    }

    public function down(): void
    {
        Schema::table('staged_import_records', function (Blueprint $table): void {
            $table->dropConstrainedForeignId('published_site_id');
            $table->dropConstrainedForeignId('published_product_id');
            $table->dropConstrainedForeignId('published_by');
            $table->dropConstrainedForeignId('reviewed_by');
            $table->dropColumn([
                'normalized_payload',
                'validation_errors',
                'review_note',
                'reviewed_at',
                'published_at',
                'publication_snapshot',
            ]);
        });

        Schema::table('products', function (Blueprint $table): void {
            $table->dropUnique(['external_id']);
            $table->dropColumn('external_id');
        });
    }
};
