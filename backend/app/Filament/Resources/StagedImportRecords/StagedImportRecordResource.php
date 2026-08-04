<?php

namespace App\Filament\Resources\StagedImportRecords;

use App\Domain\Imports\StagedProductPublisher;
use App\Filament\Resources\StagedImportRecords\Pages\ListStagedImportRecords;
use App\Models\Site;
use App\Models\StagedImportRecord;
use Filament\Actions\Action;
use Filament\Forms\Components\Checkbox;
use Filament\Forms\Components\Select;
use Filament\Forms\Components\Textarea;
use Filament\Resources\Resource;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Filters\SelectFilter;
use Filament\Tables\Table;

class StagedImportRecordResource extends Resource
{
    protected static ?string $model = StagedImportRecord::class;

    protected static ?string $navigationLabel = 'Импорт: записи и снимки';

    protected static ?string $modelLabel = 'запись импорта';

    protected static ?string $pluralModelLabel = 'записи импорта';

    protected static string|\UnitEnum|null $navigationGroup = 'Импорт каталога';

    public static function table(Table $table): Table
    {
        return $table
            ->defaultSort('id', 'desc')
            ->columns([
                TextColumn::make('import_run_id')->label('Прогон')->sortable(),
                TextColumn::make('row_number')->label('Строка')->sortable(),
                TextColumn::make('external_id')->label('ID 1С')->searchable()->toggleable(),
                TextColumn::make('normalized_payload.name')->label('Товар')->searchable()->limit(48),
                TextColumn::make('payload.legacy_name')
                    ->label('Товар Bitrix')
                    ->searchable()
                    ->limit(56)
                    ->toggleable(),
                TextColumn::make('payload.one_c_external_id')
                    ->label('Связь 1С')
                    ->searchable()
                    ->toggleable(),
                TextColumn::make('payload.transfer_status')
                    ->label('Статус переноса')
                    ->badge()
                    ->toggleable(),
                TextColumn::make('payload.legacy_url_candidate')
                    ->label('Старый URL')
                    ->limit(48)
                    ->toggleable(isToggledHiddenByDefault: true),
                TextColumn::make('normalized_payload.sku')->label('Артикул')->searchable()->toggleable(),
                TextColumn::make('status')->label('Статус')->badge(),
                TextColumn::make('validation_errors')
                    ->label('Ошибки')
                    ->formatStateUsing(fn (?array $state): string => (string) count($state ?? [])),
                TextColumn::make('reviewed_at')->label('Проверено')->dateTime()->toggleable(),
                TextColumn::make('published_at')->label('Добавлено в сайт')->dateTime()->toggleable(),
            ])
            ->filters([
                SelectFilter::make('status')->label('Статус')->options([
                    'ready_for_review' => 'Готово к проверке',
                    'invalid' => 'Ошибка валидации',
                    'duplicate' => 'Конфликт дубликата',
                    'excluded' => 'Исключено по реестру',
                    'reviewed' => 'Проверено',
                    'published' => 'Добавлено в сайт',
                    'staged_evidence' => 'Снимок Bitrix (без публикации)',
                ]),
                SelectFilter::make('import_run_id')->label('Прогон')->relationship('importRun', 'id'),
            ])
            ->recordActions([
                Action::make('review')
                    ->label('Подтвердить')
                    ->color('warning')
                    ->form([
                        Textarea::make('review_note')->label('Комментарий проверки')->maxLength(2000),
                    ])
                    ->visible(fn (StagedImportRecord $record): bool => $record->status === 'ready_for_review')
                    ->action(function (StagedImportRecord $record, array $data): void {
                        app(StagedProductPublisher::class)->review($record, auth()->user(), $data['review_note'] ?? null);
                    }),
                Action::make('publishToSite')
                    ->label('Добавить в регион')
                    ->color('success')
                    ->requiresConfirmation()
                    ->modalDescription('Товар будет создан или обновлён в общем каталоге и добавлен в выбранный сайт как черновик. На публичной витрине он не появится.')
                    ->form([
                        Select::make('site_id')
                            ->label('Сайт')
                            ->options(fn (): array => Site::query()->where('is_active', true)->orderBy('name')->pluck('name', 'id')->all())
                            ->required(),
                        Checkbox::make('confirmed')
                            ->label('Подтверждаю проверку данных и выбранный регион')
                            ->accepted()
                            ->required(),
                    ])
                    ->visible(fn (StagedImportRecord $record): bool => $record->status === 'reviewed')
                    ->action(function (StagedImportRecord $record, array $data): void {
                        $site = Site::query()->findOrFail($data['site_id']);
                        app(StagedProductPublisher::class)->publishToSite($record, $site, auth()->user());
                    }),
            ]);
    }

    public static function getPages(): array
    {
        return [
            'index' => ListStagedImportRecords::route('/'),
        ];
    }
}
