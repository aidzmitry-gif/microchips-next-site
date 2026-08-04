<?php

namespace App\Domain\Imports;

use App\Models\Site;
use App\Models\SiteCommercialFact;
use App\Models\SiteContact;
use Illuminate\Support\Facades\DB;
use RuntimeException;
use Throwable;

/**
 * Restores approved country profile data as drafts only. Verification and
 * publication are intentionally separate admin actions.
 */
final class SiteCommercialProfileDraftImporter
{
    /** @return array<string, int|string> */
    public function import(Site $site, string $file, bool $apply): array
    {
        $profile = $this->read($site, $file);
        $summary = ['mode' => $apply ? 'apply' : 'dry_run', 'site_key' => $site->key, 'contacts_created' => 0, 'contacts_updated' => 0, 'contacts_unchanged' => 0, 'facts_created' => 0, 'facts_updated' => 0, 'facts_unchanged' => 0, 'publication_status' => 'import_never_publishes_or_changes_verification'];

        DB::beginTransaction();
        try {
            foreach ($profile['contacts'] as $draft) {
                $contact = SiteContact::query()->where('site_id', $site->id)->where('locale', $draft['locale'])->where('type', $draft['type'])->where('label', $draft['label'])->first();
                $values = array_intersect_key($draft, array_flip(['locale', 'city', 'type', 'label', 'value', 'is_primary']));
                if ($contact === null) {
                    SiteContact::create(['site_id' => $site->id, ...$values, 'is_published' => false]);
                    $summary['contacts_created']++;
                } else {
                    $contact->fill($values);
                    if ($contact->is_published && $contact->isDirty()) {
                        throw new RuntimeException("Refusing to overwrite verified contact: {$draft['label']}.");
                    }
                    if ($contact->isDirty()) {
                        $contact->save();
                        $summary['contacts_updated']++;
                    } else {
                        $summary['contacts_unchanged']++;
                    }
                }
            }

            foreach ($profile['facts'] as $draft) {
                $fact = SiteCommercialFact::query()->where('site_id', $site->id)->where('locale', $draft['locale'])->where('key', $draft['key'])->first();
                $values = array_intersect_key($draft, array_flip(['locale', 'key', 'value']));
                if ($fact === null) {
                    SiteCommercialFact::create(['site_id' => $site->id, ...$values, 'is_published' => false]);
                    $summary['facts_created']++;
                } else {
                    $fact->fill($values);
                    if ($fact->is_published && $fact->isDirty()) {
                        throw new RuntimeException("Refusing to overwrite verified commercial fact: {$draft['key']}.");
                    }
                    if ($fact->isDirty()) {
                        $fact->save();
                        $summary['facts_updated']++;
                    } else {
                        $summary['facts_unchanged']++;
                    }
                }
            }
            $apply ? DB::commit() : DB::rollBack();
        } catch (Throwable $error) {
            if (DB::transactionLevel() > 0) {
                DB::rollBack();
            }
            throw $error;
        }

        return $summary;
    }

    /** @return array{contacts:list<array<string, mixed>>,facts:list<array<string, mixed>>} */
    private function read(Site $site, string $file): array
    {
        if (! is_file($file) || ($raw = file_get_contents($file)) === false) {
            throw new RuntimeException('Commercial profile manifest was not found.');
        }
        try {
            $manifest = json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException) {
            throw new RuntimeException('Commercial profile manifest is not valid JSON.');
        }
        if (! is_array($manifest) || ($manifest['schema_version'] ?? null) !== 1 || ! is_string($manifest['source'] ?? null) || trim($manifest['source']) === '' || ! is_array($manifest['contacts'] ?? null) || ! is_array($manifest['commercial_facts'] ?? null)) {
            throw new RuntimeException('Commercial profile manifest must contain schema_version 1, source, contacts and commercial_facts.');
        }

        $contacts = $this->validateRecords($manifest['contacts'], ['locale', 'city', 'type', 'label', 'value', 'is_primary'], 'contact');
        $facts = $this->validateRecords($manifest['commercial_facts'], ['locale', 'key', 'value'], 'commercial fact');
        $enabledLocales = $site->locales()->where('is_enabled', true)->pluck('locale')->all();
        $enabledLocales[] = $site->default_locale;
        foreach ([...$contacts, ...$facts] as $record) {
            if (! in_array($record['locale'], $enabledLocales, true)) {
                throw new RuntimeException("Profile locale {$record['locale']} is not enabled for this site.");
            }
        }
        foreach ($contacts as $contact) {
            if (! in_array($contact['type'], SiteContact::TYPES, true) || ! is_bool($contact['is_primary'])) {
                throw new RuntimeException('Commercial profile contains an invalid contact type or is_primary value.');
            }
        }
        foreach ($facts as $fact) {
            if (! in_array($fact['key'], SiteCommercialFact::KEYS, true)) {
                throw new RuntimeException("Commercial profile contains unsupported fact key: {$fact['key']}.");
            }
        }

        return ['contacts' => $contacts, 'facts' => $facts];
    }

    /** @param mixed $records @param list<string> $fields @return list<array<string, mixed>> */
    private function validateRecords(mixed $records, array $fields, string $kind): array
    {
        if (! is_array($records) || $records === []) {
            throw new RuntimeException("Commercial profile must contain at least one {$kind}.");
        }
        $result = [];
        foreach ($records as $index => $record) {
            if (! is_array($record)) {
                throw new RuntimeException("Profile {$kind} #{$index} must be an object.");
            }
            foreach ($fields as $field) {
                if ($field === 'is_primary') {
                    continue;
                }
                if (! is_string($record[$field] ?? null) || trim($record[$field]) === '') {
                    throw new RuntimeException("Profile {$kind} #{$index} has invalid {$field}.");
                }
                $record[$field] = trim($record[$field]);
            }
            $result[] = $record;
        }

        return $result;
    }
}
