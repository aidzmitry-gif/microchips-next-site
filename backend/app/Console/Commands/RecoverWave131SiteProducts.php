<?php

namespace App\Console\Commands;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/** Recover the immutable 7,015-product 1C Wave131 shape as safe drafts only. */
class RecoverWave131SiteProducts extends Command
{
    private const SITE_KEY = 'microchips-by';

    private const SNAPSHOT_SHA256 = '0a4598bdb93f6ec54eb57ca75ce802574d93963a688010a2e8d56c6d3e86ca25';

    private const SNAPSHOT_ROWS = 7015;

    private const WAVE133_SHA256 = '19cadbd298f6326e8675e0b834730af7f198a203e05ec55027f554eabf408985';

    private const WAVE133_ROWS = 558;

    private const MANIFEST_SHA256 = 'e33e9d3183fc9514abdc16ad2d3623e3608aa0be9e864eac26f03dd838b4aa94';

    private const SOURCE_SHA256 = '03a2aa7469d818697608d9e79e077fe64e49b13ae5b6432b9631c663df4e9bf1';

    private const ASSIGNMENTS_SHA256 = '39b3c002d62c01bc1a776afb5a82a7902c4a30b0f2a6f11a22d2672f80aa31db';

    private const EXPECTED_MISSING = 6457;

    private const SCOPE_ASSIGNMENT_COUNTS = ['categorized' => 5876, 'unclassified' => 1139, 'electronics' => 925];

    private const MISSING_ASSIGNMENT_COUNTS = ['categorized' => 5388, 'unclassified' => 1069, 'electronics' => 925];

    private const WAVE133_PRESERVED_ELECTRONICS = 3;

    private const WAVE_HASHES = [
        'wave-001.csv' => 'c5db76e28a2871a9e7dc652786beb46e65b4278317f0dff44c32658908491ac6',
        'wave-002.csv' => 'e1992fab761f7023dcf1aef15732ec28cd95c676dd0492adccfd1befa2895af1',
        'wave-003.csv' => '9b3b9ccb65cfd97b71ba0774826cd415d75817d82daa034b351dd2b0b7b97fd6',
        'wave-004.csv' => '3ebf3c88ca9f9fae4dab8afbd8c436b1c8c2f0cad3a3885c48439cbbd077a02e',
        'wave-005.csv' => '156bc2a368be7e7f76ed3484dabd67c3f62ebea98fe4deefdc8c8b79d9273015',
        'wave-006.csv' => 'f9b1bebf44c9eb81b8eca75df91ae077cf92b0ab17c6f682ece7fe69d2b3df90',
        'wave-007.csv' => '08e02a2fdc30304cb8c8bd482085156c53540d9540a7be69c11f43b32ae856ac',
        'wave-008.csv' => '82d7940dbaef9319811ce3d9c3dade7c042e4ec054b836e248a43d0178fe62dd',
        'wave-009.csv' => '5d6ebfb25bbad6d81bf09be47b00ad8352f084350570e018585bb93442683511',
        'wave-010.csv' => '0bbc3caadbeb79ff7db2ebe5d41c9cf82433b78fe20b4d0d1f0b68bcd8ae3c8f',
        'wave-011.csv' => 'ca23420cfac95aaa4842e0aa4f17208929884bb69d8151bc09bff30295081eeb',
        'wave-012.csv' => '0d44cb71f15dce237aa5afb35162266d9926e2e61e256cb64586c7cd9ece10a4',
        'wave-013.csv' => 'e8f2861c5c87193638b1fb1a08f65adc5634dfbf272f836a836114bfa952612c',
        'wave-014.csv' => 'bbaa983073b36e751e5f55e0411c2c2a1a8405ad19cacd5e7bc3bd62ee4a59d8',
        'wave-015.csv' => '92cd62c75d63f512a3746fc618c3358ea0146eecea52bebbbfe2eecb752dfd6a',
        'wave-016.csv' => 'f69d6c254822958149aba1eeb593e8540f4b5b1283a3e06f7dd174a20cb21306',
        'wave-017.csv' => 'b25c9306205780bd9e4c9aa69245fed7f64ad22aa183e6a7838fa2448716c0ee',
        'wave-018.csv' => '3f3811e7c09134e5645b7a69906a02fadbb5ca56be8fa0a0331e1666480043d8',
        'wave-019.csv' => 'f49a94bc461a599ea619c7b9a59405162354a504022728e17378cd46c1d2f28f',
    ];

    protected $signature = 'catalog:recover-wave131-site-products
                            {site : Must be microchips-by}
                            {snapshot : Immutable rb-site-product-state-wave131.json}
                            {waves-dir : Directory containing manifest.json and 19 pinned wave CSV files}
                            {assignments : Pinned refresh-2 SEO assignment CSV}
                            {wave133 : Immutable 558-row Wave133 recovery baseline}
                            {--apply : Persist missing drafts; otherwise validate in a rolled-back transaction}';

    protected $description = 'Recover missing Wave131 1C products as unpublished drafts without legacy category 410';

    public function handle(): int
    {
        try {
            $site = $this->site();
            $scope = $this->scope((string) $this->argument('snapshot'));
            $waves = $this->waves((string) $this->argument('waves-dir'));
            $assignments = $this->assignments((string) $this->argument('assignments'));
            $wave133 = $this->wave133((string) $this->argument('wave133'));
            $this->assertTopology($scope, $waves, $wave133);
            $summary = $this->recover($site, $scope, $waves, $assignments, $wave133, (bool) $this->option('apply'));
            $this->line((string) json_encode([
                'mode' => $this->option('apply') ? 'apply' : 'dry_run', 'site' => $site->key,
                'records' => self::SNAPSHOT_ROWS, 'wave133_preserved' => self::WAVE133_ROWS,
                'expected_missing_against_wave133_shape' => self::EXPECTED_MISSING, ...$summary,
                'raw_legacy_410_links_created' => 0, 'urls_created' => 0, 'prices_created' => 0,
                'published_site_products_created' => 0,
            ], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    private function site(): Site
    {
        if ((string) $this->argument('site') !== self::SITE_KEY) {
            throw new RuntimeException('Wave131 recovery is restricted to site microchips-by.');
        }

        return Site::query()->where('key', self::SITE_KEY)->first()
            ?? throw new RuntimeException('Required site microchips-by does not exist.');
    }

    /** @return array<string, array<string,mixed>> */
    private function scope(string $path): array
    {
        $rows = $this->pinnedJsonList($path, self::SNAPSHOT_SHA256, self::SNAPSHOT_ROWS, 'Wave131 snapshot');
        $scope = [];
        foreach ($rows as $index => $row) {
            $externalId = $row['product']['external_id'] ?? null;
            if (($row['site_id'] ?? null) !== 1 || ! is_string($externalId) || trim($externalId) === '') {
                throw new RuntimeException("Wave131 row {$index} has invalid 1C topology.");
            }
            if (isset($scope[$externalId])) {
                throw new RuntimeException("Wave131 repeats 1C external_id {$externalId}.");
            }
            $scope[$externalId] = $row;
        }

        return $scope;
    }

    /** @return array<string, array{external_id:string,name:string,slug:string}> */
    private function waves(string $directory): array
    {
        $base = rtrim($directory, '/\\');
        $manifestPath = $base.DIRECTORY_SEPARATOR.'manifest.json';
        if (! is_file($manifestPath) || hash_file('sha256', $manifestPath) !== self::MANIFEST_SHA256) {
            throw new RuntimeException('Pinned 1C wave manifest is missing or changed.');
        }
        $manifest = json_decode((string) file_get_contents($manifestPath), true, 512, JSON_THROW_ON_ERROR);
        if (($manifest['source_sha256'] ?? null) !== self::SOURCE_SHA256
            || ($manifest['accepted_products'] ?? null) !== 9084 || count($manifest['waves'] ?? []) !== 19) {
            throw new RuntimeException('Pinned 1C wave manifest contract drifted.');
        }
        $products = [];
        foreach ($manifest['waves'] as $index => $wave) {
            $file = $wave['file'] ?? '';
            if (! isset(self::WAVE_HASHES[$file])) {
                throw new RuntimeException("Unexpected 1C wave file at manifest index {$index}.");
            }
            $path = $base.DIRECTORY_SEPARATOR.$file;
            if (! is_file($path) || hash_file('sha256', $path) !== self::WAVE_HASHES[$file]) {
                throw new RuntimeException("Pinned 1C wave {$file} is missing or changed.");
            }
            $handle = fopen($path, 'rb');
            if ($handle === false) {
                throw new RuntimeException("Cannot read {$file}.");
            }
            try {
                $header = fgetcsv($handle, 0, ';');
                if ($header === false) {
                    throw new RuntimeException("Wave {$file} has no header.");
                }
                $header[0] = preg_replace('/^\xEF\xBB\xBF/', '', (string) $header[0]);
                if ($header !== ['external_id', 'name', 'slug']) {
                    throw new RuntimeException("Wave {$file} header drifted.");
                }
                $loaded = [];
                while (($values = fgetcsv($handle, 0, ';')) !== false) {
                    if (count($values) !== 3) {
                        throw new RuntimeException("Wave {$file} contains a ragged row.");
                    }
                    [$externalId, $name, $slug] = $values;
                    if ($externalId === '' || $name === '' || $slug === '' || isset($products[$externalId])) {
                        throw new RuntimeException("Wave {$file} contains blank or duplicate identity.");
                    }
                    $loaded[] = $externalId;
                    $products[$externalId] = compact('externalId', 'name', 'slug') + ['external_id' => $externalId];
                }
                if (count($loaded) !== $wave['count'] || $loaded[0] !== $wave['first_external_id']
                    || $loaded[array_key_last($loaded)] !== $wave['last_external_id']) {
                    throw new RuntimeException("Wave {$file} cardinality/boundary drifted.");
                }
            } finally {
                fclose($handle);
            }
        }
        if (count($products) !== 9084) {
            throw new RuntimeException('Pinned waves must contain 9,084 unique products.');
        }

        return $products;
    }

    /** @return array<string,string> */
    private function assignments(string $path): array
    {
        if (! is_file($path) || hash_file('sha256', $path) !== self::ASSIGNMENTS_SHA256) {
            throw new RuntimeException('Pinned refresh-2 SEO assignments are missing or changed.');
        }
        $handle = fopen($path, 'rb');
        if ($handle === false) {
            throw new RuntimeException('Cannot read SEO assignments.');
        }
        $result = [];
        try {
            $header = fgetcsv($handle);
            if ($header === false) {
                throw new RuntimeException('SEO assignments have no header.');
            }
            $header[0] = preg_replace('/^\xEF\xBB\xBF/', '', (string) $header[0]);
            if ($header !== ['product_external_id', 'category_external_id']) {
                throw new RuntimeException('SEO assignment header drifted.');
            }
            while (($row = fgetcsv($handle)) !== false) {
                if (count($row) !== 2 || $row[0] === '' || ! str_starts_with($row[1], 'seo:') || isset($result[$row[0]])) {
                    throw new RuntimeException('SEO assignments contain a blank, legacy, or duplicate row.');
                }
                $result[$row[0]] = $row[1];
            }
        } finally {
            fclose($handle);
        }
        if (count($result) !== 6120) {
            throw new RuntimeException('SEO assignments must contain 6,120 unique rows.');
        }

        return $result;
    }

    /** @return array<string,array<string,mixed>> */
    private function wave133(string $path): array
    {
        $rows = $this->pinnedJsonList($path, self::WAVE133_SHA256, self::WAVE133_ROWS, 'Wave133 baseline');
        $result = [];
        foreach ($rows as $row) {
            $externalId = $row['product']['external_id'] ?? null;
            if (! is_string($externalId) || isset($result[$externalId])) {
                throw new RuntimeException('Wave133 baseline identity drifted.');
            }
            $result[$externalId] = $row;
        }

        return $result;
    }

    /** @return list<array<string,mixed>> */
    private function pinnedJsonList(string $path, string $hash, int $count, string $label): array
    {
        if (! is_file($path) || hash_file('sha256', $path) !== $hash) {
            throw new RuntimeException("{$label} SHA-256 mismatch.");
        }
        $rows = json_decode((string) file_get_contents($path), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($rows) || ! array_is_list($rows) || count($rows) !== $count) {
            throw new RuntimeException("{$label} row count drifted.");
        }

        return $rows;
    }

    /** @param array<string,array<string,mixed>> $scope @param array<string,array<string,mixed>> $waves
     * @param array<string,array<string,mixed>> $wave133 */
    private function assertTopology(array $scope, array $waves, array $wave133): void
    {
        if (array_diff_key($scope, $waves) !== []) {
            throw new RuntimeException('Wave131 contains an ID absent from pinned 1C waves.');
        }
        if (array_diff_key($wave133, $scope) !== [] || count(array_diff_key($scope, $wave133)) !== self::EXPECTED_MISSING) {
            throw new RuntimeException('Wave133 must be the exact 558-row subset of the 7,015-row Wave131 scope.');
        }
    }

    /** @return array<string,int> */
    private function recover(Site $site, array $scope, array $waves, array $assignments, array $wave133, bool $apply): array
    {
        $summary = ['products_created' => 0, 'site_products_created' => 0, 'category_links_created' => 0,
            'unchanged_missing_rows' => 0, 'missing_scope_categorized' => 0, 'missing_scope_unclassified' => 0,
            'missing_scope_electronics' => 0, 'assignment_scope_categorized' => 0,
            'assignment_scope_unclassified' => 0, 'assignment_scope_electronics' => 0,
            'missing_assignment_categorized' => 0, 'missing_assignment_unclassified' => 0,
            'missing_assignment_electronics' => 0,
            'wave133_preserved_electronics' => self::WAVE133_PRESERVED_ELECTRONICS,
            'expected_total_electronics_links_when_all_assignment_categories_exist' => 928];
        $categories = SiteCategory::query()->where('site_id', $site->id)->get()->keyBy('external_id');
        foreach ($scope as $externalId => $_) {
            if (isset($assignments[$externalId])) {
                $summary['assignment_scope_categorized']++;
            } else {
                $summary['assignment_scope_unclassified']++;
            }
            if (($assignments[$externalId] ?? null) === 'seo:electronic-components') {
                $summary['assignment_scope_electronics']++;
            }
        }
        foreach (array_diff_key($scope, $wave133) as $externalId => $_) {
            if (isset($assignments[$externalId])) {
                $summary['missing_assignment_categorized']++;
            } else {
                $summary['missing_assignment_unclassified']++;
            }
            if (($assignments[$externalId] ?? null) === 'seo:electronic-components') {
                $summary['missing_assignment_electronics']++;
            }
        }
        if ([$summary['assignment_scope_categorized'], $summary['assignment_scope_unclassified'], $summary['assignment_scope_electronics']]
                !== array_values(self::SCOPE_ASSIGNMENT_COUNTS)
            || [$summary['missing_assignment_categorized'], $summary['missing_assignment_unclassified'], $summary['missing_assignment_electronics']]
                !== array_values(self::MISSING_ASSIGNMENT_COUNTS)
            || collect($wave133)->sum(fn (array $row): int => collect($row['categories'])->contains('external_id', 'seo:electronic-components') ? 1 : 0)
                !== self::WAVE133_PRESERVED_ELECTRONICS) {
            throw new RuntimeException('Pinned Wave131 assignment/electronics counters drifted.');
        }
        DB::beginTransaction();
        try {
            foreach ($wave133 as $externalId => $row) {
                $this->assertWave133Exact($site, $externalId, $row);
            }
            foreach (array_diff_key($scope, $wave133) as $externalId => $_) {
                $category = isset($assignments[$externalId]) ? $categories->get($assignments[$externalId]) : null;
                if ($category) {
                    $summary['missing_scope_categorized']++;
                    if ($category->external_id === 'seo:electronic-components') {
                        $summary['missing_scope_electronics']++;
                    }
                } else {
                    $summary['missing_scope_unclassified']++;
                }
                $this->recoverMissing($site, $externalId, $waves[$externalId], $category, $summary);
            }
            if ($apply) {
                DB::commit();
            } else {
                DB::rollBack();
            }
        } catch (Throwable $error) {
            DB::rollBack();
            throw $error;
        }

        return $summary;
    }

    private function assertWave133Exact(Site $site, string $externalId, array $row): void
    {
        $product = Product::query()->where('external_id', $externalId)->first()
            ?? throw new RuntimeException("Required Wave133 product {$externalId} is missing.");
        $source = $row['product'];
        $expected = ['sku' => $source['sku'] ?? null, 'mpn' => $source['mpn'] ?? null,
            'manufacturer' => $source['manufacturer'] ?? null, 'slug' => $source['slug'], 'name' => $source['name'],
            'short_description' => $source['short_description'] ?? null, 'status' => $source['status']];
        foreach ($expected as $field => $value) {
            if ($product->getAttribute($field) !== $value) {
                throw new RuntimeException("Wave133 product {$externalId} {$field} conflicts with its immutable baseline.");
            }
        }
        if ($this->stable($product->technical_attributes) !== $this->stable($source['technical_attributes'] ?? null)) {
            throw new RuntimeException("Wave133 product {$externalId} technical attributes conflict with its immutable baseline.");
        }
        $sp = SiteProduct::query()->where('site_id', $site->id)->where('product_id', $product->id)->first()
            ?? throw new RuntimeException("Required Wave133 site product {$externalId} is missing.");
        if ($sp->slug !== $row['slug'] || $sp->is_published || $sp->availability !== 'on_request'
            || $sp->price !== null || $sp->seo !== null) {
            throw new RuntimeException("Wave133 site product {$externalId} is not the exact safe recovery draft.");
        }
        $expectedCategories = collect($row['categories'])->pluck('external_id')->sort()->values()->all();
        $actualCategories = $sp->categories()->pluck('external_id')->sort()->values()->all();
        if ($actualCategories !== $expectedCategories || $this->hasUrl($site, $sp)) {
            throw new RuntimeException("Wave133 site product {$externalId} category/URL state conflicts with recovery baseline.");
        }
    }

    /** @param array<string,int> $summary */
    private function recoverMissing(Site $site, string $externalId, array $wave, ?SiteCategory $category, array &$summary): void
    {
        $expected = ['external_id' => $externalId, 'sku' => null, 'mpn' => null, 'manufacturer' => null,
            'slug' => $wave['slug'], 'name' => $wave['name'], 'short_description' => null,
            'technical_attributes' => null, 'status' => 'active'];
        $product = Product::query()->where('external_id', $externalId)->first();
        if (! $product) {
            if (Product::query()->where('slug', $wave['slug'])->exists()) {
                throw new RuntimeException("1C product slug conflict for {$externalId}.");
            }
            $product = Product::query()->create($expected);
            $summary['products_created']++;
        } else {
            foreach ($expected as $field => $value) {
                if ($product->getAttribute($field) !== $value) {
                    throw new RuntimeException("Existing 1C product {$externalId} {$field} conflicts with pinned wave source.");
                }
            }
        }
        $sp = SiteProduct::query()->where('site_id', $site->id)->where('product_id', $product->id)->first();
        if (! $sp) {
            if (SiteProduct::query()->where('site_id', $site->id)->where('slug', $wave['slug'])->exists()) {
                throw new RuntimeException("1C site slug conflict for {$externalId}.");
            }
            $sp = SiteProduct::withoutEvents(fn (): SiteProduct => SiteProduct::query()->create([
                'site_id' => $site->id, 'product_id' => $product->id,
                'slug' => $wave['slug'], 'is_published' => false, 'availability' => 'on_request',
                'price' => null, 'seo' => null, 'sort_order' => 0,
            ]));
            $summary['site_products_created']++;
        } elseif ($sp->slug !== $wave['slug'] || $sp->is_published || $sp->availability !== 'on_request'
            || $sp->price !== null || $sp->seo !== null) {
            throw new RuntimeException("Existing 1C site product {$externalId} conflicts with safe draft contract.");
        }
        $actual = $sp->categories()->pluck('external_id')->sort()->values()->all();
        $expectedCategory = $category ? [$category->external_id] : [];
        if ($actual === [] && $category) {
            $sp->categories()->attach($category->id, ['site_id' => $site->id]);
            $summary['category_links_created']++;
        } elseif ($actual !== $expectedCategory) {
            throw new RuntimeException("Existing 1C site product {$externalId} has a non-SEO or stale category assignment.");
        } elseif (! $product->wasRecentlyCreated && ! $sp->wasRecentlyCreated) {
            $summary['unchanged_missing_rows']++;
        }
        if ($this->hasUrl($site, $sp)) {
            throw new RuntimeException("Existing 1C site product {$externalId} has a forbidden URL.");
        }
    }

    private function hasUrl(Site $site, SiteProduct $sp): bool
    {
        return SiteUrl::query()->where('site_id', $site->id)->where('target_type', 'product')->where('target_id', $sp->id)->exists();
    }

    private function stable(mixed $value): string
    {
        if (is_array($value)) {
            if (! array_is_list($value)) {
                ksort($value);
            }
            foreach ($value as $key => $item) {
                if (is_array($item)) {
                    $value[$key] = json_decode($this->stable($item), true, 512, JSON_THROW_ON_ERROR);
                }
            }
        }

        return (string) json_encode($value, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
    }
}
