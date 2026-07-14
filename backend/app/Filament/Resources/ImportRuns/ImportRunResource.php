<?php

namespace App\Filament\Resources\ImportRuns;

use App\Filament\Resources\ImportRuns\Pages\ListImportRuns;
use App\Models\ImportRun;
use Filament\Resources\Resource;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Table;

class ImportRunResource extends Resource
{
    protected static ?string $model = ImportRun::class;

    protected static ?string $navigationLabel = 'Импорт 1С: прогоны';

    protected static ?string $modelLabel = 'прогон импорта';

    protected static ?string $pluralModelLabel = 'прогоны импорта';

    protected static string|\UnitEnum|null $navigationGroup = 'Импорт каталога';

    public static function table(Table $table): Table
    {
        return $table
            ->defaultSort('id', 'desc')
            ->columns([
                TextColumn::make('id')->label('ID')->sortable(),
                TextColumn::make('source_file')->label('Файл')->searchable(),
                TextColumn::make('status')->label('Статус')->badge(),
                TextColumn::make('total_records')->label('Записей')->numeric()->sortable(),
                TextColumn::make('summary.ready_for_review')->label('Готово')->numeric(),
                TextColumn::make('summary.invalid')->label('Ошибок')->numeric(),
                TextColumn::make('summary.duplicate_conflicts')->label('Конфликтов')->numeric(),
                TextColumn::make('finished_at')->label('Завершён')->dateTime()->sortable(),
            ]);
    }

    public static function getPages(): array
    {
        return [
            'index' => ListImportRuns::route('/'),
        ];
    }
}
