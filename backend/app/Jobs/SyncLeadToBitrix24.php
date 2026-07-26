<?php

namespace App\Jobs;

use App\Models\Lead;
use App\Models\SiteIntegration;
use Illuminate\Bus\Queueable;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Bus\Dispatchable;
use Illuminate\Queue\InteractsWithQueue;
use Illuminate\Queue\SerializesModels;
use Illuminate\Support\Facades\Http;
use Throwable;

class SyncLeadToBitrix24 implements ShouldQueue
{
    use Dispatchable, InteractsWithQueue, Queueable, SerializesModels;

    public int $tries = 3;

    public function __construct(public Lead $lead) {}

    public function handle(): void
    {
        $lead = $this->lead->fresh(['site.integrations']);
        if ($lead === null) {
            return;
        }

        $integration = $lead->site->integrations
            ->first(fn ($item) => $item->driver === 'bitrix24' && $item->is_enabled);
        $webhookUrl = data_get($integration?->settings, 'webhook_url');

        if (blank($webhookUrl)) {
            return;
        }

        if (! SiteIntegration::isValidBitrix24WebhookUrl($webhookUrl)) {
            $lead->update(['external_error' => 'Bitrix24 integration has an invalid webhook URL.']);

            return;
        }

        try {
            $response = Http::timeout(15)->post($webhookUrl, [
                'fields' => [
                    'TITLE' => "{$lead->type}: {$lead->company}",
                    'NAME' => $lead->contact_name,
                    'COMPANY_TITLE' => $lead->company,
                    'EMAIL' => $lead->email ? [['VALUE' => $lead->email, 'VALUE_TYPE' => 'WORK']] : [],
                    'PHONE' => $lead->phone ? [['VALUE' => $lead->phone, 'VALUE_TYPE' => 'WORK']] : [],
                    'COMMENTS' => $lead->message,
                    'UF_CRM_SITE_KEY' => $lead->site->key,
                    'UF_CRM_SITE_LOCALE' => $lead->locale,
                    'UF_CRM_PAGE_URL' => $lead->page_url,
                    'UF_CRM_UTM' => json_encode($lead->utm, JSON_UNESCAPED_UNICODE),
                    'UF_CRM_CART' => json_encode($lead->cart, JSON_UNESCAPED_UNICODE),
                ],
            ]);

            $response->throw();
            $lead->update(['external_id' => (string) ($response->json('result') ?? ''), 'external_error' => null]);
        } catch (Throwable $exception) {
            $lead->update(['external_error' => $exception->getMessage()]);
            throw $exception;
        }
    }
}
