FROM composer:2.10.2 AS dependencies

WORKDIR /app
COPY composer.json composer.lock ./
# Платформенные расширения (intl, pcntl) есть в рантайм-образе `app`, но не в
# build-образе composer — здесь только резолвим/ставим пакеты, поэтому проверку
# платформы для них пропускаем (иначе composer install падает с exit 2).
RUN composer install --no-dev --no-scripts --no-interaction --prefer-dist --optimize-autoloader \
    --ignore-platform-req=ext-intl --ignore-platform-req=ext-pcntl

COPY . .
# --no-scripts: не запускать artisan package:discover в build-образе composer (нет
# расширений/записываемого bootstrap/cache — падает «valid cache path»). Discovery
# выполнит рантайм-образ app на первом старте.
RUN composer dump-autoload --no-dev --classmap-authoritative --no-scripts

FROM php:8.5.8-fpm-alpine AS app

# Рантайм-либы: libpq (pgsql), icu-libs (intl). Заголовки (libpq-dev, icu-dev)
# нужны только на время компиляции расширений — ставим во временный .build-deps.
# opcache НЕ ставим через ext-install: в этом php-образе он уже статически
# вкомпилирован (см. `php -m` → Zend OPcache), а install падает «can't stat modules/*».
RUN apk add --no-cache libpq icu-libs \
    && apk add --no-cache --virtual .build-deps libpq-dev icu-dev \
    && docker-php-ext-install pdo_pgsql pcntl intl \
    && apk del .build-deps

# phpredis: очередь и кэш работают через Redis (QUEUE_CONNECTION/CACHE_STORE=redis),
# Horizon без него падает «PHP Redis extension is not installed». PECL-сборке нужны
# временные phpize-зависимости; yes '' отвечает дефолтами на промпты сериализаторов.
RUN apk add --no-cache --virtual .phpize-deps $PHPIZE_DEPS \
    && yes '' | pecl install redis \
    && docker-php-ext-enable redis \
    && apk del .phpize-deps

WORKDIR /var/www
COPY --from=dependencies /app /var/www
# storage/framework/* и logs исключены из контекста (.dockerignore), поэтому
# создаём рантайм-каталоги здесь — иначе Laravel падает «valid cache path».
RUN mkdir -p storage/framework/cache/data storage/framework/sessions \
        storage/framework/views storage/logs bootstrap/cache \
    && chown -R www-data:www-data storage bootstrap/cache

USER www-data
EXPOSE 9000
CMD ["php-fpm"]
