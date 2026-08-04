<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('leads', function (Blueprint $table): void {
            $table->foreignId('handled_by')->nullable()->after('status')->constrained('users')->nullOnDelete();
            $table->timestamp('handled_at')->nullable()->after('handled_by');
            $table->text('internal_note')->nullable()->after('handled_at');
            $table->index(['site_id', 'status', 'created_at']);
        });
    }

    public function down(): void
    {
        Schema::table('leads', function (Blueprint $table): void {
            $table->dropIndex(['site_id', 'status', 'created_at']);
            $table->dropConstrainedForeignId('handled_by');
            $table->dropColumn(['handled_at', 'internal_note']);
        });
    }
};
