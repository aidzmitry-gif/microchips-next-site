<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        // The first local development run used temporary names while the
        // workflow was being hardened. Fresh installs already receive the
        // canonical columns from 000001; this migration only aligns that
        // short-lived local shape without touching contact values.
        Schema::table('site_contacts', function (Blueprint $table): void {
            if (Schema::hasColumn('site_contacts', 'is_public') && ! Schema::hasColumn('site_contacts', 'is_published')) {
                $table->renameColumn('is_public', 'is_published');
            }
            if (Schema::hasColumn('site_contacts', 'verification_source') && ! Schema::hasColumn('site_contacts', 'verification_note')) {
                $table->renameColumn('verification_source', 'verification_note');
            }
        });
    }

    public function down(): void
    {
        // Intentionally no-op. The preceding migration owns the canonical
        // columns on fresh installs and can safely remove them on rollback.
        // Reverting names here would make that rollback depend on whether a
        // local database happened to contain the short-lived legacy columns.
    }
};
