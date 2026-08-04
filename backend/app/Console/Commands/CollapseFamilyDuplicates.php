<?php

namespace App\Console\Commands;

use App\Events\SiteContentChanged;
use App\Models\Product;
use App\Models\ProductFamily;
use App\Models\ProductVariant;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\SiteSeo;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/**
 * Removes only a reviewed duplicate market row that was previously modelled
 * as a family option. Shared product identities and other markets are kept.
 */
class CollapseFamilyDuplicates extends Command
{
    protected $signature = 'catalog:collapse-family-duplicates
                            {site : Site key}
                            {file : CSV containing duplicate_external_id and survivor_external_id}
                            {--apply : Persist the reviewed collapse; default is dry-run}';

    protected $description = 'Collapse explicit false family variants into their canonical survivor without deleting shared products';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $rows = $this->rows((string) $this->argument('file'));
            $summary = $this->collapse($site, $rows, (bool) $this->option('apply'));
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /**
     * @param  list<array{duplicate_external_id:string,survivor_external_id:string}>  $rows
     * @return array{mode:string,requested:int,collapsed:int,already_collapsed:int,site_products_deleted:int,shared_products_deleted:int}
     */
    private function collapse(Site $site, array $rows, bool $apply): array
    {
        $plans = [];
        $alreadyCollapsed = 0;
        $revalidationPaths = [];

        foreach ($rows as $row) {
            $survivor = $this->siteProduct($site, $row['survivor_external_id']);
            $revalidationPaths = [
                ...$revalidationPaths,
                ...SiteUrl::query()
                    ->where('site_id', $site->id)
                    ->where('target_type', 'product')
                    ->where('target_id', $survivor->id)
                    ->pluck('path')
                    ->all(),
            ];
            $duplicateProduct = Product::query()->where('external_id', $row['duplicate_external_id'])->sole();
            if ($duplicateProduct->is($survivor->product)) {
                throw new RuntimeException("Duplicate {$row['duplicate_external_id']} cannot equal its survivor.");
            }

            $duplicate = SiteProduct::query()
                ->with(['product.media', 'priceEvidences'])
                ->where('site_id', $site->id)
                ->where('product_id', $duplicateProduct->id)
                ->first();
            $variant = ProductVariant::query()
                ->with('family')
                ->where('product_id', $duplicateProduct->id)
                ->whereHas('family', fn ($query) => $query->where('site_id', $site->id))
                ->first();

            if ($duplicate === null) {
                if ($variant !== null) {
                    throw new RuntimeException("Duplicate {$row['duplicate_external_id']} has no site row but still has a family relation.");
                }
                $alreadyCollapsed++;

                continue;
            }
            if ($variant === null || $variant->family === null || $variant->family->site_id !== $site->id || $variant->family->canonical_product_id !== $survivor->product_id) {
                throw new RuntimeException("Duplicate {$row['duplicate_external_id']} is not an explicit variant of survivor {$row['survivor_external_id']}.");
            }
            if (SiteUrl::query()->where('site_id', $site->id)->where('target_type', 'product')->where('target_id', $duplicate->id)->exists()) {
                throw new RuntimeException("Duplicate {$row['duplicate_external_id']} has a URL and cannot be collapsed by this command.");
            }
            if (SiteSeo::query()->where('site_id', $site->id)->where('resource_type', 'product')->where('resource_id', $duplicate->id)->exists()) {
                throw new RuntimeException("Duplicate {$row['duplicate_external_id']} has SEO state and cannot be collapsed by this command.");
            }
            if ($duplicate->price !== null || $duplicate->priceEvidences->isNotEmpty()) {
                throw new RuntimeException("Duplicate {$row['duplicate_external_id']} has price evidence that must be reviewed before collapse.");
            }
            if ($duplicateProduct->media->contains(fn ($media): bool => $media->verification_status === 'verified' && $media->is_published && filled($media->storage_path) && filled($media->rights_basis))) {
                throw new RuntimeException("Duplicate {$row['duplicate_external_id']} has storefront media that must be reviewed before collapse.");
            }

            $plans[] = ['site_product' => $duplicate, 'variant' => $variant, 'family_id' => $variant->product_family_id];
        }

        $work = function () use ($plans): void {
            foreach ($plans as $plan) {
                $familyId = $plan['family_id'];
                $plan['variant']->delete();
                $plan['site_product']->delete();
                if (! ProductVariant::query()->where('product_family_id', $familyId)->exists()) {
                    ProductFamily::query()->whereKey($familyId)->delete();
                }
            }
        };

        if ($apply) {
            DB::transaction($work);
            SiteContentChanged::dispatch($site, array_values(array_unique([...$revalidationPaths, '/catalog', '/sitemap.xml'])));
        } else {
            DB::beginTransaction();
            try {
                $work();
            } finally {
                DB::rollBack();
            }
        }

        return [
            'mode' => $apply ? 'apply' : 'dry_run',
            'requested' => count($rows),
            'collapsed' => count($plans),
            'already_collapsed' => $alreadyCollapsed,
            'site_products_deleted' => $apply ? count($plans) : 0,
            'shared_products_deleted' => 0,
        ];
    }

    private function siteProduct(Site $site, string $externalId): SiteProduct
    {
        return SiteProduct::query()
            ->with('product')
            ->where('site_id', $site->id)
            ->whereHas('product', fn ($query) => $query->where('external_id', $externalId))
            ->sole();
    }

    /** @return list<array{duplicate_external_id:string,survivor_external_id:string}> */
    private function rows(string $file): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Family duplicate CSV is not readable.');
        }
        $handle = fopen($file, 'rb');
        if ($handle === false) {
            throw new RuntimeException('Family duplicate CSV cannot be opened.');
        }

        try {
            $header = fgetcsv($handle);
            if ($header === false) {
                throw new RuntimeException('Family duplicate CSV has no header.');
            }
            $header = array_map(static fn ($value): string => mb_strtolower(ltrim(trim((string) $value), "\xEF\xBB\xBF")), $header);
            $duplicateIndex = array_search('duplicate_external_id', $header, true);
            $survivorIndex = array_search('survivor_external_id', $header, true);
            if ($duplicateIndex === false || $survivorIndex === false) {
                throw new RuntimeException('Family duplicate CSV requires duplicate_external_id and survivor_external_id.');
            }

            $rows = [];
            $seen = [];
            while (($row = fgetcsv($handle)) !== false) {
                $duplicate = trim((string) ($row[$duplicateIndex] ?? ''));
                $survivor = trim((string) ($row[$survivorIndex] ?? ''));
                if ($duplicate === '' || $survivor === '' || mb_strlen($duplicate) > 255 || mb_strlen($survivor) > 255 || isset($seen[$duplicate])) {
                    throw new RuntimeException('Family duplicate CSV has an empty, overlong or repeated identity.');
                }
                $seen[$duplicate] = true;
                $rows[] = ['duplicate_external_id' => $duplicate, 'survivor_external_id' => $survivor];
            }
            if ($rows === []) {
                throw new RuntimeException('Family duplicate CSV has no product rows.');
            }

            return $rows;
        } finally {
            fclose($handle);
        }
    }
}
