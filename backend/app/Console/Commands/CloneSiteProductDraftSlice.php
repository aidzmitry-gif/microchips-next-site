<?php

namespace App\Console\Commands;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Console\Command;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;
use RuntimeException;
use Throwable;

class CloneSiteProductDraftSlice extends Command
{
    protected $signature = 'catalog:clone-site-draft-slice
                            {source-site : Active source site key}
                            {target-site : Active target site key}
                            {--expected-count= : Exact number of non-public source drafts expected}
                            {--apply : Create target drafts; default is dry-run}';

    protected $description = 'Clone shared product identities into a target site as safe non-public drafts';

    public function handle(): int
    {
        try {
            $source = $this->site((string) $this->argument('source-site'));
            $target = $this->site((string) $this->argument('target-site'));

            if ($source->is($target)) {
                throw new RuntimeException('Source and target sites must be different.');
            }

            $sourceDrafts = $this->sourceDrafts($source);
            $this->assertExpectedCount($sourceDrafts->count());

            if (! $this->option('apply')) {
                $existing = SiteProduct::query()
                    ->where('site_id', $target->id)
                    ->whereIn('product_id', $sourceDrafts->pluck('product_id'))
                    ->count();

                $this->info(sprintf(
                    'Dry-run passed: %d source draft(s) selected from %s; %d target draft(s) would be created for %s and %d existing target record(s) would be left untouched. No database records changed.',
                    $sourceDrafts->count(),
                    $source->key,
                    $sourceDrafts->count() - $existing,
                    $target->key,
                    $existing,
                ));

                return self::SUCCESS;
            }

            [$created, $existing] = DB::transaction(function () use ($source, $target): array {
                $drafts = $this->sourceDrafts($source, true);
                $this->assertExpectedCount($drafts->count());

                $created = 0;
                $existing = 0;

                foreach ($drafts as $sourceDraft) {
                    $targetDraft = SiteProduct::query()
                        ->where('site_id', $target->id)
                        ->where('product_id', $sourceDraft->product_id)
                        ->lockForUpdate()
                        ->first();

                    if ($targetDraft !== null) {
                        if ($targetDraft->is_published) {
                            throw new RuntimeException("Target site {$target->key} already publishes product {$sourceDraft->product_id}; it cannot be replaced by a draft clone.");
                        }

                        $existing++;

                        continue;
                    }

                    $product = $sourceDraft->product;
                    if (! $product instanceof Product) {
                        throw new RuntimeException("Source draft {$sourceDraft->id} has no shared product identity.");
                    }

                    // Do not copy source SiteProduct fields. Availability, price, SEO,
                    // ordering and the source slug are market-specific commercial data.
                    // The target gets only the shared product identity and a new safe slug.
                    SiteProduct::query()->create([
                        'site_id' => $target->id,
                        'product_id' => $product->id,
                        'slug' => $this->targetSlug($target, $product),
                        'is_published' => false,
                        'availability' => 'on_request',
                        'price' => null,
                        'seo' => null,
                        'sort_order' => 0,
                    ]);
                    $created++;
                }

                return [$created, $existing];
            });
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->info(sprintf(
            'Created %d non-public target draft(s) for %s from %s. Left %d existing target draft(s) untouched. No URLs, categories, contacts, commercial facts, prices or SEO data were copied.',
            $created,
            $target->key,
            $source->key,
            $existing,
        ));

        return self::SUCCESS;
    }

    private function site(string $key): Site
    {
        return Site::query()->where('key', $key)->where('is_active', true)->sole();
    }

    /** @return Collection<int, SiteProduct> */
    private function sourceDrafts(Site $source, bool $lockForUpdate = false): Collection
    {
        $query = SiteProduct::query()
            ->with('product')
            ->where('site_id', $source->id)
            ->where('is_published', false)
            ->orderBy('id');

        if ($lockForUpdate) {
            $query->lockForUpdate();
        }

        $drafts = $query->get();
        if ($drafts->isEmpty()) {
            throw new RuntimeException("Source site {$source->key} has no non-public product drafts.");
        }

        return $drafts;
    }

    private function assertExpectedCount(int $actual): void
    {
        $expected = (string) $this->option('expected-count');
        if ($expected === '' || ! ctype_digit($expected) || (int) $expected < 1) {
            throw new RuntimeException('The --expected-count option must be a positive integer safety check.');
        }
        if ((int) $expected !== $actual) {
            throw new RuntimeException("Expected {$expected} non-public source draft(s), found {$actual}.");
        }
    }

    private function targetSlug(Site $target, Product $product): string
    {
        $base = trim((string) $product->slug);
        if ($base === '') {
            $base = "product-{$product->id}";
        }

        $candidate = Str::limit($base, 255, '');
        $suffix = "-{$product->id}";
        $attempt = 1;

        while (SiteProduct::query()
            ->where('site_id', $target->id)
            ->where('slug', $candidate)
            ->where('product_id', '!=', $product->id)
            ->exists()) {
            $number = $attempt === 1 ? $suffix : "{$suffix}-{$attempt}";
            $candidate = Str::limit($base, 255 - strlen($number), '').$number;
            $attempt++;
        }

        return $candidate;
    }
}
