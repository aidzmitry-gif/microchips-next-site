<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class DuplicateConflict extends Model
{
    protected $fillable = ['import_run_id', 'entity_type', 'match_key', 'candidate_ids', 'status', 'resolution_note'];

    protected function casts(): array
    {
        return ['candidate_ids' => 'array'];
    }
}
