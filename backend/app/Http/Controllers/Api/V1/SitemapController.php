<?php

namespace App\Http\Controllers\Api\V1;

use App\Domain\Seo\SiteSeoReleaseAuditor;
use App\Domain\Sites\SiteResolver;
use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;

class SitemapController extends Controller
{
    public function __invoke(string $host, SiteResolver $resolver, SiteSeoReleaseAuditor $auditor): JsonResponse
    {
        $site = $resolver->resolve($host);
        abort_if($site === null, 404, 'Site not found.');

        return response()->json([
            'site' => $site->key,
            'urls' => $auditor->sitemapUrls($site)
                ->map(fn ($url) => [
                    'path' => $url->path,
                    'lastModified' => $url->updated_at->toAtomString(),
                ])
                ->values(),
        ]);
    }
}
