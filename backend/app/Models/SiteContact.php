<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Validation\ValidationException;

class SiteContact extends Model
{
    public const TYPES = ['phone', 'email', 'address', 'working_hours', 'legal_entity'];

    protected $fillable = [
        'site_id', 'locale', 'city', 'type', 'label', 'value', 'is_primary',
        'is_published', 'verified_at', 'verified_by', 'verification_note',
    ];

    protected function casts(): array
    {
        return [
            'is_primary' => 'boolean',
            'is_published' => 'boolean',
            'verified_at' => 'datetime',
        ];
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    public function verifiedBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'verified_by');
    }

    public function scopePublished(Builder $query): Builder
    {
        return $query->where('is_published', true);
    }

    public function publish(User $verifier, string $note): void
    {
        $note = trim($note);
        if ($note === '') {
            throw ValidationException::withMessages(['verification_note' => 'A verification note is required before publication.']);
        }

        $this->forceFill([
            'is_published' => true,
            'verified_at' => now(),
            'verified_by' => $verifier->id,
            'verification_note' => $note,
        ])->save();
    }

    public function unpublish(): void
    {
        $this->forceFill([
            'is_published' => false,
            'verified_at' => null,
            'verified_by' => null,
            'verification_note' => null,
        ])->save();
    }

    protected static function booted(): void
    {
        static::saving(function (self $contact): void {
            if ($contact->exists && $contact->getOriginal('is_published') && $contact->isDirty(['locale', 'city', 'type', 'label', 'value'])) {
                $contact->is_published = false;
                $contact->verified_at = null;
                $contact->verified_by = null;
                $contact->verification_note = null;
            }
            $contact->validateForStorage();
        });
        static::saved(fn (self $contact) => self::revalidate($contact));
        static::deleted(fn (self $contact) => self::revalidate($contact));
    }

    private function validateForStorage(): void
    {
        $errors = [];
        if (! in_array($this->type, self::TYPES, true)) {
            $errors['type'] = 'Unsupported site contact type.';
        }
        if ($this->is_published && ($this->verified_at === null || $this->verified_by === null || blank($this->verification_note))) {
            $errors['is_published'] = 'A published contact requires verifier, date, and note.';
        }
        if (! $this->hasValidValue()) {
            $errors['value'] = 'The contact value is not valid for its type.';
        }
        if ($errors !== []) {
            throw ValidationException::withMessages($errors);
        }
    }

    private function hasValidValue(): bool
    {
        $value = trim($this->value);

        return match ($this->type) {
            'phone' => preg_match('/^\+?[0-9()\-\s]{7,32}$/', $value) === 1,
            'email' => filter_var($value, FILTER_VALIDATE_EMAIL) !== false,
            'address', 'working_hours', 'legal_entity' => $value !== '' && mb_strlen($value) <= 2000,
            default => false,
        };
    }

    private static function revalidate(self $contact): void
    {
        if ($contact->site === null) {
            return;
        }

        SiteContentChanged::dispatch($contact->site, [
            '/', '/contacts', '/delivery', '/payment', '/warranty', '/warranty-and-documents', '/sitemap.xml',
        ]);
    }
}
