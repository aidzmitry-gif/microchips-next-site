<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Validation\ValidationException;

class SiteIntegration extends Model
{
    protected $fillable = ['site_id', 'driver', 'settings', 'is_enabled'];

    protected function casts(): array
    {
        return ['settings' => 'array', 'is_enabled' => 'boolean'];
    }

    public function site(): BelongsTo
    {
        return $this->belongsTo(Site::class);
    }

    public static function isValidBitrix24WebhookUrl(mixed $url): bool
    {
        if (! is_string($url) || filter_var($url, FILTER_VALIDATE_URL) === false) {
            return false;
        }

        $parts = parse_url($url);
        if ($parts === false) {
            return false;
        }
        $host = strtolower((string) ($parts['host'] ?? ''));
        $path = (string) ($parts['path'] ?? '');

        return ($parts['scheme'] ?? null) === 'https'
            && ! isset($parts['user'], $parts['pass'], $parts['port'], $parts['query'], $parts['fragment'])
            && preg_match('/^[a-z0-9-]+\.bitrix24\.[a-z]{2,}$/', $host) === 1
            && preg_match('#^/rest/[A-Za-z0-9/_.-]+\.json$#', $path) === 1;
    }

    protected static function booted(): void
    {
        static::saving(function (self $integration): void {
            if ($integration->driver === 'bitrix24' && $integration->is_enabled && ! self::isValidBitrix24WebhookUrl(data_get($integration->settings, 'webhook_url'))) {
                throw ValidationException::withMessages([
                    'settings.webhook_url' => 'An enabled Bitrix24 integration requires an HTTPS cloud webhook URL ending in /rest/...json.',
                ]);
            }
        });
    }
}
