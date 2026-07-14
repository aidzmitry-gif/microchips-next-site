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
                TextColumn::make('candidate_ids.staged_record_ids')
                    ->label('Записи CSV')
                    ->formatStateUsing(fn (?array $state): string => implode(', ', $state ?? [])),
                TextColumn::make('candidate_ids.product_ids')
                    ->label('Товары каталога')
                    ->formatStateUsing(fn (?array $state): string => implode(', ', $state ?? [])),
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
