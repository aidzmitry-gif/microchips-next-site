<?php

namespace App\Console\Commands;

use App\Domain\Seo\SiteIndexabilityPublisher;
use App\Models\SiteUrl;
use DomainException;
use Illuminate\Console\Command;

class PromoteSiteUrlIndexability extends Command
{
    protected $signature = 'seo:promote-url {site : Site key} {path : Normalized URL path}';

    protected $description = 'Promote one published site URL from noindex only when the complete release audit passes';

    public function handle(SiteIndexabilityPublisher $publisher): int
    {
        $url = SiteUrl::query()
            ->whereHas('site', fn ($query) => $query->where('key', $this->argument('site')))
            ->where('path', $this->argument('path'))
            ->first();
        if ($url === null) {
            $this->error('Site URL was not found.');

            return self::FAILURE;
        }

        try {
            $publisher->promote($url);
        } catch (DomainException $exception) {
            $this->error($exception->getMessage());

            return self::FAILURE;
        }

        $this->info("PASS: {$url->path} is now indexable.");

        return self::SUCCESS;
    }
}
