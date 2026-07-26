<?php

namespace App\Filament\Resources\SiteCommercialFacts\Pages;

use App\Filament\Resources\SiteCommercialFacts\SiteCommercialFactResource;
use Filament\Actions\CreateAction;
use Filament\Resources\Pages\ListRecords;

class ListSiteCommercialFacts extends ListRecords
{
    protected static string $resource = SiteCommercialFactResource::class;

    protected function getHeaderActions(): array
    {
        return [CreateAction::make()];
    }
}
