<?php

namespace App\Filament\Resources\DuplicateConflicts;

use App\Filament\Resources\DuplicateConflicts\Pages\ListDuplicateConflicts;
use App\Models\DuplicateConflict;
use Filament\Resources\Resource;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Filters\SelectFilter;
use Filament\Tables\Table;

class DuplicateConflictResource extends Resource
{
    protected static ?string $model = DuplicateConflict::class;

    protected static ?string $navigationLabel = 'Импорт 1С: конфликты';

    protected static ?string $modelLabel = 'конфликт дубликата';

    protected static ?string $pluralModelLabel = 'конфликты дубликатов';

    protected static string|\UnitEnum|null $navigationGroup = 'Импорт каталога';

    public static function table(Table $table): Table
    {
        return $table
            ->defaultSort('id', 'desc')
            ->columns([
                TextColumn::make('import_run_id')->label('Прогон')->sortable(),
                TextColumn::make('match_key')->label('Ключ совпадения')->searchable(),
                // Compute the whole cell as a string via state(): a dot-path to the
                // candidate_ids array made Filament treat the state as a list and call
                // formatStateUsing() once per scalar item (int), throwing a TypeError
                // and crashing the list as soon as a conflict had any candidate id.
                TextColumn::make('staged_record_ids')
                    ->label('Записи CSV')
                    ->state(fn (DuplicateConflict $record): string => implode(', ', $record->candidate_ids['staged_record_ids'] ?? [])),
                TextColumn::make('product_ids')
                    ->label('Товары каталога')
                    ->state(fn (DuplicateConflict $record): string => implode(', ', $record->candidate_ids['product_ids'] ?? [])),
                TextColumn::make('status')->label('Статус')->badge(),
                TextColumn::make('created_at')->label('Найден')->dateTime()->sortable(),
            ])
            ->filters([
                SelectFilter::make('status')->label('Статус')->options(['open' => 'Открыт', 'resolved' => 'Решён']),
            ]);
    }

    public static function getPages(): array
    {
        return [
            'index' => ListDuplicateConflicts::route('/'),
        ];
    }
}
