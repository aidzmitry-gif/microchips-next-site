<?php

namespace App\Events;

use App\Models\Site;
use Illuminate\Contracts\Events\ShouldDispatchAfterCommit;
use Illuminate\Foundation\Events\Dispatchable;
use Illuminate\Queue\SerializesModels;

class SiteContentChanged implements ShouldDispatchAfterCommit
{
    use Dispatchable, SerializesModels;

    /** @param array<int, string> $paths */
    public function __construct(
        public Site $site,
        public array $paths,
    ) {}
}
