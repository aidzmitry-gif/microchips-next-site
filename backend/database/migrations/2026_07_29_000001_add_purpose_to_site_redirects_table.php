<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::table('site_redirects', function (Blueprint $table): void {
            $table->string('purpose')->default('seo')->after('status_code')->index();
        });

        // Redirects whose current destination is an explicitly non-indexable
        // preview were created only to preserve a replaced preview path. They
        // must remain distinguishable from launch/legacy SEO redirects, whose
        // destination is required to be indexable by the release auditor.
        DB::table('site_redirects')->orderBy('id')->eachById(function (object $redirect): void {
            $targetsNoindexPreview = DB::table('site_urls')
                ->where('site_id', $redirect->site_id)
                ->where('path', $redirect->target_path)
                ->where('is_indexable', false)
                ->exists();

            if ($targetsNoindexPreview) {
                DB::table('site_redirects')->where('id', $redirect->id)->update(['purpose' => 'preview']);
            }
        });
    }

    public function down(): void
    {
        Schema::table('site_redirects', function (Blueprint $table): void {
            $table->dropIndex(['purpose']);
            $table->dropColumn('purpose');
        });
    }
};
