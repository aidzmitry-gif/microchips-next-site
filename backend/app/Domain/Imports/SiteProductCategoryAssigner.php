<?php

namespace App\Domain\Imports;

use App\Models\Product;
use App\Models\Site;
use App\Models\SiteCategory;
use App\Models\SiteCategoryProduct;
use App\Models\SiteProduct;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/**
 * Assigns already-staged site products into an already-imported site category
 * tree. This tool never creates products, site products or categories: those
 * remain the responsibility of the staging pipeline and
 * SiteCategoryTaxonomyImporter. It only links the two and, optionally,
 * records a battery chemistry value (AGM/GEL) taken from the CSV's own
 * 'chemistry'/'technology' column for that row.
 *
 * Honesty note: this class has NO category-to-chemistry mapping and never
 * compares the CSV's chemistry value against the section the same row links
 * the product into. The value stored is exactly what the CSV column says --
 * nothing is computed or inferred from category placement. A row such as
 * 'acb-1,gel,AGM' (chemistry column says AGM while the category column links
 * to the GEL section) is accepted as-is; this class does not detect or claim
 * to detect that kind of mismatch, and the provenance marker below must never
 * say otherwise.
 *
 * Chemistry key collision (resolved): StageProductValidator::technicalAttributes()
 * already owns the 'chemistry' slot on Product::$technical_attributes and fills
 * it from a CONFIRMED, name-derived spec value (see
 * tests/Feature/RbStagingConverterPipelineTest.php). This class deliberately
 * does NOT introduce a second, competing key (e.g. 'technology') for the same
 * physical property: two keys for one fact would both reach the storefront via
 * SiteResolver::productPayload()'s `attributes` => technical_attributes dump,
 * and a reader could not tell which one to trust. Instead this class writes
 * into the SAME 'chemistry' key and:
 *   - tags every value it sets with a `chemistry_provenance` sibling key
 *     (source only) so a reader can always tell this particular value came
 *     from this CSV column, not from a manufacturer spec sheet -- a CSV
 *     column can be mistyped or stale;
 *   - refuses to overwrite a 'chemistry' value that lacks that provenance
 *     marker (i.e. one set by the staging pipeline from a confirmed source):
 *     if the CSV disagrees (case-insensitively) the whole run is blocked with
 *     'chemistry_conflict_with_confirmed_attribute'; if it merely differs in
 *     case, the confirmed value is left untouched (case is not a fact) --
 *     either way a confirmed value is NEVER silently overwritten or merged;
 *   - freely corrects a value that carries this class's own provenance marker
 *     (a previous run of this same tool), since that is not a competing
 *     source, just a re-run with an updated CSV.
 *
 * Provenance survives beyond this writer (round-2 fix): a nested
 * `chemistry_provenance` object living inside Product::$technical_attributes
 * is worthless if every real reader of that column either strips it as "not a
 * string/scalar" or republishes over it. Two real consumers were found doing
 * exactly that and are fixed alongside this class:
 *   - SiteResolver::productPayload() no longer republishes internal
 *     `*_provenance` keys into the public `attributes` payload (they are
 *     audit metadata, not a storefront-facing fact, and leaking them broke
 *     the frontend's declared `Record<string, string>` contract);
 *   - StagedProductPublisher::publishToSite() no longer wipes a previously
 *     set 'chemistry' + 'chemistry_provenance' pair when an unrelated
 *     staging batch for the same product is republished without its own
 *     'chemistry' fact (see that class for detail).
 *
 * Site-boundary note: `products` is the canonical table shared by every site
 * (including a future RU site), NOT the site-scoped `site_products` table. An
 * apply run driven by one site's CSV therefore mutates data that other sites'
 * storefronts will also read. This is intentional (chemistry is a physical
 * property of the product, not a per-site fact) but must always be visible to
 * whoever reads the run, not just in this docblock -- see the
 * `writes_canonical_product_attributes` / `canonical_write_note` summary keys
 * below and the command's console output.
 *
 * Publication state (`is_published`) is never read or written by this class.
 */
class SiteProductCategoryAssigner
{
    /**
     * Provenance marker recorded on every chemistry value this class sets.
     * Honest about what it is: the value came from this CSV's chemistry
     * column for that row, supplied by whoever built the CSV. It is NOT a
     * claim that the value was checked against, or derived from, the
     * category the row links the product into.
     */
    private const CHEMISTRY_SOURCE = 'operator_supplied_csv_column';

    /** Allowed chemistry values (case-normalized). No other value is honest to accept. */
    private const CHEMISTRY_ENUM = ['AGM' => 'AGM', 'GEL' => 'GEL'];

    /** @var array<string, string> */
    private const HEADERS = [
        'productexternalid' => 'product_external_id',
        'товарexternalid' => 'product_external_id',
        'товарid' => 'product_external_id',
        '1сid' => 'product_external_id',
        'externalid' => 'product_external_id',
        'categoryexternalid' => 'category_external_id',
        'категорияid' => 'category_external_id',
        'разделid' => 'category_external_id',
        'technology' => 'chemistry',
        'технология' => 'chemistry',
        'chemistry' => 'chemistry',
        'химия' => 'chemistry',
    ];

    /** Canonical column names this class ever reads. Anything else in the CSV header row is rejected, not ignored. */
    private const KNOWN_HEADERS = ['product_external_id', 'category_external_id', 'chemistry'];

    /**
     * @return array<string, mixed>
     */
    public function assign(
        Site $site,
        string $file,
        string $delimiter,
        string $categorySource,
        bool $apply,
    ): array {
        [$rows, $readErrors] = $this->read($file, $delimiter);

        $summary = [
            'mode' => $apply ? 'apply' : 'dry_run',
            'site_id' => $site->id,
            'site_key' => $site->key,
            'category_source' => $categorySource,
            'csv_records' => count($rows),
            'accepted_records' => 0,
            'assignments_created' => 0,
            'assignments_unchanged' => 0,
            'assignment_creations' => [],
            'chemistry_attributes_set' => 0,
            'chemistry_attributes_unchanged' => 0,
            'chemistry_updates' => [],
            'is_published_changed' => 0,
            'writes_canonical_product_attributes' => true,
            'canonical_write_note' => "Chemistry values are written to the shared products table (Product::technical_attributes['chemistry']), not to a site-scoped table. A change made here from site '{$site->key}' CSV data can affect what every other site linking this product renders.",
            'validation_error_count' => 0,
            'validation_errors' => [],
        ];

        $validation = $this->validate($site, $categorySource, $rows, $readErrors);
        $summary['validation_error_count'] = count($validation['errors']);
        $summary['validation_errors'] = array_slice($validation['errors'], 0, 50);

        if ($validation['errors'] !== []) {
            return $summary;
        }

        $summary['accepted_records'] = count($rows);
        DB::beginTransaction();

        try {
            foreach ($validation['assignments'] as $assignment) {
                $existingPivot = SiteCategoryProduct::query()
                    ->where('site_category_id', $assignment['site_category_id'])
                    ->where('site_product_id', $assignment['site_product_id'])
                    ->exists();

                if ($existingPivot) {
                    $summary['assignments_unchanged']++;
                } else {
                    $pivot = SiteCategoryProduct::create([
                        'site_id' => $site->id,
                        'site_category_id' => $assignment['site_category_id'],
                        'site_product_id' => $assignment['site_product_id'],
                    ]);
                    $summary['assignments_created']++;
                    // D4: identifiers of the created link, not just a count --
                    // an erroneous run needs to be traceable back to specific
                    // rows without re-deriving them from the source CSV.
                    $summary['assignment_creations'][] = [
                        'site_category_product_id' => $pivot->id,
                        'site_category_id' => $assignment['site_category_id'],
                        'site_product_id' => $assignment['site_product_id'],
                        'product_external_id' => $assignment['product_external_id'],
                        'category_external_id' => $assignment['category_external_id'],
                    ];
                }
            }

            foreach ($validation['chemistry_updates'] as $update) {
                /** @var Product $product */
                $product = $update['product'];
                $attributesBefore = $product->technical_attributes ?? [];

                if (($attributesBefore['chemistry'] ?? null) === $update['chemistry']) {
                    $summary['chemistry_attributes_unchanged']++;

                    continue;
                }

                // Honest provenance: the value is exactly what the CSV's
                // chemistry column said for this row. No comparison against
                // the category this row links the product into is ever
                // performed, so no "confidence"/"derived" claim is made.
                $provenance = [
                    'source' => self::CHEMISTRY_SOURCE,
                ];

                $attributesAfter = [
                    ...$attributesBefore,
                    'chemistry' => $update['chemistry'],
                    'chemistry_provenance' => $provenance,
                ];

                $product->technical_attributes = $attributesAfter;
                $product->save();
                $summary['chemistry_attributes_set']++;
                $summary['chemistry_updates'][] = [
                    'product_external_id' => $product->external_id,
                    'before' => [
                        'chemistry' => $attributesBefore['chemistry'] ?? null,
                        'chemistry_provenance' => $attributesBefore['chemistry_provenance'] ?? null,
                    ],
                    'after' => [
                        'chemistry' => $update['chemistry'],
                        'chemistry_provenance' => $provenance,
                    ],
                ];
            }

            if ($apply) {
                DB::commit();
            } else {
                DB::rollBack();
            }
        } catch (Throwable $error) {
            if (DB::transactionLevel() > 0) {
                DB::rollBack();
            }

            throw $error;
        }

        return $summary;
    }

    /**
     * @param  list<array<string, mixed>>  $rows
     * @param  list<array<string, mixed>>  $readErrors
     * @return array{errors: list<array<string, mixed>>, assignments: list<array{site_category_id: int, site_product_id: int, product_external_id: string, category_external_id: string}>, chemistry_updates: list<array{product: Product, chemistry: string}>}
     */
    private function validate(Site $site, string $categorySource, array $rows, array $readErrors): array
    {
        $errors = $readErrors;
        $seenPairs = [];
        $chemistryByProduct = [];
        $chemistryFirstRowByProduct = [];

        foreach ($rows as $row) {
            $pairKey = $row['product_external_id'].'|'.$row['category_external_id'];

            if (isset($seenPairs[$pairKey])) {
                $errors[] = $this->error($row['row_number'], 'duplicate_assignment_row', [
                    'product_external_id' => $row['product_external_id'],
                    'category_external_id' => $row['category_external_id'],
                ]);
            } else {
                $seenPairs[$pairKey] = true;
            }

            if ($row['chemistry'] !== null) {
                $productId = $row['product_external_id'];
                if (isset($chemistryByProduct[$productId]) && $chemistryByProduct[$productId] !== $row['chemistry']) {
                    $errors[] = $this->error($row['row_number'], 'chemistry_conflict_in_csv', [
                        'product_external_id' => $productId,
                        'first_value' => $chemistryByProduct[$productId],
                        'conflicting_value' => $row['chemistry'],
                    ]);
                } else {
                    $chemistryByProduct[$productId] = $row['chemistry'];
                    $chemistryFirstRowByProduct[$productId] ??= $row['row_number'];
                }
            }
        }

        $productExternalIds = array_values(array_unique(array_column($rows, 'product_external_id')));
        $products = Product::query()
            ->whereIn('external_id', $productExternalIds)
            ->get()
            ->keyBy('external_id');

        $siteProducts = SiteProduct::query()
            ->where('site_id', $site->id)
            ->whereIn('product_id', $products->pluck('id')->all())
            ->get()
            ->keyBy('product_id');

        $categoryExternalIds = array_values(array_unique(array_column($rows, 'category_external_id')));
        $siteCategories = SiteCategory::query()
            ->where('site_id', $site->id)
            ->where('source', $categorySource)
            ->whereIn('external_id', $categoryExternalIds)
            ->get()
            ->keyBy('external_id');

        $assignments = [];
        $seenAssignments = [];

        foreach ($rows as $row) {
            $product = $products->get($row['product_external_id']);
            if ($product === null) {
                $errors[] = $this->error($row['row_number'], 'unknown_product', [
                    'product_external_id' => $row['product_external_id'],
                ]);

                continue;
            }

            $siteProduct = $siteProducts->get($product->id);
            if ($siteProduct === null) {
                $errors[] = $this->error($row['row_number'], 'product_not_linked_to_site', [
                    'product_external_id' => $row['product_external_id'],
                    'site_key' => $site->key,
                ]);

                continue;
            }

            $siteCategory = $siteCategories->get($row['category_external_id']);
            if ($siteCategory === null) {
                $errors[] = $this->error($row['row_number'], 'unknown_category', [
                    'category_external_id' => $row['category_external_id'],
                    'site_key' => $site->key,
                    'category_source' => $categorySource,
                ]);

                continue;
            }

            $assignmentKey = $siteCategory->id.'|'.$siteProduct->id;
            if (isset($seenAssignments[$assignmentKey])) {
                continue;
            }
            $seenAssignments[$assignmentKey] = true;

            $assignments[] = [
                'site_category_id' => $siteCategory->id,
                'site_product_id' => $siteProduct->id,
                'product_external_id' => $row['product_external_id'],
                'category_external_id' => $row['category_external_id'],
            ];
        }

        $chemistryUpdates = [];
        foreach ($chemistryByProduct as $productExternalId => $chemistry) {
            $product = $products->get($productExternalId);
            if ($product === null) {
                continue;
            }

            $existingAttributes = $product->technical_attributes ?? [];
            $existingChemistry = $existingAttributes['chemistry'] ?? null;
            // D5: a blank value is absence of a confirmed value, not a
            // confirmed value of "". Without this, an existing 'chemistry' =>
            // '' (or a whitespace-only placeholder) would be treated as a
            // genuine confirmed fact and would falsely conflict with (and
            // block) every CSV value. An incoming blank CSV cell is already
            // treated as absent, so the two sides now agree.
            if (is_string($existingChemistry) && trim($existingChemistry) === '') {
                $existingChemistry = null;
            }
            $existingChemistryNormalized = is_string($existingChemistry) ? mb_strtoupper(trim($existingChemistry)) : null;
            $existingSource = $existingAttributes['chemistry_provenance']['source'] ?? null;
            $existingIsOurs = $existingSource === self::CHEMISTRY_SOURCE;

            if ($existingChemistry !== null && ! $existingIsOurs) {
                // A confirmed value (not one this class previously wrote)
                // already occupies this slot. Compare case-insensitively --
                // the staging pipeline that wrote it does not guarantee this
                // class's casing convention -- but never touch it either way:
                // a genuine mismatch blocks the whole run, and a case-only
                // match is left exactly as it was rather than being re-saved
                // and re-tagged with this class's provenance marker.
                if ($existingChemistryNormalized !== $chemistry) {
                    $errors[] = $this->error($chemistryFirstRowByProduct[$productExternalId] ?? null, 'chemistry_conflict_with_confirmed_attribute', [
                        'product_external_id' => $productExternalId,
                        'existing_value' => $existingChemistry,
                        'csv_value' => $chemistry,
                    ]);
                }

                continue;
            }

            $chemistryUpdates[] = ['product' => $product, 'chemistry' => $chemistry];
        }

        return [
            'errors' => $errors,
            'assignments' => $errors === [] ? $assignments : [],
            'chemistry_updates' => $errors === [] ? $chemistryUpdates : [],
        ];
    }

    /**
     * @return array{list<array<string, mixed>>, list<array<string, mixed>>}
     */
    private function read(string $file, string $delimiter): array
    {
        $handle = fopen($file, 'rb');
        if ($handle === false) {
            throw new RuntimeException("Unable to open {$file}.");
        }

        try {
            $rawHeaders = fgetcsv($handle, 0, $delimiter, '"', '');
            if ($rawHeaders === false) {
                throw new RuntimeException('CSV file does not contain a header row.');
            }

            $headers = array_map(fn (mixed $header): string => $this->normalizeHeader((string) $header), $rawHeaders);
            foreach (['product_external_id', 'category_external_id'] as $required) {
                if (! in_array($required, $headers, true)) {
                    throw new RuntimeException("Required column is missing: {$required}.");
                }
            }
            if (count($headers) !== count(array_unique($headers))) {
                throw new RuntimeException('CSV contains duplicate normalized headers.');
            }
            // An unrecognized column header must block the run, not be
            // silently ignored: a misspelled or unexpected header (e.g.
            // 'tech', 'Тип') would otherwise pass validation while its data
            // is never read anywhere.
            foreach ($headers as $index => $header) {
                if (! in_array($header, self::KNOWN_HEADERS, true)) {
                    throw new RuntimeException("Unrecognized column header: \"{$rawHeaders[$index]}\".");
                }
            }

            $rows = [];
            $errors = [];
            $rowNumber = 1;
            while (($raw = fgetcsv($handle, 0, $delimiter, '"', '')) !== false) {
                $rowNumber++;
                if ($raw === [null] || $raw === []) {
                    continue;
                }
                if (count($raw) !== count($headers)) {
                    $errors[] = $this->error($rowNumber, 'column_count_mismatch', [
                        'expected' => count($headers),
                        'actual' => count($raw),
                    ]);

                    continue;
                }

                $payload = array_combine($headers, $raw);
                $productExternalId = $this->clean($payload['product_external_id'] ?? null);
                $categoryExternalId = $this->clean($payload['category_external_id'] ?? null);
                // Deliberately NOT $this->clean(): clean() collapses both "absent"
                // and "present but >255 chars" to null, which would let an
                // oversized garbage value silently masquerade as "no technology
                // column supplied" and pass the run as clean. trimmedScalar()
                // preserves the distinction so the length check below can catch it.
                $chemistryRaw = isset($payload['chemistry']) ? $this->trimmedScalar($payload['chemistry']) : null;

                $invalid = array_keys(array_filter([
                    'product_external_id' => $productExternalId === null,
                    'category_external_id' => $categoryExternalId === null,
                ]));

                if ($invalid !== []) {
                    $errors[] = $this->error($rowNumber, 'invalid_required_fields', ['fields' => $invalid]);

                    continue;
                }

                $chemistry = null;
                if ($chemistryRaw !== null) {
                    if (mb_strlen($chemistryRaw) > 255) {
                        $errors[] = $this->error($rowNumber, 'invalid_chemistry_value', [
                            'value' => mb_substr($chemistryRaw, 0, 255).'…',
                            'reason_detail' => 'value_too_long',
                            'allowed' => array_values(self::CHEMISTRY_ENUM),
                        ]);

                        continue;
                    }

                    $chemistry = self::CHEMISTRY_ENUM[mb_strtoupper($chemistryRaw)] ?? null;
                    if ($chemistry === null) {
                        $errors[] = $this->error($rowNumber, 'invalid_chemistry_value', [
                            'value' => $chemistryRaw,
                            'allowed' => array_values(self::CHEMISTRY_ENUM),
                        ]);

                        continue;
                    }
                }

                $rows[] = [
                    'row_number' => $rowNumber,
                    'product_external_id' => $productExternalId,
                    'category_external_id' => $categoryExternalId,
                    'chemistry' => $chemistry,
                ];
            }

            return [$rows, $errors];
        } finally {
            fclose($handle);
        }
    }

    private function normalizeHeader(string $header): string
    {
        $normalized = mb_strtolower(ltrim(trim($header), "\xEF\xBB\xBF"));
        $normalized = preg_replace('/[^\p{L}\p{N}]+/u', '', $normalized) ?? '';

        return self::HEADERS[$normalized] ?? $normalized;
    }

    private function clean(mixed $value): ?string
    {
        if (! is_scalar($value)) {
            return null;
        }
        $clean = trim((string) $value);

        return $clean !== '' && mb_strlen($clean) <= 255 ? $clean : null;
    }

    /**
     * Like clean(), but never collapses an over-long value to null: it only
     * reports "no value present" for genuine absence (non-scalar or blank
     * after trim). Callers that must distinguish "column empty" from "column
     * has garbage" -- e.g. the chemistry column's length check -- need this
     * instead of clean().
     */
    private function trimmedScalar(mixed $value): ?string
    {
        if (! is_scalar($value)) {
            return null;
        }
        $clean = trim((string) $value);

        return $clean !== '' ? $clean : null;
    }

    /** @param  array<string, mixed>  $context */
    private function error(?int $rowNumber, string $reason, array $context = []): array
    {
        return ['row_number' => $rowNumber, 'reason' => $reason, ...$context];
    }
}
