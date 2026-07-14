<?php

namespace App\Filament\Resources\DuplicateConflicts\Pages;

use App\Filament\Resources\DuplicateConflicts\DuplicateConflictResource;
use Filament\Resources\Pages\ListRecords;

class ListDuplicateConflicts extends ListRecords
{
    protected static string $resource = DuplicateConflictResource::class;
}
