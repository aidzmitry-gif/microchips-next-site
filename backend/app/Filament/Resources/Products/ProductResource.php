<?php

namespace App\Filament\Resources\Products;

use App\Filament\Resources\Products\Pages\CreateProduct;
use App\Filament\Resources\Products\Pages\EditProduct;
use App\Filament\Resources\Products\Pages\ListProducts;
use App\Models\Product;
use Filament\Actions\BulkActionGroup;
use Filament\Actions\DeleteBulkAction;
use Filament\Actions\EditAction;
use Filament\Forms\Components\KeyValue;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\Textarea;
use Filament\Forms\Components\TextInput;
use Filament\Resources\Resource;
use Filament\Schemas\Schema;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Table;

class ProductResource extends Resource
{
    protected static ?string $model = Product::class;

    protected static ?string $navigationLabel = 'Общий каталог';

    protected static ?string $modelLabel = 'товар';

    protected static ?string $pluralModelLabel = 'товары';

    public static function form(Schema $schema): Schema
    {
        return $schema->components([
            TextInput::make('name')->label('Наименование')->required()->maxLength(255),
            TextInput::make('slug')->required()->unique(ignoreRecord: true)->maxLength(255),
            TextInput::make('sku')->label('Артикул')->maxLength(255),
            TextInput::make('mpn')->label('MPN')->maxLength(255),
            TextInput::make('manufacturer')->label('Производитель')->maxLength(255),
            Select::make('status')->options(['draft' => 'Черновик', 'active' => 'Активен', 'archived' => 'Архив'])->required()->default('draft'),
            Textarea::make('short_description')->label('Краткое описание')->columnSpanFull(),
            KeyValue::make('technical_attributes')->label('Технические характеристики')->columnSpanFull(),
        ])->columns(2);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->columns([
                TextColumn::make('name')->label('Наименование')->searchable()->sortable(),
                TextColumn::make('sku')->label('Артикул')->searchable(),
                TextColumn::make('mpn')->label('MPN')->searchable(),
                TextColumn::make('manufacturer')->label('Производитель')->toggleable(),
                TextColumn::make('status')->label('Статус')->badge(),
                TextColumn::make('updated_at')->label('Изменён')->since(),
            ])
            ->recordActions([EditAction::make()])
            ->toolbarActions([BulkActionGroup::make([DeleteBulkAction::make()])]);
    }

    public static function getPages(): array
    {
        return [
            'index' => ListProducts::route('/'),
            'create' => CreateProduct::route('/create'),
            'edit' => EditProduct::route('/{record}/edit'),
        ];
    }
}
