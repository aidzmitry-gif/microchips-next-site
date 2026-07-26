<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('site_contacts', function (Blueprint $table): void {
            $table->boolean('is_published')->default(false)->after('is_primary');
            $table->timestamp('verified_at')->nullable()->after('is_published');
            $table->foreignId('verified_by')->nullable()->after('verified_at')->constrained('users')->nullOnDelete();
            $table->string('verification_note')->nullable()->after('verified_by');
            $table->index(['site_id', 'locale', 'is_published']);
        });
    }

    public function down(): void
    {
        Schema::table('site_contacts', function (Blueprint $table): void {
            $table->dropIndex(['site_id', 'locale', 'is_published']);
            $table->dropConstrainedForeignId('verified_by');
            $table->dropColumn(['verification_note', 'verified_at', 'is_published']);
        });
    }
};
