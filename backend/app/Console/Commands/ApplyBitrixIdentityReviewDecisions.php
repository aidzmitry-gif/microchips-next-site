<?php

namespace App\Console\Commands;

use App\Domain\Imports\ProductIdentity;
use App\Domain\Imports\ProductIdentityGuard;
use App\Models\CatalogIdentityCandidate;
use App\Models\ImportRun;
use App\Models\OneCNomenclatureItem;
use App\Models\Product;
use App\Models\Site;
use App\Models\SiteProduct;
use App\Models\StagedImportRecord;
use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class ApplyBitrixIdentityReviewDecisions extends Command
{
    protected $signature = 'catalog:apply-bitrix-identity-review-decisions
                            {file : Reviewed identity decisions JSON}
                            {--reviewer-email= : Existing administrator e-mail}
                            {--apply : Persist reviewed evidence; default is dry-run}';

    protected $description = 'Record reviewed Bitrix/1C identity links without merging or publishing products';

    private const DECISIONS = ['same_identity', 'hold', 'different_product_false_mapping'];

    private const FORBIDDEN_MUTATIONS = [
        'change_products', 'change_site_links', 'merge_products', 'delete_products',
        'change_publication', 'change_urls', 'change_seo', 'change_media',
    ];

    public function handle(ProductIdentityGuard $identityGuard): int
    {
        try {
            [$manifest, $raw] = $this->readManifest((string) $this->argument('file'));
            $reviewer = $this->reviewer((string) $this->option('reviewer-email'));
            $validated = $this->validateManifest($manifest, $identityGuard);
            $hash = hash('sha256', $raw);
            $source = 'bitrix_identity_review_decisions:'.$manifest['site_key'];
            $existingRun = ImportRun::query()->where('source', $source)->latest('id')->first();
            $sameCount = $validated['decision_counts']['same_identity'] ?? 0;
            $unchanged = $existingRun !== null
                && ($existingRun->summary['manifest_sha256'] ?? null) === $hash
                && StagedImportRecord::query()->where('import_run_id', $existingRun->id)->count() === count($validated['decisions'])
                && CatalogIdentityCandidate::query()
                    ->where('review_batch', $manifest['review_batch'])
                    ->where('review_status', 'same_identity_confirmed')
                    ->count() === $sameCount;
            $summary = [
                'mode' => $this->option('apply') ? 'apply' : 'dry_run',
                'site' => $manifest['site_key'],
                'source_snapshot_run_id' => $manifest['source_snapshot_run_id'],
                'source_duplicate_evidence_run_id' => $manifest['source_duplicate_evidence_run_id'],
                'decisions' => count($validated['decisions']),
                'decision_counts' => $validated['decision_counts'],
                'manifest_sha256' => $hash,
                'catalog_entity_mutations' => 0,
                'unchanged' => $unchanged,
            ];

            if (! $this->option('apply') || $unchanged) {
                $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

                return self::SUCCESS;
            }

            DB::transaction(function () use ($manifest, $reviewer, $source, $summary, $validated): void {
                $run = ImportRun::query()->create([
                    'source' => $source,
                    'status' => 'completed',
                    'source_file' => basename((string) $this->argument('file')),
                    'total_records' => count($validated['decisions']),
                    'processed_records' => count($validated['decisions']),
                    'failed_records' => 0,
                    'summary' => [...$summary, 'mode' => 'apply', 'unchanged' => false],
                    'started_at' => now(),
                    'finished_at' => now(),
                ]);

                foreach ($validated['decisions'] as $index => $entry) {
                    $decision = $entry['decision'];
                    $checksum = hash('sha256', json_encode($decision, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
                    StagedImportRecord::query()->create([
                        'import_run_id' => $run->id,
                        'row_number' => $index + 1,
                        'entity_type' => 'bitrix_identity_review_decision',
                        'external_id' => 'bitrix:'.$decision['legacy_element_id'],
                        'payload' => $decision,
                        'normalized_payload' => [
                            'one_c_external_id' => $decision['one_c_external_id'],
                            'decision' => $decision['decision'],
                            'decision_checksum' => $checksum,
                        ],
                        'validation_errors' => [],
                        'status' => 'reviewed_evidence',
                        'review_note' => 'Reviewed identity evidence only; no product merge, publication or URL mutation.',
                        'reviewed_by' => $reviewer->id,
                        'reviewed_at' => now(),
                    ]);

                    if ($decision['decision'] !== 'same_identity') {
                        continue;
                    }

                    if ($entry['existing_candidate'] !== null) {
                        continue;
                    }

                    CatalogIdentityCandidate::query()->create([
                        'import_run_id' => $run->id,
                        'one_c_nomenclature_item_id' => $entry['one_c_item']->id,
                        'legacy_source' => 'bitrix',
                        'legacy_id' => $decision['legacy_element_id'],
                        'legacy_name' => $entry['source_snapshot']->payload['legacy_name'],
                        'legacy_url' => $entry['source_snapshot']->payload['legacy_url_candidate'] ?? null,
                        'review_priority' => $decision['review_priority'],
                        'review_batch' => $manifest['review_batch'],
                        'confidence' => 1,
                        'match_method' => 'official_source_exact_identity',
                        'signature' => ProductIdentity::normalize($decision['manufacturer'].' '.$decision['confirmed_mpn']),
                        'comparison_status' => 'same_identity',
                        'review_status' => 'same_identity_confirmed',
                        'confirmed_mpn' => $decision['confirmed_mpn'],
                        'confirmed_mpn_normalized' => ProductIdentity::normalize($decision['confirmed_mpn']),
                        'confirmed_manufacturer' => $decision['manufacturer'],
                        'review_note' => sprintf('Official evidence: %s (%s; checked %s).', $decision['source_url'], $decision['source_kind'], $decision['checked_at']),
                        'reviewed_by' => $reviewer->id,
                        'reviewed_at' => now(),
                        'source_payload' => $decision,
                        'source_checksum' => $checksum,
                    ]);
                }
            });

            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

            return self::SUCCESS;
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }
    }

    /** @return array{array<string,mixed>,string} */
    private function readManifest(string $file): array
    {
        if (! is_file($file) || ! is_readable($file)) {
            throw new RuntimeException('Identity decisions manifest is missing or unreadable.');
        }
        $raw = file_get_contents($file);
        if ($raw === false) {
            throw new RuntimeException('Unable to read identity decisions manifest.');
        }
        $manifest = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($manifest)) {
            throw new RuntimeException('Identity decisions manifest must be an object.');
        }

        return [$manifest, $raw];
    }

    /** @return array{decisions:list<array{decision:array<string,mixed>,one_c_item:OneCNomenclatureItem,source_snapshot:StagedImportRecord,existing_candidate:?CatalogIdentityCandidate}>,decision_counts:array<string,int>} */
    private function validateManifest(array $manifest, ProductIdentityGuard $identityGuard): array
    {
        foreach (['schema_version', 'site_key', 'review_batch', 'source_snapshot_run_id', 'source_snapshot_manifest_sha256', 'source_duplicate_evidence_run_id', 'source_duplicate_manifest_sha256', 'expected_count', 'mutation_policy', 'decisions'] as $field) {
            if (! array_key_exists($field, $manifest)) {
                throw new RuntimeException("Identity decisions manifest misses {$field}.");
            }
        }
        if ($manifest['schema_version'] !== 1 || $manifest['site_key'] !== 'microchips-by' || ! is_string($manifest['review_batch'])) {
            throw new RuntimeException('Manifest schema, site key or review batch is invalid.');
        }
        foreach (['source_snapshot_manifest_sha256', 'source_duplicate_manifest_sha256'] as $field) {
            if (! preg_match('/^[a-f0-9]{64}$/', (string) $manifest[$field])) {
                throw new RuntimeException("{$field} must be SHA-256.");
            }
        }
        if (! is_array($manifest['mutation_policy'])) {
            throw new RuntimeException('mutation_policy must be an object.');
        }
        foreach (self::FORBIDDEN_MUTATIONS as $mutation) {
            if (($manifest['mutation_policy'][$mutation] ?? null) !== false) {
                throw new RuntimeException("Mutation {$mutation} must be false.");
            }
        }
        if (! is_array($manifest['decisions']) || count($manifest['decisions']) !== $manifest['expected_count'] || count($manifest['decisions']) < 1 || count($manifest['decisions']) > 22) {
            throw new RuntimeException('Decision count is outside the bounded 1..22 queue.');
        }

        $snapshotRun = $this->sourceRun((int) $manifest['source_snapshot_run_id'], 'bitrix_legacy_snapshot:microchips-by', (string) $manifest['source_snapshot_manifest_sha256']);
        $duplicateRun = $this->sourceRun((int) $manifest['source_duplicate_evidence_run_id'], 'bitrix_duplicate_review_evidence:microchips-by', (string) $manifest['source_duplicate_manifest_sha256']);
        $snapshots = StagedImportRecord::query()->where('import_run_id', $snapshotRun->id)->where('entity_type', 'bitrix_legacy_product_evidence')->get()->keyBy('external_id');
        $duplicateEvidence = StagedImportRecord::query()->where('import_run_id', $duplicateRun->id)->where('entity_type', 'bitrix_duplicate_review_decision')->get()->keyBy('external_id');
        $site = Site::query()->where('key', $manifest['site_key'])->sole();

        $seenLegacy = [];
        $seenOneC = [];
        $counts = [];
        $validated = [];
        foreach ($manifest['decisions'] as $decision) {
            if (! is_array($decision)) {
                throw new RuntimeException('Decision is not an object.');
            }
            foreach (['review_priority', 'legacy_element_id', 'one_c_external_id', 'legacy_text_sha256', 'decision', 'identity_scope', 'reason', 'checked_at'] as $field) {
                if (! isset($decision[$field]) || trim((string) $decision[$field]) === '') {
                    throw new RuntimeException("Identity decision misses {$field}.");
                }
            }
            $legacyId = trim((string) $decision['legacy_element_id']);
            $oneCExternalId = trim((string) $decision['one_c_external_id']);
            $verdict = trim((string) $decision['decision']);
            if (isset($seenLegacy[$legacyId]) || isset($seenOneC[$oneCExternalId]) || ! in_array($verdict, self::DECISIONS, true)) {
                throw new RuntimeException('Decision repeats an identity or uses an unsupported verdict.');
            }
            if (! preg_match('/^[a-f0-9]{64}$/', (string) $decision['legacy_text_sha256'])) {
                throw new RuntimeException("Legacy text hash for {$legacyId} is invalid.");
            }
            $snapshot = $snapshots->get('bitrix:'.$legacyId);
            $duplicate = $duplicateEvidence->get('bitrix:'.$legacyId);
            if ($snapshot === null || $duplicate === null
                || ($snapshot->payload['one_c_external_id'] ?? null) !== $oneCExternalId
                || ($snapshot->payload['legacy_text_sha256'] ?? null) !== $decision['legacy_text_sha256']
                || ($duplicate->payload['one_c_external_id'] ?? null) !== $oneCExternalId
                || ($duplicate->payload['group_decision'] ?? null) !== 'single_high_signal_review_queue'
                || ($duplicate->payload['member_decision'] ?? null) !== 'review_exact_identity_candidate') {
                throw new RuntimeException("Decision {$legacyId} drifted from reviewed source evidence.");
            }
            $oneCItem = OneCNomenclatureItem::query()->where('source_key', '1c_nomenclature')->where('external_id', $oneCExternalId)->where('is_group', false)->sole();

            $existingCandidate = null;
            if ($verdict === 'same_identity') {
                foreach (['confirmed_mpn', 'manufacturer', 'source_url', 'source_kind'] as $field) {
                    if (! isset($decision[$field]) || trim((string) $decision[$field]) === '') {
                        throw new RuntimeException("Same-identity decision {$legacyId} misses {$field}.");
                    }
                }
                if ($decision['identity_scope'] !== 'exact' || ! filter_var($decision['source_url'], FILTER_VALIDATE_URL) || ! str_starts_with($decision['source_url'], 'https://')) {
                    throw new RuntimeException("Same-identity decision {$legacyId} lacks exact HTTPS primary evidence.");
                }
                $target = Product::query()->where('external_id_normalized', ProductIdentity::normalize($oneCExternalId))->sole();
                SiteProduct::query()->where('site_id', $site->id)->where('product_id', $target->id)->sole();
                $identityGuard->assertCanPersist([
                    'external_id' => $oneCExternalId,
                    'mpn' => $decision['confirmed_mpn'],
                    'manufacturer' => $decision['manufacturer'],
                ], $target);
                $decisionChecksum = hash('sha256', json_encode($decision, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
                $existingByLegacy = CatalogIdentityCandidate::query()->where('legacy_source', 'bitrix')->where('legacy_id', $legacyId)->first();
                $existingByOneC = CatalogIdentityCandidate::query()->where('one_c_nomenclature_item_id', $oneCItem->id)->first();
                if ($existingByLegacy !== null || $existingByOneC !== null) {
                    if ($existingByLegacy === null || $existingByOneC === null || $existingByLegacy->id !== $existingByOneC->id
                        || $existingByLegacy->review_status !== 'same_identity_confirmed'
                        || $existingByLegacy->review_batch !== $manifest['review_batch']
                        || $existingByLegacy->source_checksum !== $decisionChecksum) {
                        throw new RuntimeException("Identity candidate {$legacyId} already exists and will not be overwritten.");
                    }
                    $existingCandidate = $existingByLegacy;
                }
            }

            $seenLegacy[$legacyId] = true;
            $seenOneC[$oneCExternalId] = true;
            $counts[$verdict] = ($counts[$verdict] ?? 0) + 1;
            $validated[] = [
                'decision' => $decision,
                'one_c_item' => $oneCItem,
                'source_snapshot' => $snapshot,
                'existing_candidate' => $existingCandidate,
            ];
        }
        ksort($counts);
        if (($manifest['decision_counts'] ?? null) !== $counts) {
            throw new RuntimeException('Decision summary counts do not match reviewed rows.');
        }

        return ['decisions' => $validated, 'decision_counts' => $counts];
    }

    private function sourceRun(int $id, string $source, string $hash): ImportRun
    {
        $run = ImportRun::query()->find($id);
        if ($run === null || $run->source !== $source || ($run->summary['manifest_sha256'] ?? null) !== $hash) {
            throw new RuntimeException("Source evidence run {$id} or its manifest hash does not match.");
        }

        return $run;
    }

    private function reviewer(string $email): User
    {
        $query = User::query()->where('is_admin', true);
        if ($email !== '') {
            $query->where('email', $email);
        }

        return $query->sole();
    }
}
