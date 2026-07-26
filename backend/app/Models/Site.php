<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Site extends Model
{
    protected $fillable = [
        'key', 'domain', 'country_code', 'currency_code', 'default_locale', 'name',
        'legal_name', 'legal_address', 'phone', 'email', 'delivery_terms', 'payment_terms', 'is_active',
    ];

    protected function casts(): array
    {
        return ['is_active' => 'boolean'];
    }

    public function locales(): HasMany
    {
        return $this->hasMany(SiteLocale::class);
    }

    public function products(): HasMany
    {
        return $this->hasMany(SiteProduct::class);
    }

    public function pages(): HasMany
    {
        return $this->hasMany(SitePage::class);
    }

    public function contacts(): HasMany
    {
        return $this->hasMany(SiteContact::class);
    }

    public function commercialFacts(): HasMany
    {
        return $this->hasMany(SiteCommercialFact::class);
    }

    public function urls(): HasMany
    {
        return $this->hasMany(SiteUrl::class);
    }

    public function redirects(): HasMany
    {
        return $this->hasMany(SiteRedirect::class);
    }

    public function integrations(): HasMany
    {
        return $this->hasMany(SiteIntegration::class);
    }
}
