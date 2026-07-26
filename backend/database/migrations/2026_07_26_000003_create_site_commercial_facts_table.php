<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('site_commercial_facts', function (Blueprint $table): void {
            $table->id();
            $table->foreignId('site_id')->constrained()->cascadeOnDelete();
            $table->string('locale', 10);
            $table->string('key', 64);
            $table->longText('value');
            $table->boolean('is_published')->default(false);
            $table->timestamp('verified_at')->nullable();
            $table->foreignId('verified_by')->nullable()->constrained('users')->nullOnDelete();
            $table->string('verification_note', 255)->nullable();
            $table->timestamps();

            $table->unique(['site_id', 'locale', 'key']);
            $table->index(['site_id', 'locale', 'is_published']);
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('site_commercial_facts');
    }
};
