<?php

namespace App\Http\Controllers\Api\V1;

use App\Http\Controllers\Controller;
use App\Models\ProductMedia;
use Illuminate\Support\Facades\Storage;

class ProductMediaController extends Controller
{
    public function __invoke(int $media): mixed
    {
        $record = ProductMedia::query()->previewReady()->findOrFail($media);
        if ($record->storage_path === null || ! Storage::disk('public')->exists($record->storage_path)) {
            abort(404);
        }

        $verified = $record->verification_status === ProductMedia::STATUS_VERIFIED;

        return Storage::disk('public')->response($record->storage_path, null, [
            'Cache-Control' => $verified ? 'public, max-age=31536000, immutable' : 'private, no-store, max-age=0',
            'Content-Disposition' => 'inline',
            'X-Robots-Tag' => $verified ? 'index, follow' : 'noindex, noarchive',
        ]);
    }
}
