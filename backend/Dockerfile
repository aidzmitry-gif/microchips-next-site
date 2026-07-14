FROM composer:2.10.2 AS dependencies

WORKDIR /app
COPY composer.json composer.lock ./
RUN composer install --no-dev --no-scripts --no-interaction --prefer-dist --optimize-autoloader

COPY . .
RUN composer dump-autoload --no-dev --classmap-authoritative

FROM php:8.5.8-fpm-alpine AS app

RUN apk add --no-cache libpq \
    && docker-php-ext-install pdo_pgsql pcntl opcache

WORKDIR /var/www
COPY --from=dependencies /app /var/www
RUN chown -R www-data:www-data storage bootstrap/cache

USER www-data
EXPOSE 9000
CMD ["php-fpm"]
