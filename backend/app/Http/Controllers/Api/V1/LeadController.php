<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Jobs\SyncLeadToBitrix24;
use App\Models\Lead;
use App\Models\Site;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;
use Illuminate\Validation\ValidationException;

class LeadController extends Controller
{
    public function quote(Request $request): JsonResponse
    {
        return $this->store($request, 'quote');
    }

    public function batteryPackDesign(Request $request): JsonResponse
    {
        return $this->store($request, 'battery_pack_design');
    }

    private function store(Request $request, string $type): JsonResponse
    {
        $validated = $request->validate([
            'site_key' => ['required', 'string', 'max:64'],
            'locale' => ['nullable', 'string', 'max:10'],
            'company' => ['required', 'string', 'max:255'],
            'contact_name' => ['required', 'string', 'max:255'],
            'email' => ['nullable', 'email', 'required_without:phone', 'max:255'],
            'phone' => ['nullable', 'string', 'required_without:email', 'max:50'],
            'message' => ['nullable', 'string', 'max:5000'],
            'page_url' => ['required', 'url', 'max:2048'],
            'cart' => ['nullable', 'array', 'max:100'],
            'cart.*' => ['array:external_id,variant_key,name,sku,quantity,attributes'],
            'cart.*.external_id' => ['nullable', 'string', 'max:255'],
            'cart.*.variant_key' => ['nullable', 'string', 'max:255'],
            'cart.*.name' => ['nullable', 'string', 'max:500'],
            'cart.*.sku' => ['nullable', 'string', 'max:255'],
            'cart.*.quantity' => ['required', 'integer', 'min:1', 'max:100000'],
            'cart.*.attributes' => ['nullable', 'array', 'max:50'],
            'cart.*.attributes.*' => ['string', 'max:500'],
            'utm' => ['nullable', 'array', 'max:30'],
        ]);

        foreach ($validated['cart'] ?? [] as $index => $line) {
            if (blank($line['external_id'] ?? null) && blank($line['sku'] ?? null) && blank($line['name'] ?? null)) {
                throw ValidationException::withMessages([
                    "cart.{$index}" => ['Each cart line requires an external_id, sku or name.'],
                ]);
            }
        }

        $site = Site::query()
            ->where('key', $validated['site_key'])
            ->where('is_active', true)
            ->firstOrFail();

        $pageHost = $this->normalizedHost($validated['page_url']);
        if ($pageHost === null || ! hash_equals($site->domain, $pageHost)) {
            throw ValidationException::withMessages([
                'page_url' => ['The page URL must belong to the selected site.'],
            ]);
        }

        $locale = $validated['locale'] ?? $site->default_locale;
        if ($locale !== $site->default_locale && ! $site->locales()->where('locale', $locale)->where('is_enabled', true)->exists()) {
            throw ValidationException::withMessages([
                'locale' => ['The locale is not enabled for the selected site.'],
            ]);
        }

        unset($validated['site_key']);

        $lead = Lead::create([
            ...$validated,
            'site_id' => $site->id,
            'locale' => $locale,
            'type' => $type,
            'status' => 'new',
        ]);

        // Local inbox is the default operating mode. A CRM job is created
        // only after an operator explicitly enables that integration for the
        // current site, so an absent Bitrix24 account cannot manufacture
        // retries or false external errors for an otherwise accepted lead.
        if ($site->integrations()->where('driver', 'bitrix24')->where('is_enabled', true)->exists()) {
            SyncLeadToBitrix24::dispatch($lead);
        }

        return response()->json(['id' => $lead->id, 'status' => 'accepted'], 201);
    }

    private function normalizedHost(string $url): ?string
    {
        $host = parse_url($url, PHP_URL_HOST);
        if (! is_string($host) || $host === '') {
            return null;
        }

        return preg_replace('/^www\./', '', strtolower($host));
    }
}
