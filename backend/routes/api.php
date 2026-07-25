<?php

use App\Http\Controllers\Api\V1\CatalogController;
use App\Http\Controllers\Api\V1\LeadController;
use App\Http\Controllers\Api\V1\ResolveSitePathController;
use App\Http\Controllers\Api\V1\ResolveSiteRedirectController;
use App\Http\Controllers\Api\V1\SitemapController;
use Illuminate\Support\Facades\Route;

Route::get('/sites/{host}/resolve', ResolveSitePathController::class);
Route::get('/sites/{host}/redirect', ResolveSiteRedirectController::class);
Route::get('/sites/{site}/catalog/products', [CatalogController::class, 'index']);
Route::get('/sites/{site}/catalog/categories', [CatalogController::class, 'categories']);
Route::get('/sites/{host}/seo/sitemap', SitemapController::class);

Route::post('/leads/quote', [LeadController::class, 'quote'])->middleware('throttle:leads');
Route::post('/leads/battery-pack-design', [LeadController::class, 'batteryPackDesign'])->middleware('throttle:leads');
