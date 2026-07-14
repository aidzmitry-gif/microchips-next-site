<?php

namespace App\Filament\Resources\Sites;

use App\Filament\Resources\Sites\Pages\CreateSite;
use App\Filament\Resources\Sites\Pages\EditSite;
use App\Filament\Resources\Sites\Pages\ListSites;
use App\Models\Site;
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
use Filament\Tables\Table;

class SiteResource extends Resource
{
    protected static ?string $model = Site::class;

    protected static ?string $navigationLabel = 'Сайты';

    protected static ?string $modelLabel = 'сайт';

    protected static ?string $pluralModelLabel = 'сайты';

    public static function form(Schema $schema): Schema
    {
        return $schema->components([
            TextInput::make('key')->required()->unique(ignoreRecord: true)->maxLength(64),
            TextInput::make('domain')->required()->unique(ignoreRecord: true)->maxLength(255),
            Select::make('country_code')->label('Страна')->options(['BY' => 'Беларусь', 'RU' => 'Россия', 'UZ' => 'Узбекистан', 'KZ' => 'Казахстан'])->required(),
            TextInput::make('currency_code')->label('Валюта')->required()->maxLength(3),
            TextInput::make('default_locale')->label('Локаль по умолчанию')->required()->maxLength(10),
            TextInput::make('name')->label('Название')->required()->maxLength(255),
            TextInput::make('legal_name')->label('Юридическое лицо')->maxLength(255),
            Textarea::make('legal_address')->label('Юридический адрес')->columnSpanFull(),
            TextInput::make('phone')->label('Телефон')->tel(),
            TextInput::make('email')->label('E-mail')->email(),
            Textarea::make('delivery_terms')->label('Условия доставки')->columnSpanFull(),
            Textarea::make('payment_terms')->label('Условия оплаты')->columnSpanFull(),
            Toggle::make('is_active')->label('Активен')->default(true),
        ])->columns(2);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('name')->label('Сайт')->searchable(),
                TextColumn::make('domain')->label('Домен')->copyable(),
                TextColumn::make('country_code')->label('Страна'),
                TextColumn::make('default_locale')->label('Локаль'),
                IconColumn::make('is_active')->label('Активен')->boolean(),
                TextColumn::make('updated_at')->label('Изменён')->since(),
            ])
            ->recordActions([EditAction::make()])
            ->toolbarActions([BulkActionGroup::make([DeleteBulkAction::make()])]);
    }

    public static function getPages(): array
    {
        return [
            'index' => ListSites::route('/'),
            'create' => CreateSite::route('/create'),
            'edit' => EditSite::route('/{record}/edit'),
        ];
    }
}
