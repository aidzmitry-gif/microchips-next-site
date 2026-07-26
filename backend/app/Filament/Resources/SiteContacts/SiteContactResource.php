<?php

namespace App\Filament\Resources\SiteContacts;

use App\Filament\Resources\SiteContacts\Pages\CreateSiteContact;
use App\Filament\Resources\SiteContacts\Pages\EditSiteContact;
use App\Filament\Resources\SiteContacts\Pages\ListSiteContacts;
use App\Models\SiteContact;
use App\Models\User;
use Filament\Actions\Action;
use Filament\Actions\BulkActionGroup;
use Filament\Actions\DeleteBulkAction;
use Filament\Actions\EditAction;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\Textarea;
use Filament\Forms\Components\TextInput;
use Filament\Forms\Components\Toggle;
use Filament\Resources\Resource;
use Filament\Schemas\Schema;
use Filament\Tables\Columns\IconColumn;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Filters\SelectFilter;
use Filament\Tables\Table;

class SiteContactResource extends Resource
{
    protected static ?string $model = SiteContact::class;

    protected static ?string $navigationLabel = 'Контакты сайтов';

    protected static string|\UnitEnum|null $navigationGroup = 'Сайты';

    public static function form(Schema $schema): Schema
    {
        return $schema->components([
            Select::make('site_id')->relationship('site', 'name')->searchable()->preload()->required(),
            TextInput::make('locale')->maxLength(10),
            TextInput::make('city')->maxLength(255),
            Select::make('type')->options(array_combine(SiteContact::TYPES, SiteContact::TYPES))->required(),
            TextInput::make('label')->required()->maxLength(255),
            TextInput::make('value')->required()->maxLength(2000)->columnSpanFull(),
            Toggle::make('is_primary')->default(false),
        ])->columns(2);
    }

    public static function table(Table $table): Table
    {
        return $table->columns([
            TextColumn::make('site.name')->label('Сайт')->searchable(),
            TextColumn::make('locale')->label('Локаль')->badge(),
            TextColumn::make('type')->label('Тип')->badge(),
            TextColumn::make('label')->label('Метка')->searchable(),
            TextColumn::make('value')->label('Значение')->limit(48),
            IconColumn::make('is_published')->label('Опубликован')->boolean(),
            TextColumn::make('verified_at')->label('Проверен')->dateTime()->placeholder('—'),
        ])->filters([
            SelectFilter::make('type')->options(array_combine(SiteContact::TYPES, SiteContact::TYPES)),
        ])->recordActions([
            EditAction::make(),
            Action::make('publish')
                ->label('Подтвердить и опубликовать')
                ->color('success')
                ->visible(fn (SiteContact $record): bool => ! $record->is_published)
                ->form([Textarea::make('verification_note')->required()->maxLength(255)])
                ->action(function (SiteContact $record, array $data): void {
                    $verifier = auth()->user();
                    if (! $verifier instanceof User) {
                        abort(403);
                    }

                    $record->publish($verifier, $data['verification_note']);
                }),
            Action::make('unpublish')
                ->label('Снять с публикации')
                ->color('warning')
                ->requiresConfirmation()
                ->visible(fn (SiteContact $record): bool => $record->is_published)
                ->action(fn (SiteContact $record): mixed => $record->unpublish()),
        ])
            ->toolbarActions([BulkActionGroup::make([DeleteBulkAction::make()])]);
    }

    public static function getPages(): array
    {
        return [
            'index' => ListSiteContacts::route('/'),
            'create' => CreateSiteContact::route('/create'),
            'edit' => EditSiteContact::route('/{record}/edit'),
        ];
    }
}
