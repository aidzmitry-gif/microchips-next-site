<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Lead extends Model
{
    public const STATUSES = ['new', 'in_progress', 'closed', 'rejected'];

    protected $fillable = [
        'site_id', 'locale', 'type', 'company', 'contact_name', 'email', 'phone', 'message', 'page_url',
        'cart', 'utm', 'status', 'handled_by', 'handled_at', 'internal_note', 'external_id', 'external_error',
    ];

    protected function casts(): array
    {
        return ['cart' => 'array', 'utm' => 'array', 'handled_at' => 'datetime'];
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    public function handledBy(): BelongsTo
    {
        return $this->belongsTo(User::class, 'handled_by');
    }

    public function startProcessing(User $operator, ?string $note = null): void
    {
        $this->update([
            'status' => 'in_progress',
            'handled_by' => $operator->id,
            'handled_at' => now(),
            'internal_note' => filled($note) ? trim($note) : $this->internal_note,
        ]);
    }

    public function close(User $operator, string $note): void
    {
        $note = trim($note);
        if ($note === '') {
            throw new \InvalidArgumentException('A closing note is required.');
        }

        $this->update([
            'status' => 'closed',
            'handled_by' => $operator->id,
            'handled_at' => now(),
            'internal_note' => $note,
        ]);
    }
}
