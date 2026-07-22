<?php

namespace App\Filament\Resources\ProductDescriptionDrafts;

use App\Domain\Content\ProductDescriptionDrafter;
use App\Filament\Resources\ProductDescriptionDrafts\Pages\ListProductDescriptionDrafts;
use App\Filament\Resources\ProductDescriptionDrafts\Pages\ViewProductDescriptionDraft;
use App\Models\ProductDescriptionDraft;
use Filament\Actions\Action;
use Filament\Actions\ViewAction;
use Filament\Infolists\Components\TextEntry;
use Filament\Resources\Resource;
use Filament\Schemas\Schema;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Filters\SelectFilter;
use Filament\Tables\Table;

class ProductDescriptionDraftResource extends Resource
{
    protected static ?string $model = ProductDescriptionDraft::class;

    protected static ?string $navigationLabel = 'Черновики описаний';

    protected static ?string $modelLabel = 'черновик описания';

    protected static ?string $pluralModelLabel = 'черновики описаний';

    protected static string|\UnitEnum|null $navigationGroup = 'Контент каталога';

    public static function infolist(Schema $schema): Schema
    {
        return $schema
            ->components([
                TextEntry::make('title')->label('Товар'),
                TextEntry::make('status')->label('Статус')->badge(),
                TextEntry::make('locale')->label('Локаль')->badge(),
                TextEntry::make('product.name')->label('Товар в общем каталоге')->placeholder('Не связан'),
                TextEntry::make('content')
                    ->label('Черновик текста')
                    ->placeholder('Текст не создан')
                    ->columnSpanFull(),
                TextEntry::make('rejection_reason')
                    ->label('Причина отклонения')
                    ->placeholder('Нет')
                    ->columnSpanFull(),
                TextEntry::make('verified_fields_display')
                    ->label('Подтверждённые поля')
                    ->state(function (ProductDescriptionDraft $record): string {
                        return json_encode(
                            $record->verified_fields ?? [],
                            JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES,
                        ) ?: '{}';
                    })
                    ->fontFamily('mono')
                    ->columnSpanFull(),
                TextEntry::make('source_urls_display')
                    ->label('Источники')
                    ->state(function (ProductDescriptionDraft $record): string {
                        return implode("\n", $record->source_urls ?? []);
                    })
                    ->markdown()
                    ->columnSpanFull(),
                TextEntry::make('submittedBy.email')->label('Передал на проверку')->placeholder('Не передано'),
                TextEntry::make('submitted_at')->label('Передано')->dateTime()->placeholder('—'),
            ])
            ->columns(2);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->defaultSort('id', 'desc')
            ->columns([
                TextColumn::make('title')->label('Товар')->searchable()->sortable()->limit(64),
                TextColumn::make('locale')->label('Локаль')->badge(),
                TextColumn::make('status')->label('Статус')->badge(),
                TextColumn::make('source_urls')
                    ->label('Источники')
                    ->formatStateUsing(function (mixed $state): string {
                        if (is_array($state)) {
                            return (string) count($state);
                        }

                        if (is_string($state)) {
                            $decoded = json_decode($state, true);

                            return is_array($decoded) ? (string) count($decoded) : '0';
                        }

                        return '0';
                    }),
                TextColumn::make('submitted_at')->label('Передано')->dateTime()->toggleable(),
                TextColumn::make('created_at')->label('Создано')->since(),
            ])
            ->filters([
                SelectFilter::make('status')->label('Статус')->options([
                    'draft' => 'Черновик',
                    'review' => 'На редакторской проверке',
                    'rejected' => 'Отклонён шлюзом',
                ]),
                SelectFilter::make('locale')->label('Локаль'),
            ])
            ->recordActions([
                ViewAction::make(),
                Action::make('submitForReview')
                    ->label('Передать на проверку')
                    ->color('warning')
                    ->requiresConfirmation()
                    ->visible(fn (ProductDescriptionDraft $record): bool => $record->status === 'draft')
                    ->action(function (ProductDescriptionDraft $record): void {
                        app(ProductDescriptionDrafter::class)->submitForReview($record, auth()->user());
                    }),
            ]);
    }

    public static function getPages(): array
    {
        return [
            'index' => ListProductDescriptionDrafts::route('/'),
            'view' => ViewProductDescriptionDraft::route('/{record}'),
        ];
    }
}
