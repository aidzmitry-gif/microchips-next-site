# Контур качества

`scripts/quality-gate.ps1` — единая обязательная проверка перед коммитом и та же последовательность, которую выполняет GitHub Actions. Она не запускает контейнеры, не обращается к production и не меняет исходный код.

Проверяются строго в таком порядке:

1. состав PHP-расширений;
2. синтаксис всех PHP-файлов приложения вне `vendor`;
3. Laravel Pint в режиме `--test`;
4. PHPUnit с SQLite в памяти;
5. production-сборка Next.js;
6. `docker compose config --quiet` с безопасным `.env.example`.

## Локальный запуск

Сначала один раз установите зависимости из зафиксированных lockfile:

```powershell
Set-Location backend
composer install
Set-Location ..
pnpm install --frozen-lockfile
./scripts/quality-gate.ps1
```

Если `php`, `pnpm` или `docker` не находятся в `PATH`, передайте полный путь через переменную окружения:

```powershell
$env:PHP_BIN = 'C:\\php\\php.exe'
$env:PNPM_BIN = 'C:\\Users\\name\\AppData\\Roaming\\npm\\pnpm.cmd'
$env:DOCKER_BIN = 'C:\\Program Files\\Docker\\Docker\\resources\\bin\\docker.exe'
./scripts/quality-gate.ps1
```

На Windows PHP должен быть настроен через `php.ini`. Обязательные расширения: `ctype`, `curl`, `dom`, `fileinfo`, `intl`, `mbstring`, `openssl`, `pdo_pgsql`, `pgsql`, `pdo_sqlite`, `sqlite3`, `tokenizer`, `xml`, `xmlwriter`, `zip`.

Если используется переносимая PHP-сборка без `php.ini`, можно передать параметры загрузки расширений явно:

```powershell
$phpRoot = 'C:\\php'
$phpFlags = @(
  '-n',
  '-d', "extension_dir=$phpRoot\\ext",
  '-d', 'extension=php_openssl.dll',
  '-d', 'extension=php_curl.dll',
  '-d', 'extension=php_mbstring.dll',
  '-d', 'extension=php_fileinfo.dll',
  '-d', 'extension=php_zip.dll',
  '-d', 'extension=php_intl.dll',
  '-d', 'extension=php_pdo_pgsql.dll',
  '-d', 'extension=php_pgsql.dll',
  '-d', 'extension=php_pdo_sqlite.dll',
  '-d', 'extension=php_sqlite3.dll'
)
./scripts/quality-gate.ps1 -PhpPath "$phpRoot\\php.exe" -PhpArguments $phpFlags
```

`pcntl` и `posix` нужны Horizon внутри Linux-контейнера, но не требуются для Windows CLI и этого quality gate.

## CI

Workflow [quality.yml](../.github/workflows/quality.yml) запускается для `push`, pull request и вручную. Внешние Actions зафиксированы полными SHA, а PHP, Node.js и pnpm — точными версиями. CI использует `composer.lock` и `pnpm-lock.yaml`; изменение зависимостей без изменения соответствующего lockfile не допускается.

Проверка Compose валидирует итоговую конфигурацию, но не делает `docker compose up`, не скачивает образы и не требует работающего Docker daemon.
