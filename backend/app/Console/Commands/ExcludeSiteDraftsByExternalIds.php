<?php

namespace App\Console\Commands;

use App\Models\ImportRun;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/** Removes only an unpublished market link; it never deletes canonical products. */
class ExcludeSiteDraftsByExternalIds extends Command
{
    protected $signature = 'catalog:exclude-site-drafts
                            {site : Site key}
                            {file : CSV containing product_external_id}
                            {--apply : Remove validated non-public site drafts; otherwise roll back}';

    protected $description = 'Exclude explicit out-of-scope products from one site without deleting shared catalogue identities';

    public function handle(): int
    {
        $site = Site::query()->where('key', (string) $this->argument('site'))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }
        $apply = (bool) $this->option('apply');
        $run = ImportRun::create(['source' => 'site_draft_scope_exclusion_csv', 'source_file' => basename((string) $this->argument('file')), 'status' => 'running', 'started_at' => now()]);

        try {
            $ids = $this->externalIds((string) $this->argument('file'));
            $drafts = SiteProduct::query()->with('product')
                ->where('site_id', $site->id)
                ->whereHas('product', fn ($query) => $query->whereIn('external_id', $ids))
                ->get();
            if ($drafts->count() !== count($ids)) {
                $found = $drafts->pluck('product.external_id')->filter()->all();
                $missing = array_values(array_diff($ids, $found));
                throw new RuntimeException('Some requested products are not linked to this site: '.implode(', ', array_slice($missing, 0, 10)));
            }
            if ($drafts->contains(fn (SiteProduct $draft): bool => $draft->is_published)) {
                throw new RuntimeException('A published product cannot be excluded by this draft-only command.');
            }

            if ($apply) {
                DB::transaction(fn () => SiteProduct::query()->whereIn('id', $drafts->pluck('id'))->delete());
            }
            $run->update([
                'status' => $apply ? 'completed' : 'dry_run_complete',
                'total_records' => count($ids),
                'processed_records' => $apply ? count($ids) : 0,
                'summary' => ['mode' => $apply ? 'apply' : 'dry_run', 'site_key' => $site->key, 'excluded_site_drafts' => count($ids), 'canonical_products_deleted' => 0, 'published_products_changed' => 0],
                'finished_at' => now(),
            ]);
            $this->info(sprintf('%s %d non-public %s drafts; canonical products and other markets were not changed.', $apply ? 'Excluded' : 'Validated', count($ids), $site->key));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $run->update(['status' => 'failed', 'summary' => ['mode' => $apply ? 'apply' : 'dry_run', 'error' => $error->getMessage()], 'finished_at' => now()]);
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /** @return list<string> */
    private function externalIds(string $file): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Scope exclusion CSV is not readable.');
        }
        $handle = fopen($file, 'rb');
        if ($handle === false) {
            throw new RuntimeException('Scope exclusion CSV cannot be opened.');
        }
        try {
            $header = fgetcsv($handle);
            if ($header === false) {
                throw new RuntimeException('Scope exclusion CSV has no header.');
            }
            $header = array_map(static fn ($value): string => mb_strtolower(ltrim(trim((string) $value), "\xEF\xBB\xBF")), $header);
            $index = array_search('product_external_id', $header, true);
            if ($index === false) {
                throw new RuntimeException('Scope exclusion CSV requires product_external_id.');
            }
            $ids = [];
            while (($row = fgetcsv($handle)) !== false) {
                $id = trim((string) ($row[$index] ?? ''));
                if ($id === '' || mb_strlen($id) > 255 || isset($ids[$id])) {
                    throw new RuntimeException('Scope exclusion CSV has an empty, overlong or duplicate product_external_id.');
                }
                $ids[$id] = true;
            }
            if ($ids === []) {
                throw new RuntimeException('Scope exclusion CSV has no product rows.');
            }

            return array_keys($ids);
        } finally {
            fclose($handle);
        }
    }
}
