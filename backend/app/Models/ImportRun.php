<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class ImportRun extends Model
{
    protected $fillable = [
        'source', 'status', 'source_file', 'total_records', 'processed_records', 'failed_records',
        'summary', 'started_at', 'finished_at',
    ];

    protected function casts(): array
    {
        return ['summary' => 'array', 'started_at' => 'datetime', 'finished_at' => 'datetime'];
    }
}
