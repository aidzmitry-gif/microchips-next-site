<?php

namespace App\Http\Controllers\Api\V1;

use App\Domain\Sites\SiteResolver;
use App\Http\Controllers\Controller;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

class ResolveSitePathController extends Controller
{
    public function __invoke(Request $request, string $host, SiteResolver $resolver): JsonResponse
    {
        $site = $resolver->resolve($host);

        abort_if($site === null, 404, 'Site not found.');

        return response()->json($resolver->resolvePath($site, (string) $request->query('path', '/')));
    }
}
