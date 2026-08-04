<?php

namespace App\Console\Commands;

use App\Domain\Imports\StagedProductPublisher;
use App\Models\Site;
use App\Models\StagedImportRecord;
use App\Models\User;
use Illuminate\Console\Command;
use Illuminate\Database\Eloquent\Collection;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

class ReviewAndPublishStagedDelta extends Command
{
    protected $signature = 'catalog:review-publish-staged-delta
                            {site : Active site key, for example microchips-by}
                            {run : Import run ID containing only the intended delta}
                            {--expected-count= : Exact number of ready records expected in the run}
                            {--reviewer-email= : Existing administrator e-mail}
                            {--apply : Review and create site drafts; default is dry-run}';

    protected $description = 'Review a bounded staged delta and create non-public site product drafts';

    public function handle(StagedProductPublisher $publisher): int
    {
        try {
            $site = Site::query()->where('key', (string) $this->argument('site'))->where('is_active', true)->sole();
            $reviewer = $this->reviewer((string) $this->option('reviewer-email'));
            $records = $this->records((int) $this->argument('run'));
            $this->assertExpectedCount($records->count());

            if (! $this->option('apply')) {
                $this->info(sprintf(
                    'Dry-run passed: %d staged record(s) from run %d can be reviewed and published as non-public drafts for %s. No database records changed.',
                    $records->count(),
                    (int) $this->argument('run'),
                    $site->key,
                ));

                return self::SUCCESS;
            }

            DB::transaction(function () use ($records, $publisher, $reviewer, $site): void {
                foreach ($records as $record) {
                    $reviewed = $publisher->review(
                        $record,
                        $reviewer,
                        'Evidence-backed identity decision; published as a non-public RB draft.',
                    );
                    $published = $publisher->publishToSite($reviewed, $site, $reviewer);

                    if (($published->publication_snapshot['publicly_visible'] ?? true) !== false) {
                        throw new RuntimeException("Record {$published->id} was not kept non-public.");
                    }
                }
            });
        } catch (Throwable $error) {
            $this->error($error->getMessage());

            return self::FAILURE;
        }

        $this->info(sprintf(
            'Reviewed and published %d staged record(s) from run %d as non-public drafts for %s.',
            $records->count(),
            (int) $this->argument('run'),
            $site->key,
        ));

        return self::SUCCESS;
    }

    /** @return Collection<int, StagedImportRecord> */
    private function records(int $runId): Collection
    {
        $records = StagedImportRecord::query()
            ->where('import_run_id', $runId)
            ->where('entity_type', 'product')
            ->orderBy('id')
            ->get();

        if ($records->isEmpty()) {
            throw new RuntimeException("Import run {$runId} has no staged product records.");
        }
        if ($records->contains(fn (StagedImportRecord $record): bool => $record->status !== 'ready_for_review')) {
            throw new RuntimeException("Import run {$runId} contains records that are not ready for review; use a dedicated, untouched delta run.");
        }

        return $records;
    }

    private function assertExpectedCount(int $actual): void
    {
        $expected = (string) $this->option('expected-count');
        if ($expected === '' || ! ctype_digit($expected) || (int) $expected < 1) {
            throw new RuntimeException('The --expected-count option must be a positive integer safety check.');
        }
        if ((int) $expected !== $actual) {
            throw new RuntimeException("Expected {$expected} ready staged record(s), found {$actual}.");
        }
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
