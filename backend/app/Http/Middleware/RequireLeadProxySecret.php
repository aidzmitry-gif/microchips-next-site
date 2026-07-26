<?php

namespace App\Http\Middleware;

use Closure;
use Illuminate\Http\Request;
use Symfony\Component\HttpFoundation\Response;

class RequireLeadProxySecret
{
    public function handle(Request $request, Closure $next): Response
    {
        $expected = config('services.lead_proxy_secret');
        if (! is_string($expected) || strlen($expected) < 32) {
            abort(503, 'Lead service is not configured.');
        }

        $provided = (string) $request->header('X-Lead-Proxy-Secret', '');
        if ($provided === '' || ! hash_equals($expected, $provided)) {
            abort(403, 'Lead endpoint accepts requests only from the application proxy.');
        }

        return $next($request);
    }
}
