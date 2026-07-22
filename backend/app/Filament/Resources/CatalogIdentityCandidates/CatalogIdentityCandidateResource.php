<?php

namespace App\Filament\Resources\CatalogIdentityCandidates;

use App\Domain\Imports\IdentityCandidateReviewer;
use App\Filament\Resources\CatalogIdentityCandidates\Pages\ListCatalogIdentityCandidates;
use App\Models\CatalogIdentityCandidate;
use Filament\Actions\Action;
use Filament\Forms\Components\Textarea;
use Filament\Forms\Components\TextInput;
use Filament\Resources\Resource;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Filters\SelectFilter;
use Filament\Tables\Table;

class CatalogIdentityCandidateResource extends Resource
{
    protected static ?string $model = CatalogIdentityCandidate::class;

    protected static ?string $navigationLabel = 'Сверка Bitrix и 1С';

    protected static ?string $modelLabel = 'кандидат идентичности';

    protected static ?string $pluralModelLabel = 'кандидаты идентичности';

    protected static string|\UnitEnum|null $navigationGroup = 'Импорт каталога';

    public static function table(Table $table): Table
    {
        return $table
            ->defaultSort('review_priority')
            ->columns([
                TextColumn::make('review_priority')->label('№')->sortable(),
                TextColumn::make('review_batch')->label('Пакет')->badge()->sortable(),
                TextColumn::make('legacy_name')->label('Название Bitrix')->searchable()->wrap(),
                TextColumn::make('oneCItem.external_id')->label('Код 1С')->searchable(),
                TextColumn::make('oneCItem.article')->label('Артикул из 1С')->searchable()->placeholder('нет'),
                TextColumn::make('oneCItem.name')->label('Название 1С')->searchable()->wrap(),
                TextColumn::make('confidence')->label('Уверенность')->numeric(decimalPlaces: 2),
                TextColumn::make('comparison_status')->label('Сравнение')->toggleable(),
                TextColumn::make('review_status')->label('Статус')->badge(),
            ])
            ->filters([
                SelectFilter::make('review_batch')->label('Пакет')->options([
                    'rb-initial-50' => 'Первые 50',
                    'rb-backlog' => 'Остальные кандидаты',
                ]),
                SelectFilter::make('review_status')->label('Статус')->options([
                    'pending' => 'Ожидает проверки',
                    'approved_for_staging' => 'Разрешён к staging',
                    'rejected' => 'Отклонён',
                ]),
            ])
            ->recordActions([
                Action::make('approveIdentity')
                    ->label('Подтвердить идентичность')
                    ->color('success')
                    ->form([
                        TextInput::make('confirmed_sku')->label('Подтверждённый SKU')->maxLength(255),
                        TextInput::make('confirmed_mpn')->label('Подтверждённый MPN')->maxLength(255),
                        TextInput::make('confirmed_manufacturer')->label('Производитель')->maxLength(255),
                        TextInput::make('confirmed_category')->label('Категория')->maxLength(255),
                        Textarea::make('review_note')->label('Комментарий')->maxLength(2000),
                    ])
                    ->visible(fn (CatalogIdentityCandidate $record): bool => $record->review_status === 'pending')
                    ->action(function (CatalogIdentityCandidate $record, array $data): void {
                        app(IdentityCandidateReviewer::class)->approve($record, auth()->user(), $data);
                    }),
                Action::make('rejectIdentity')
                    ->label('Отклонить')
                    ->color('danger')
                    ->form([
                        Textarea::make('review_note')
                            ->label('Причина отклонения')
                            ->required()
                            ->maxLength(2000),
                    ])
                    ->visible(fn (CatalogIdentityCandidate $record): bool => $record->review_status === 'pending')
                    ->action(function (CatalogIdentityCandidate $record, array $data): void {
                        app(IdentityCandidateReviewer::class)->reject($record, auth()->user(), $data['review_note']);
                    }),
            ]);
    }

    public static function getPages(): array
    {
        return [
            'index' => ListCatalogIdentityCandidates::route('/'),
        ];
    }
}
