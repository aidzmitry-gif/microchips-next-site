<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Jobs\SyncLeadToBitrix24;
use App\Models\Lead;
use App\Models\Site;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\Request;

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
            'utm' => ['nullable', 'array', 'max:30'],
        ]);

        $site = Site::query()
            ->where('key', $validated['site_key'])
            ->where('is_active', true)
            ->firstOrFail();

        unset($validated['site_key']);

        $lead = Lead::create([
            ...$validated,
            'site_id' => $site->id,
            'locale' => $validated['locale'] ?? $site->default_locale,
            'type' => $type,
            'status' => 'new',
        ]);

        SyncLeadToBitrix24::dispatch($lead);

        return response()->json(['id' => $lead->id, 'status' => 'accepted'], 201);
    }
}
