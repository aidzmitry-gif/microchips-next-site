<?php

namespace App\Models;

use App\Events\SiteContentChanged;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Validation\ValidationException;

class SiteCommercialFact extends Model
{
    public const KEYS = ['legal_name', 'legal_address', 'delivery_terms', 'payment_terms', 'warranty_terms'];

    protected $fillable = [
        'site_id', 'locale', 'key', 'value', 'is_published', 'verified_at', 'verified_by', 'verification_note',
    ];

    protected function casts(): array
    {
        return ['is_published' => 'boolean', 'verified_at' => 'datetime'];
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
        static::saving(function (self $fact): void {
            if ($fact->exists && $fact->getOriginal('is_published') && $fact->isDirty(['locale', 'key', 'value'])) {
                $fact->is_published = false;
                $fact->verified_at = null;
                $fact->verified_by = null;
                $fact->verification_note = null;
            }

            $fact->validateForStorage();
        });
        static::saved(fn (self $fact) => self::revalidate($fact));
        static::deleted(fn (self $fact) => self::revalidate($fact));
    }

    private function validateForStorage(): void
    {
        $errors = [];
        if (! in_array($this->key, self::KEYS, true)) {
            $errors['key'] = 'Unsupported commercial fact key.';
        }
        if (blank($this->locale) || mb_strlen($this->locale) > 10) {
            $errors['locale'] = 'A valid locale is required.';
        }
        if (blank($this->value)) {
            $errors['value'] = 'A commercial fact value is required.';
        }
        if ($this->is_published && ($this->verified_at === null || $this->verified_by === null || blank($this->verification_note))) {
            $errors['is_published'] = 'A published fact requires verifier, date, and note.';
        }
        if ($errors !== []) {
            throw ValidationException::withMessages($errors);
        }
    }

    private static function revalidate(self $fact): void
    {
        if ($fact->site !== null) {
            SiteContentChanged::dispatch($fact->site, ['/', '/contacts', '/delivery', '/payment', '/warranty', '/warranty-and-documents', '/sitemap.xml']);
        }
    }
}
