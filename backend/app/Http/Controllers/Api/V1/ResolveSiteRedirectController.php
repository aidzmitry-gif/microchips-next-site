<?php

namespace App\Http\Controllers\Api\V1;

use App\Domain\Sites\SiteResolver;
use App\Http\Controllers\Controller;
use App\Models\SiteRedirect;
use App\Models\SiteUrl;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class ResolveSiteRedirectController extends Controller
{
    public function __invoke(Request $request, string $host, SiteResolver $resolver): JsonResponse
    {
        $site = $resolver->resolve($host);

        abort_if($site === null, 404, 'Site not found.');

        $path = $resolver->normalizePath((string) $request->query('path', '/'));
        $locale = SiteUrl::query()
            ->where('site_id', $site->id)
            ->where('path', $path)
            ->value('locale') ?? $site->default_locale;

        $redirect = SiteRedirect::query()
            ->where('site_id', $site->id)
            ->where('source_path', $path)
            ->where('is_active', true)
            ->first();

        if ($redirect === null) {
            return response()->json(['kind' => 'not_found', 'locale' => $locale]);
        }

        return response()->json([
            'kind' => 'redirect',
            'to' => $redirect->target_path,
            'status' => $redirect->status_code,
            'locale' => $locale,
        ]);
    }
}
