<?php

namespace App\Console\Commands;

use App\Domain\Imports\IdentityCandidateReviewer;
use App\Models\CatalogIdentityCandidate;
use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class ApplyIdentityReviewEvidence extends Command
{
    protected $signature = 'catalog:apply-identity-review-evidence
                            {file : JSON evidence decisions file}
                            {--reviewer-email= : Existing administrator e-mail}
                            {--apply : Persist decisions; default is dry-run}';

    protected $description = 'Apply explicit evidence-backed MPN decisions through the normal duplicate guard';

    public function handle(IdentityCandidateReviewer $reviewer): int
    {
        try {
            $decisions = $this->decisions((string) $this->argument('file'));
            $reviewerUser = $this->reviewer((string) $this->option('reviewer-email'));
            $this->validate($decisions);

            if (! $this->option('apply')) {
                $this->info(sprintf('Dry-run passed: %d evidence decision(s) can be reviewed. No database records changed.', count($decisions)));

                return self::SUCCESS;
            }

            DB::transaction(function () use ($decisions, $reviewer, $reviewerUser): void {
                foreach ($decisions as $decision) {
                    $candidate = CatalogIdentityCandidate::query()->lockForUpdate()->findOrFail($decision['candidate_id']);
                    $this->assertMatchesEvidence($candidate, $decision);
                    $reviewer->approve($candidate, $reviewerUser, [
                        'confirmed_mpn' => $decision['confirmed_mpn'],
                        'confirmed_manufacturer' => $decision['manufacturer'],
                        'confirmed_category' => $decision['category'],
                        'review_note' => sprintf('Evidence: %s (%s; checked %s).', $decision['source_url'], $decision['source_kind'], $decision['checked_at']),
                    ]);
                }
            });
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->info(sprintf('Applied %d evidence-backed identity decision(s).', count($decisions)));

        return self::SUCCESS;
    }

    /** @return list<array{candidate_id:int,external_id_1c:string,confirmed_mpn:string,manufacturer:string,category:string,source_url:string,source_kind:string,checked_at:string}> */
    private function decisions(string $file): array
    {
        if (! is_file($file)) {
            throw new RuntimeException('Evidence decisions file was not found.');
        }
        $decoded = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        if (! is_array($decoded) || ! isset($decoded['decisions']) || ! is_array($decoded['decisions'])) {
            throw new RuntimeException('Evidence decisions JSON must contain a decisions array.');
        }

        return array_values($decoded['decisions']);
    }

    /** @param list<array<string, mixed>> $decisions */
    private function validate(array $decisions): void
    {
        if ($decisions === []) {
            throw new RuntimeException('At least one evidence decision is required.');
        }
        $ids = [];
        foreach ($decisions as $decision) {
            foreach (['candidate_id', 'external_id_1c', 'confirmed_mpn', 'manufacturer', 'category', 'source_url', 'source_kind', 'checked_at'] as $field) {
                if (! isset($decision[$field]) || trim((string) $decision[$field]) === '') {
                    throw new RuntimeException("Evidence decision misses {$field}.");
                }
            }
            if (! filter_var($decision['source_url'], FILTER_VALIDATE_URL) || ! str_starts_with((string) $decision['source_url'], 'https://')) {
                throw new RuntimeException('Evidence source_url must be an HTTPS URL.');
            }
            if (isset($ids[(int) $decision['candidate_id']])) {
                throw new RuntimeException('Evidence decisions repeat a candidate_id.');
            }
            $ids[(int) $decision['candidate_id']] = true;
        }
    }

    /** @param array<string, mixed> $decision */
    private function assertMatchesEvidence(CatalogIdentityCandidate $candidate, array $decision): void
    {
        if ($candidate->review_status !== 'pending') {
            throw new RuntimeException("Candidate {$candidate->id} is no longer pending.");
        }
        if ($candidate->comparison_status !== 'agree' || (float) $candidate->confidence !== 0.95) {
            throw new RuntimeException("Candidate {$candidate->id} no longer satisfies the strict match gate.");
        }
        if ((string) $candidate->oneCItem->external_id !== (string) $decision['external_id_1c']) {
            throw new RuntimeException("Candidate {$candidate->id} 1C external ID does not match its evidence.");
        }
    }

    private function reviewer(string $email): User
    {
        $query = User::query()->where('is_admin', true);
        if ($email !== '') {
            $query->where('email', $email);
        }
        $reviewer = $query->sole();

        return $reviewer;
    }
}
