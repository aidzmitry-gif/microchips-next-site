<?php

namespace App\Providers;

use App\Events\SiteContentChanged;
use App\Jobs\RevalidateNextSite;
use Illuminate\Cache\RateLimiting\Limit;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Event;
use Illuminate\Support\Facades\RateLimiter;
use Illuminate\Support\ServiceProvider;

class AppServiceProvider extends ServiceProvider
{
    /**
     * Register any application services.
     */
    public function register(): void
    {
        //
    }

    /**
     * Bootstrap any application services.
     */
    public function boot(): void
    {
        RateLimiter::for('leads', function (Request $request): Limit {
            $key = (string) $request->header('X-Lead-Rate-Key', '');

            return Limit::perMinute(10)->by(preg_match('/^[a-f0-9-]{36}$/i', $key) ? $key : $request->ip());
        });

        Event::listen(SiteContentChanged::class, function (SiteContentChanged $event): void {
            RevalidateNextSite::dispatch($event->site->id, $event->paths);
        });
    }
}
