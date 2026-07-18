<?php

namespace Tests\Feature;

use App\Jobs\RevalidateNextSite;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Illuminate\Http\Client\RequestException;
use Illuminate\Support\Facades\Http;
use Illuminate\Support\Facades\Log;
use Tests\TestCase;

class RevalidateNextSiteTest extends TestCase
{
    use RefreshDatabase;

    public function test_it_does_not_call_http_when_revalidation_is_not_configured(): void
    {
        config([
            'services.next.revalidate_url' => null,
            'services.next.revalidate_secret' => null,
        ]);

        Http::fake();

        (new RevalidateNextSite(1, ['/catalog/alpha-battery']))->handle();

        Http::assertNothingSent();
    }

    public function test_it_posts_paths_and_secret_to_the_revalidate_url_on_success(): void
    {
        config([
            'services.next.revalidate_url' => 'https://next.example.test/api/revalidate',
            'services.next.revalidate_secret' => 'super-secret-token',
        ]);

        Http::fake([
            'next.example.test/*' => Http::response(['revalidated' => true], 200),
        ]);

        (new RevalidateNextSite(7, ['/catalog/alpha-battery', '/catalog/alpha-battery']))->handle();

        Http::assertSent(function ($request) {
            return $request->url() === 'https://next.example.test/api/revalidate'
                && $request->hasHeader('Authorization', 'Bearer super-secret-token')
                && $request['paths'] === ['/catalog/alpha-battery'];
        });
    }

    public function test_it_logs_a_warning_and_throws_when_the_revalidate_request_fails(): void
    {
        config([
            'services.next.revalidate_url' => 'https://next.example.test/api/revalidate',
            'services.next.revalidate_secret' => 'super-secret-token',
        ]);

        Http::fake([
            'next.example.test/*' => Http::response(['message' => 'nope'], 500),
        ]);

        Log::shouldReceive('warning')
            ->once()
            ->with('Next.js revalidation request failed.', [
                'site_id' => 7,
                'status' => 500,
            ]);

        $this->expectException(RequestException::class);

        (new RevalidateNextSite(7, ['/catalog/alpha-battery']))->handle();
    }
}
