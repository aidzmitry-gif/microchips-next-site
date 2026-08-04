<?php

namespace App\Console\Commands;

use App\Models\ImportRun;
use App\Models\StagedImportRecord;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use JsonException;
use RuntimeException;
use Throwable;

class StageBitrixDuplicateReviewEvidence extends Command
{
    protected $signature = 'catalog:stage-bitrix-duplicate-review-evidence
                            {file : Complete duplicate-review evidence JSON}
                            {--apply : Persist evidence only; default is dry-run}';

    protected $description = 'Stage complete Bitrix/1C collision decisions without changing catalog entities';

    /** @var list<string> */
    private const GROUP_DECISIONS = [
        'mixed_mapping_collision_hold',
        'single_high_signal_review_queue',
        'variant_or_collision_hold',
    ];

    /** @var list<string> */
    private const MEMBER_DECISIONS = [
        'hold_insufficient_identity_evidence',
        'hold_multiple_high_signal_candidates',
        'review_exact_identity_candidate',
    ];

    /** @var list<string> */
    private const FORBIDDEN_MUTATIONS = [
        'create_products', 'merge_products', 'delete_products', 'change_site_links',
        'create_families', 'change_publication', 'change_urls', 'change_seo',
        'render_legacy_html',
    ];

    public function handle(): int
    {
        $file = (string) $this->argument('file');
        if (! is_file($file) || ! is_readable($file)) {
            $this->error('Evidence manifest is missing or unreadable.');

            return self::FAILURE;
        }

        try {
            $raw = file_get_contents($file);
            if ($raw === false) {
                throw new RuntimeException('Unable to read evidence manifest.');
            }
            $manifest = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
            $validated = $this->validateManifest($manifest);
        } catch (JsonException|RuntimeException $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $hash = hash('sha256', $raw);
        $source = 'bitrix_duplicate_review_evidence:'.$manifest['site_key'];
        $existing = ImportRun::query()->where('source', $source)->latest('id')->first();
        $unchanged = $existing !== null
            && ($existing->summary['manifest_sha256'] ?? null) === $hash
            && $existing->total_records === count($validated['members']);
        $summary = [
            'mode' => $this->option('apply') ? 'apply' : 'dry_run',
            'site' => $manifest['site_key'],
            'source_import_run_id' => $manifest['source_import_run_id'],
            'groups' => count($validated['groups']),
            'members' => count($validated['members']),
            'group_decision_counts' => $validated['group_decision_counts'],
            'member_decision_counts' => $validated['member_decision_counts'],
            'manifest_sha256' => $hash,
            'catalog_mutations' => 0,
            'unchanged' => $unchanged,
        ];

        if (! $this->option('apply') || $unchanged) {
            $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

            return self::SUCCESS;
        }

        try {
            DB::transaction(function () use ($file, $hash, $manifest, $source, $summary, $validated): void {
                $run = ImportRun::query()->create([
                    'source' => $source,
                    'status' => 'completed',
                    'source_file' => basename($file),
                    'total_records' => count($validated['members']),
                    'processed_records' => count($validated['members']),
                    'failed_records' => 0,
                    'summary' => [...$summary, 'mode' => 'apply', 'manifest_sha256' => $hash],
                    'started_at' => now(),
                    'finished_at' => now(),
                ]);

                foreach (array_chunk($validated['members'], 100) as $chunkOffset => $chunk) {
                    $rows = [];
                    foreach ($chunk as $offset => $member) {
                        $rows[] = [
                            'import_run_id' => $run->id,
                            'row_number' => ($chunkOffset * 100) + $offset + 1,
                            'entity_type' => 'bitrix_duplicate_review_decision',
                            'external_id' => 'bitrix:'.$member['legacy_element_id'],
                            'payload' => json_encode($member, JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE),
                            'normalized_payload' => json_encode([
                                'source_import_run_id' => $manifest['source_import_run_id'],
                                'one_c_external_id' => $member['one_c_external_id'],
                                'group_decision' => $member['group_decision'],
                                'member_decision' => $member['member_decision'],
                            ], JSON_THROW_ON_ERROR | JSON_UNESCAPED_UNICODE),
                            'validation_errors' => json_encode([], JSON_THROW_ON_ERROR),
                            'status' => 'staged_evidence',
                            'error' => null,
                            'review_note' => 'Collision classification only. Product merge, family creation and publication are forbidden.',
                            'created_at' => now(),
                            'updated_at' => now(),
                        ];
                    }
                    StagedImportRecord::query()->insert($rows);
                }
            });
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->line(json_encode($summary, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE));

        return self::SUCCESS;
    }

    /**
     * @return array{groups:list<array<string,mixed>>,members:list<array<string,mixed>>,group_decision_counts:array<string,int>,member_decision_counts:array<string,int>}
     */
    private function validateManifest(mixed $manifest): array
    {
        if (! is_array($manifest) || ($manifest['schema_version'] ?? null) !== 1) {
            throw new RuntimeException('Evidence manifest must use schema_version 1.');
        }
        foreach (['site_key', 'source_import_run_id', 'source_manifest_sha256', 'matcher_evidence_sha256', 'expected_groups', 'expected_members', 'mutation_policy', 'groups'] as $field) {
            if (! array_key_exists($field, $manifest)) {
                throw new RuntimeException("Evidence manifest misses {$field}.");
            }
        }
        if ($manifest['site_key'] !== 'microchips-by' || ! is_int($manifest['source_import_run_id'])) {
            throw new RuntimeException('Site key or source import run ID is invalid.');
        }
        foreach (['source_manifest_sha256', 'matcher_evidence_sha256'] as $hashField) {
            if (! preg_match('/^[a-f0-9]{64}$/', (string) $manifest[$hashField])) {
                throw new RuntimeException("{$hashField} must be SHA-256.");
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
        if (! is_array($manifest['groups']) || count($manifest['groups']) !== $manifest['expected_groups']) {
            throw new RuntimeException('Group count does not match expected_groups.');
        }

        $sourceRun = ImportRun::query()->find($manifest['source_import_run_id']);
        if ($sourceRun === null
            || $sourceRun->source !== 'bitrix_legacy_snapshot:microchips-by'
            || ($sourceRun->summary['manifest_sha256'] ?? null) !== $manifest['source_manifest_sha256']) {
            throw new RuntimeException('Source snapshot run or manifest hash does not match.');
        }
        $sourceRows = StagedImportRecord::query()
            ->where('import_run_id', $sourceRun->id)
            ->where('entity_type', 'bitrix_legacy_product_evidence')
            ->get()
            ->filter(fn (StagedImportRecord $row): bool => ($row->payload['transfer_status'] ?? null) === 'candidate_duplicate_group');
        $sourceByLegacy = $sourceRows->keyBy(fn (StagedImportRecord $row): string => (string) ($row->payload['legacy_element_id'] ?? ''));

        $groups = [];
        $members = [];
        $seenGroups = [];
        $seenMembers = [];
        $groupDecisionCounts = [];
        $memberDecisionCounts = [];
        foreach ($manifest['groups'] as $group) {
            if (! is_array($group)) {
                throw new RuntimeException('Group is not an object.');
            }
            $groupKey = trim((string) ($group['group_key'] ?? ''));
            $oneC = trim((string) ($group['one_c_external_id'] ?? ''));
            $groupDecision = trim((string) ($group['group_decision'] ?? ''));
            $groupMembers = $group['members'] ?? null;
            if ($groupKey !== 'one_c:'.$oneC || $oneC === '' || isset($seenGroups[$groupKey])) {
                throw new RuntimeException('Invalid or duplicate group key.');
            }
            if (! in_array($groupDecision, self::GROUP_DECISIONS, true) || ! is_array($groupMembers)) {
                throw new RuntimeException("Group {$groupKey} has an invalid decision or members list.");
            }
            if (count($groupMembers) !== ($group['expected_member_count'] ?? null)) {
                throw new RuntimeException("Group {$groupKey} member count drifted.");
            }
            $highSignal = 0;
            foreach ($groupMembers as $member) {
                if (! is_array($member)) {
                    throw new RuntimeException("Group {$groupKey} contains a non-object member.");
                }
                $legacyId = trim((string) ($member['legacy_element_id'] ?? ''));
                $memberDecision = trim((string) ($member['member_decision'] ?? ''));
                if ($legacyId === '' || isset($seenMembers[$legacyId]) || ! in_array($memberDecision, self::MEMBER_DECISIONS, true)) {
                    throw new RuntimeException("Group {$groupKey} has an invalid or duplicate member.");
                }
                if (($member['create_product'] ?? null) !== false
                    || ($member['merge_product'] ?? null) !== false
                    || ($member['change_publication'] ?? null) !== false) {
                    throw new RuntimeException("Member {$legacyId} permits a forbidden mutation.");
                }
                $sourceRow = $sourceByLegacy->get($legacyId);
                $sourcePayload = $sourceRow?->payload;
                if ($sourceRow === null
                    || ($sourcePayload['one_c_external_id'] ?? null) !== $oneC
                    || ($sourcePayload['legacy_text_sha256'] ?? null) !== ($member['legacy_text_sha256'] ?? null)) {
                    throw new RuntimeException("Member {$legacyId} drifted from source snapshot.");
                }
                if ($memberDecision !== 'hold_insufficient_identity_evidence') {
                    $highSignal++;
                }
                $seenMembers[$legacyId] = true;
                $memberDecisionCounts[$memberDecision] = ($memberDecisionCounts[$memberDecision] ?? 0) + 1;
                $members[] = [
                    ...$member,
                    'group_key' => $groupKey,
                    'one_c_external_id' => $oneC,
                    'group_decision' => $groupDecision,
                ];
            }
            $expectedGroupDecision = $highSignal === 0
                ? 'mixed_mapping_collision_hold'
                : ($highSignal === 1 ? 'single_high_signal_review_queue' : 'variant_or_collision_hold');
            if ($highSignal !== ($group['high_signal_member_count'] ?? null) || $groupDecision !== $expectedGroupDecision) {
                throw new RuntimeException("Group {$groupKey} high-signal decision is inconsistent.");
            }
            $seenGroups[$groupKey] = true;
            $groupDecisionCounts[$groupDecision] = ($groupDecisionCounts[$groupDecision] ?? 0) + 1;
            $groups[] = $group;
        }
        if (count($members) !== $manifest['expected_members'] || count($members) !== $sourceRows->count()) {
            throw new RuntimeException('Evidence manifest does not exactly cover source collision members.');
        }
        ksort($groupDecisionCounts);
        ksort($memberDecisionCounts);
        if (($manifest['group_decision_counts'] ?? null) !== $groupDecisionCounts
            || ($manifest['member_decision_counts'] ?? null) !== $memberDecisionCounts) {
            throw new RuntimeException('Decision summary counts do not match members.');
        }

        return [
            'groups' => $groups,
            'members' => $members,
            'group_decision_counts' => $groupDecisionCounts,
            'member_decision_counts' => $memberDecisionCounts,
        ];
    }
}
