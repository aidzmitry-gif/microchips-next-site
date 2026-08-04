<?php

namespace App\Filament\Resources\Leads;

use App\Filament\Resources\Leads\Pages\ListLeads;
use App\Filament\Resources\Leads\Pages\ViewLead;
use App\Models\Lead;
use App\Models\User;
use Filament\Actions\Action;
use Filament\Actions\ViewAction;
use Filament\Forms\Components\Textarea;
use Filament\Infolists\Components\TextEntry;
use Filament\Resources\Resource;
use Filament\Schemas\Schema;
use Filament\Tables\Columns\IconColumn;
use Filament\Tables\Columns\TextColumn;
use Filament\Tables\Filters\SelectFilter;
use Filament\Tables\Table;

/**
 * Customer facts remain read-only. The only mutation is an explicit local
 * inbox lifecycle, used when no external CRM is configured.
 */
class LeadResource extends Resource
{
    protected static ?string $model = Lead::class;

    protected static ?string $navigationLabel = 'Заявки';

    protected static ?string $modelLabel = 'заявка';

    protected static ?string $pluralModelLabel = 'заявки';

    protected static string|\UnitEnum|null $navigationGroup = 'CRM';

    public static function infolist(Schema $schema): Schema
    {
        return $schema->components([
            TextEntry::make('site.name')->label('Сайт'),
            TextEntry::make('locale')->label('Локаль')->badge(),
            TextEntry::make('type')->label('Тип')->badge(),
            TextEntry::make('status')->label('Статус')->badge(),
            TextEntry::make('company')->label('Компания'),
            TextEntry::make('contact_name')->label('Контакт'),
            TextEntry::make('email')->label('E-mail')->placeholder('—'),
            TextEntry::make('phone')->label('Телефон')->placeholder('—'),
            TextEntry::make('page_url')->label('Страница')->url(fn (Lead $record): string => $record->page_url)->openUrlInNewTab()->columnSpanFull(),
            TextEntry::make('message')->label('Сообщение')->placeholder('—')->columnSpanFull(),
            TextEntry::make('external_id')->label('Bitrix24 ID')->placeholder('Не передан'),
            TextEntry::make('external_error')->label('Ошибка CRM')->placeholder('Нет')->columnSpanFull(),
            TextEntry::make('handledBy.name')->label('Ответственный')->placeholder('Не назначен'),
            TextEntry::make('handled_at')->label('Взята в работу')->dateTime()->placeholder('—'),
            TextEntry::make('internal_note')->label('Внутренняя заметка')->placeholder('Нет')->columnSpanFull(),
            TextEntry::make('utm')->label('UTM')->state(fn (Lead $record): string => self::json($record->utm))->fontFamily('mono')->columnSpanFull(),
            TextEntry::make('cart')->label('Состав запроса')->state(fn (Lead $record): string => self::json($record->cart))->fontFamily('mono')->columnSpanFull(),
            TextEntry::make('created_at')->label('Получена')->dateTime(),
            TextEntry::make('updated_at')->label('Обновлена')->dateTime(),
        ])->columns(2);
    }

    public static function table(Table $table): Table
    {
        return $table
            ->defaultSort('id', 'desc')
            ->columns([
                TextColumn::make('id')->label('ID')->sortable(),
                TextColumn::make('site.name')->label('Сайт')->searchable(),
                TextColumn::make('type')->label('Тип')->badge(),
                TextColumn::make('company')->label('Компания')->searchable()->limit(35),
                TextColumn::make('contact_name')->label('Контакт')->searchable()->limit(35),
                TextColumn::make('locale')->label('Локаль')->badge(),
                TextColumn::make('external_id')->label('Bitrix24 ID')->placeholder('—'),
                IconColumn::make('external_error')->label('Ошибка CRM')->boolean()->state(fn (Lead $record): bool => filled($record->external_error)),
                TextColumn::make('handledBy.name')->label('Ответственный')->placeholder('—')->toggleable(),
                TextColumn::make('created_at')->label('Получена')->dateTime()->sortable(),
            ])
            ->filters([
                SelectFilter::make('site_id')->label('Сайт')->relationship('site', 'name'),
                SelectFilter::make('type')->label('Тип')->options(['quote' => 'Запрос КП', 'battery_pack_design' => 'Проектирование АКБ']),
                SelectFilter::make('status')->label('Статус')->options([
                    'new' => 'Новая', 'in_progress' => 'В работе', 'closed' => 'Закрыта', 'rejected' => 'Отклонена',
                ]),
            ])
            ->recordActions([
                ViewAction::make(),
                Action::make('startProcessing')
                    ->label('Взять в работу')
                    ->color('warning')
                    ->visible(fn (Lead $record): bool => $record->status === 'new')
                    ->form([Textarea::make('internal_note')->label('Заметка оператору')->maxLength(5000)])
                    ->action(function (Lead $record, array $data): void {
                        $operator = auth()->user();
                        if (! $operator instanceof User) {
                            abort(403);
                        }
                        $record->startProcessing($operator, $data['internal_note'] ?? null);
                    }),
                Action::make('closeLead')
                    ->label('Закрыть заявку')
                    ->color('success')
                    ->visible(fn (Lead $record): bool => in_array($record->status, ['new', 'in_progress'], true))
                    ->form([Textarea::make('internal_note')->label('Итог обработки')->required()->maxLength(5000)])
                    ->action(function (Lead $record, array $data): void {
                        $operator = auth()->user();
                        if (! $operator instanceof User) {
                            abort(403);
                        }
                        $record->close($operator, $data['internal_note']);
                    }),
            ]);
    }

    public static function getPages(): array
    {
        return [
            'index' => ListLeads::route('/'),
            'view' => ViewLead::route('/{record}'),
        ];
    }

    /** @param array<mixed>|null $value */
    private static function json(?array $value): string
    {
        return json_encode($value ?? [], JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES) ?: '{}';
    }
}
