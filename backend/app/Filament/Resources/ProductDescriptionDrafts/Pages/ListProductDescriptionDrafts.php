<?php

namespace App\Filament\Resources\ProductDescriptionDrafts\Pages;

use App\Filament\Resources\ProductDescriptionDrafts\ProductDescriptionDraftResource;
use Filament\Resources\Pages\ListRecords;

class ListProductDescriptionDrafts extends ListRecords
{
    protected static string $resource = ProductDescriptionDraftResource::class;
}
