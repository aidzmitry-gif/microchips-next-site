<?php

namespace App\Filament\Widgets;

use App\Models\DuplicateConflict;
use App\Models\Lead;
use App\Models\Site;
use App\Models\SiteCategoryProduct;
use App\Models\SitePage;
use App\Models\SiteProduct;
use App\Models\SiteUrl;
use Filament\Widgets\StatsOverviewWidget as BaseWidget;
use Filament\Widgets\StatsOverviewWidget\Stat;

class RbOperationalReadinessWidget extends BaseWidget
{
    protected static ?int $sort = -3;

    /** @return array<Stat> */
    protected function getStats(): array
    {
        $site = Site::query()->where('key', 'microchips-by')->first();
        if ($site === null) {
            return [Stat::make('RB operational readiness', 'Site profile is not configured')->color('danger')];
        }

        $drafts = SiteProduct::query()->where('site_id', $site->id)->where('is_published', false)->count();
        $published = SiteProduct::query()->where('site_id', $site->id)->where('is_published', true)->count();
        $categoryLinks = SiteCategoryProduct::query()->where('site_id', $site->id)->count();
        $pendingLeads = Lead::query()->where('site_id', $site->id)->whereIn('status', ['new', 'in_progress'])->count();
        $openConflicts = DuplicateConflict::query()->where('status', 'open')->count();
        $draftPages = SitePage::query()->where('site_id', $site->id)->where('is_published', false)->count();
        $indexableUrls = SiteUrl::query()->where('site_id', $site->id)->where('is_indexable', true)->count();

        return [
            Stat::make('RB catalog drafts', (string) $drafts)
                ->description("{$categoryLinks} category links; {$published} public cards")
                ->color($drafts > 0 && $published === 0 ? 'success' : 'warning'),
            Stat::make('Open duplicate conflicts', (string) $openConflicts)
                ->description('Must remain zero before review or release')
                ->color($openConflicts === 0 ? 'success' : 'danger'),
            Stat::make('Local inbox queue', (string) $pendingLeads)
                ->description('New and in-progress RB leads')
                ->color($pendingLeads === 0 ? 'success' : 'warning'),
            Stat::make('Regional content drafts', (string) $draftPages)
                ->description("{$indexableUrls} indexable RB URL(s)")
                ->color($indexableUrls === 0 ? 'warning' : 'success'),
        ];
    }
}
