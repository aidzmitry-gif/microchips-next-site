<?php

namespace App\Console\Commands;

use App\Domain\Content\ModelCoreIdentityMatcher;
use App\Domain\Imports\ProductIdentity;
use App\Models\Product;
use App\Models\ProductMedia;
use App\Models\Site;
use App\Models\SiteProduct;
use Illuminate\Console\Command;
use RuntimeException;
use Throwable;

/** Export review candidates only; this command never promotes or mutates media. */
class ExportEnrichmentLegacyPreviewMedia extends Command
{
    private const SOURCE_KIND = 'legacy_bitrix_exact_element_preview';

    /** @var list<string> */
    private const DEFAULT_REVIEW_LEDGERS = [
        'docs/audits/generated/rb-reviewed-legacy-preview-media-wave225.csv',
        'docs/audits/generated/rb-reviewed-legacy-preview-media-wave226.csv',
        'docs/audits/generated/rb-wave237-reviewed-media-skip-ledger.csv',
        'docs/audits/generated/rb-reviewed-legacy-preview-media-wave246.csv',
    ];

    /** @var list<string> */
    private const OUTPUT_FIELDS = [
        'external_id', 'media_id', 'storage_path', 'content_sha256', 'rights_basis',
        'identity_scope', 'mpn', 'model_core', 'manufacturer',
    ];

    protected $signature = 'media:export-enrichment-legacy-preview-candidates
                            {site : Site key whose SiteProduct must be published}
                            {queue : Current enrichment queue CSV with product_external_id}
                            {output : Destination read-only candidate CSV}
                            {--review-ledger=* : Reviewed-media ledger CSVs to exclude; repository defaults are used when omitted}';

    protected $description = 'Export unreviewed company-owned legacy_exact_preview media for published enrichment-queue products';

    public function handle(): int
    {
        $site = Site::query()->where('key', trim((string) $this->argument('site')))->first();
        if ($site === null) {
            $this->error('Site was not found.');

            return self::FAILURE;
        }

        try {
            $summary = $this->export($site, (string) $this->argument('queue'), (string) $this->argument('output'));
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        foreach (explode("\n", (string) json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE)) as $line) {
            $this->line($line);
        }

        return self::SUCCESS;
    }

    /** @return array{mode: string, queue_products: int, exported_media: int, excluded_reviewed_media: int, skipped_unpublished_products: int, skipped_without_pinned_identity: int, database_mutations: int} */
    private function export(Site $site, string $queuePath, string $output): array
    {
        $queue = $this->readQueue($queuePath);
        $reviewedMedia = $this->readReviewedMedia($this->reviewLedgerPaths());
        $products = Product::query()->whereIn('external_id', array_keys($queue))->get()->keyBy('external_id');
        $publishedProductIds = SiteProduct::query()
            ->where('site_id', $site->id)
            ->where('is_published', true)
            ->whereIn('product_id', $products->pluck('id'))
            ->pluck('product_id')
            ->flip();
        $mediaByProduct = ProductMedia::query()
            ->whereIn('product_id', $publishedProductIds->keys())
            ->where('kind', 'image')
            ->where('source_kind', self::SOURCE_KIND)
            ->where('verification_status', ProductMedia::STATUS_LEGACY_EXACT_PREVIEW)
            ->where('is_published', true)
            ->orderBy('id')
            ->get()
            ->groupBy('product_id');

        $rows = [];
        $summary = [
            'mode' => 'read_only_export',
            'queue_products' => count($queue),
            'exported_media' => 0,
            'excluded_reviewed_media' => 0,
            'skipped_unpublished_products' => 0,
            'skipped_without_pinned_identity' => 0,
            'database_mutations' => 0,
        ];
        foreach ($queue as $externalId => $queueRow) {
            /** @var Product|null $product */
            $product = $products->get($externalId);
            if ($product === null || ! $publishedProductIds->has($product->id)) {
                $summary['skipped_unpublished_products']++;

                continue;
            }
            $identity = $this->pinnedIdentity($product, $queueRow, $externalId);
            if ($identity === null) {
                $summary['skipped_without_pinned_identity']++;

                continue;
            }
            foreach ($mediaByProduct->get($product->id, collect()) as $media) {
                /** @var ProductMedia $media */
                $key = $externalId.'|'.$media->id;
                if (isset($reviewedMedia[$key])) {
                    $summary['excluded_reviewed_media']++;

                    continue;
                }
                if (! $this->hasCompanyOwnedPinnedMediaFields($media)) {
                    continue;
                }
                $rows[] = [
                    'external_id' => $externalId,
                    'media_id' => (string) $media->id,
                    'storage_path' => $media->storage_path,
                    'content_sha256' => strtolower((string) $media->content_sha256),
                    'rights_basis' => $media->rights_basis,
                    'identity_scope' => $identity['identity_scope'],
                    'mpn' => $identity['mpn'],
                    'model_core' => $identity['model_core'],
                    'manufacturer' => $identity['manufacturer'],
                ];
            }
        }
        $this->writeCsv($output, $rows);
        $summary['exported_media'] = count($rows);

        return $summary;
    }

    /** @return array<string, array<string, string>> keyed by product_external_id */
    private function readQueue(string $path): array
    {
        $rows = $this->readCsv($path, 'Enrichment queue');
        if (! array_key_exists('product_external_id', $rows['header'])) {
            throw new RuntimeException('Enrichment queue must contain product_external_id.');
        }
        $queue = [];
        foreach ($rows['records'] as $line => $row) {
            $externalId = trim($row['product_external_id'] ?? '');
            if ($externalId === '' || isset($queue[$externalId])) {
                throw new RuntimeException("Enrichment queue has an empty or duplicate product_external_id at line {$line}.");
            }
            $queue[$externalId] = $row;
        }
        if ($queue === []) {
            throw new RuntimeException('Enrichment queue must contain at least one product_external_id.');
        }

        return $queue;
    }

    /** @param list<string> $paths @return array<string, true> */
    private function readReviewedMedia(array $paths): array
    {
        $reviewed = [];
        foreach ($paths as $path) {
            $csv = $this->readCsv($path, 'Reviewed-media ledger');
            foreach (['external_id', 'media_id'] as $field) {
                if (! array_key_exists($field, $csv['header'])) {
                    throw new RuntimeException("Reviewed-media ledger must contain {$field}.");
                }
            }
            foreach ($csv['records'] as $line => $row) {
                $externalId = trim($row['external_id'] ?? '');
                $mediaId = trim($row['media_id'] ?? '');
                if ($externalId === '' || ! ctype_digit($mediaId) || (int) $mediaId < 1) {
                    throw new RuntimeException("Reviewed-media ledger has an invalid external_id or media_id at line {$line}.");
                }
                $reviewed[$externalId.'|'.(int) $mediaId] = true;
            }
        }

        return $reviewed;
    }

    /** @return array{identity_scope: string, mpn: string, model_core: string, manufacturer: string}|null */
    private function pinnedIdentity(Product $product, array $queueRow, string $externalId): ?array
    {
        $queueMpn = trim($queueRow['mpn'] ?? '');
        $queueModelCore = trim($queueRow['model_core'] ?? '');
        if ($queueMpn !== '' && $queueModelCore !== '') {
            throw new RuntimeException("Enrichment queue identity is ambiguous for {$externalId}.");
        }

        $productMpn = trim((string) $product->mpn);
        if ($productMpn !== '') {
            if ($queueMpn !== '' && ProductIdentity::normalize($queueMpn) !== ProductIdentity::normalize($productMpn)) {
                throw new RuntimeException("Enrichment queue MPN drifts from product {$externalId}.");
            }
            if (! ModelCoreIdentityMatcher::nameContains($product->name, $productMpn)) {
                return null;
            }

            return ['identity_scope' => 'exact', 'mpn' => $productMpn, 'model_core' => '', 'manufacturer' => ''];
        }
        if ($queueMpn !== '' || $queueModelCore === '') {
            return null;
        }

        $queueManufacturer = trim($queueRow['manufacturer'] ?? '');
        $manufacturer = trim((string) $product->manufacturer) ?: $queueManufacturer;
        if ($manufacturer === ''
            || ($queueManufacturer !== '' && filled($product->manufacturer)
                && ProductIdentity::normalize($queueManufacturer) !== ProductIdentity::normalize((string) $product->manufacturer))
            || ! ModelCoreIdentityMatcher::nameContains($product->name, $queueModelCore)
            || ! ModelCoreIdentityMatcher::nameContains($product->name, $manufacturer)) {
            return null;
        }

        return ['identity_scope' => 'model_core', 'mpn' => '', 'model_core' => $queueModelCore, 'manufacturer' => $manufacturer];
    }

    private function hasCompanyOwnedPinnedMediaFields(ProductMedia $media): bool
    {
        $rights = trim((string) $media->rights_basis);
        $hash = strtolower(trim((string) $media->content_sha256));

        return trim((string) $media->storage_path) !== ''
            && str_contains(mb_strtolower($rights), 'company-owned')
            && preg_match('/^[a-f0-9]{64}$/', $hash) === 1;
    }

    /** @return list<string> */
    private function reviewLedgerPaths(): array
    {
        $paths = [];
        foreach ((array) $this->option('review-ledger') as $path) {
            $path = trim((string) $path);
            if ($path !== '') {
                $paths[] = $path;
            }
        }

        if ($paths === []) {
            $paths = array_map(static fn (string $path): string => base_path('../'.$path), self::DEFAULT_REVIEW_LEDGERS);
        }

        return array_values(array_unique($paths));
    }

    /** @return array{header: array<string, int>, records: array<int, array<string, string>>} */
    private function readCsv(string $path, string $label): array
    {
        if (! is_file($path) || ! is_readable($path)) {
            throw new RuntimeException("{$label} must be a readable CSV file.");
        }
        $handle = fopen($path, 'rb');
        if ($handle === false) {
            throw new RuntimeException("{$label} must be a readable CSV file.");
        }
        try {
            $header = fgetcsv($handle, 0, ',', '"', '');
            if ($header === false) {
                throw new RuntimeException("{$label} must contain a CSV header.");
            }
            $columns = [];
            foreach ($header as $index => $field) {
                $field = trim((string) $field);
                $field = preg_replace('/^\xEF\xBB\xBF/', '', $field) ?? $field;
                if ($field === '' || isset($columns[$field])) {
                    throw new RuntimeException("{$label} header is empty or duplicated.");
                }
                $columns[$field] = $index;
            }
            $records = [];
            $line = 1;
            while (($values = fgetcsv($handle, 0, ',', '"', '')) !== false) {
                $line++;
                if ($values === [null]) {
                    continue;
                }
                if (count($values) !== count($columns)) {
                    throw new RuntimeException("{$label} has a malformed row at line {$line}.");
                }
                $row = [];
                foreach ($columns as $field => $index) {
                    $row[$field] = trim((string) $values[$index]);
                }
                $records[$line] = $row;
            }

            return ['header' => $columns, 'records' => $records];
        } finally {
            fclose($handle);
        }
    }

    /** @param list<array<string, string>> $rows */
    private function writeCsv(string $path, array $rows): void
    {
        $directory = dirname($path);
        if (! is_dir($directory) && ! mkdir($directory, 0777, true) && ! is_dir($directory)) {
            throw new RuntimeException('Unable to create candidate export directory.');
        }
        $handle = fopen($path, 'wb');
        if ($handle === false) {
            throw new RuntimeException('Unable to create candidate export CSV.');
        }
        try {
            fwrite($handle, "\xEF\xBB\xBF");
            fputcsv($handle, self::OUTPUT_FIELDS, ',', '"', '');
            foreach ($rows as $row) {
                fputcsv($handle, $row, ',', '"', '');
            }
        } finally {
            fclose($handle);
        }
    }
}
