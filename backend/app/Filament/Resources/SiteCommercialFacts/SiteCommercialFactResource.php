<?php

namespace App\Filament\Resources\SiteCommercialFacts;

use App\Filament\Resources\SiteCommercialFacts\Pages\CreateSiteCommercialFact;
use App\Filament\Resources\SiteCommercialFacts\Pages\EditSiteCommercialFact;
use App\Filament\Resources\SiteCommercialFacts\Pages\ListSiteCommercialFacts;
use App\Models\SiteCommercialFact;
use App\Models\User;
use Filament\Actions\Action;
use Filament\Actions\BulkActionGroup;
use Filament\Actions\DeleteBulkAction;
use Filament\Actions\EditAction;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\Textarea;
use Filament\Forms\Components\TextInput;
use Filament\Resources\Resource;
use Filament\Schemas\Schema;
use Filament\Tables\Columns\IconColumn;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Table;

class SiteCommercialFactResource extends Resource
{
    protected static ?string $model = SiteCommercialFact::class;

    protected static ?string $navigationLabel = 'Commercial facts';

    protected static string|\UnitEnum|null $navigationGroup = 'Sites';

    public static function form(Schema $schema): Schema
    {
        return $schema->components([
            Select::make('site_id')->relationship('site', 'name')->searchable()->preload()->required(),
            TextInput::make('locale')->required()->maxLength(10),
            Select::make('key')->options(array_combine(SiteCommercialFact::KEYS, SiteCommercialFact::KEYS))->required(),
            Textarea::make('value')->required()->rows(6)->columnSpanFull(),
        ])->columns(2);
    }

    public static function table(Table $table): Table
    {
        return $table->columns([
            TextColumn::make('site.name')->label('Site')->searchable(),
            TextColumn::make('locale')->badge(),
            TextColumn::make('key')->badge(),
            TextColumn::make('value')->limit(70),
            IconColumn::make('is_published')->label('Published')->boolean(),
            TextColumn::make('verified_at')->label('Verified')->dateTime()->placeholder('-'),
        ])->recordActions([
            EditAction::make(),
            Action::make('publish')
                ->label('Verify and publish')
                ->color('success')
                ->visible(fn (SiteCommercialFact $record): bool => ! $record->is_published)
                ->form([Textarea::make('verification_note')->required()->maxLength(255)])
                ->action(function (SiteCommercialFact $record, array $data): void {
                    $verifier = auth()->user();
                    if (! $verifier instanceof User) {
                        abort(403);
                    }
                    $record->publish($verifier, $data['verification_note']);
                }),
            Action::make('unpublish')
                ->label('Unpublish')
                ->color('warning')
                ->requiresConfirmation()
                ->visible(fn (SiteCommercialFact $record): bool => $record->is_published)
                ->action(fn (SiteCommercialFact $record): mixed => $record->unpublish()),
        ])->toolbarActions([BulkActionGroup::make([DeleteBulkAction::make()])]);
    }

    public static function getPages(): array
    {
        return [
            'index' => ListSiteCommercialFacts::route('/'),
            'create' => CreateSiteCommercialFact::route('/create'),
            'edit' => EditSiteCommercialFact::route('/{record}/edit'),
        ];
    }
}
