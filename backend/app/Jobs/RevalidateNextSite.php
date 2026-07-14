<?php

namespace App\Jobs;

use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;

class RevalidateNextSite implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    /** @param array<int, string> $paths */
    public function __construct(
        public int $siteId,
        public array $paths,
    ) {}

    public function handle(): void
    {
        $url = config('services.next.revalidate_url');
        $secret = config('services.next.revalidate_secret');

        if (blank($url) || blank($secret)) {
            return;
        }

        $response = Http::timeout(10)
            ->acceptJson()
            ->withToken($secret)
            ->post($url, ['paths' => array_values(array_unique($this->paths))]);

        if ($response->failed()) {
            Log::warning('Next.js revalidation request failed.', [
                'site_id' => $this->siteId,
                'status' => $response->status(),
            ]);

            $response->throw();
        }
    }
}
