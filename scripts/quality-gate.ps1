[CmdletBinding()]
param(
    [string] $PhpPath = $env:PHP_BIN,
    [string[]] $PhpArguments = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Resolve-Executable {
    param(
        [Parameter(Mandatory)]
        [AllowEmptyString()]
        [string] $ConfiguredPath,
        [Parameter(Mandatory)]
        [string] $CommandName,
        [Parameter(Mandatory)]
        [string] $EnvironmentVariable
    )

    if ($ConfiguredPath) {
        if (-not (Test-Path -LiteralPath $ConfiguredPath)) {
            throw "$EnvironmentVariable points to a missing file: $ConfiguredPath"
        }

        return (Resolve-Path -LiteralPath $ConfiguredPath).Path
    }

    $command = Get-Command $CommandName -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "'$CommandName' was not found. Add it to PATH or set $EnvironmentVariable to its full path."
    }

    return $command.Source
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory)]
        [string] $Name,
        [Parameter(Mandatory)]
        [scriptblock] $Command
    )

    Write-Host "`n==> $Name" -ForegroundColor Cyan
    & $Command

    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}

$php = Resolve-Executable -ConfiguredPath $PhpPath -CommandName 'php' -EnvironmentVariable 'PHP_BIN'
$pnpm = Resolve-Executable -ConfiguredPath $env:PNPM_BIN -CommandName 'pnpm' -EnvironmentVariable 'PNPM_BIN'
$docker = Resolve-Executable -ConfiguredPath $env:DOCKER_BIN -CommandName 'docker' -EnvironmentVariable 'DOCKER_BIN'

$requiredExtensions = @(
    'ctype', 'curl', 'dom', 'fileinfo', 'intl', 'mbstring', 'openssl',
    'pdo_pgsql', 'pgsql', 'pdo_sqlite', 'sqlite3', 'tokenizer', 'xml', 'xmlwriter', 'zip'
)

Invoke-CheckedCommand -Name 'Check PHP extensions' -Command {
    $loadedExtensions = @(& $php @PhpArguments -m | ForEach-Object { $_.Trim().ToLowerInvariant() })
    $missingExtensions = $requiredExtensions | Where-Object { $_ -notin $loadedExtensions }

    if ($missingExtensions) {
        throw "PHP is missing required extensions: $($missingExtensions -join ', '). See docs/quality-gate.md."
    }
}

$phpFiles = Get-ChildItem -Path (Join-Path $projectRoot 'backend') -Recurse -File -Filter '*.php' |
    Where-Object { $_.FullName -notmatch '[\\/]vendor[\\/]' }

Invoke-CheckedCommand -Name 'PHP syntax lint' -Command {
    foreach ($phpFile in $phpFiles) {
        & $php @PhpArguments -l $phpFile.FullName
        if ($LASTEXITCODE -ne 0) {
            throw "PHP syntax lint failed for $($phpFile.FullName)."
        }
    }
}

$pint = Join-Path $projectRoot 'backend/vendor/bin/pint'
$phpunit = Join-Path $projectRoot 'backend/vendor/bin/phpunit'

if (-not (Test-Path -LiteralPath $pint) -or -not (Test-Path -LiteralPath $phpunit)) {
    throw 'PHP dependencies are absent. Run "composer install" in backend first.'
}

Invoke-CheckedCommand -Name 'Laravel Pint (check mode)' -Command {
    Push-Location (Join-Path $projectRoot 'backend')
    try {
        & $php @PhpArguments $pint --test
    }
    finally {
        Pop-Location
    }
}

Invoke-CheckedCommand -Name 'PHPUnit' -Command {
    Push-Location (Join-Path $projectRoot 'backend')
    try {
        & $php @PhpArguments $phpunit
    }
    finally {
        Pop-Location
    }
}

Invoke-CheckedCommand -Name 'Next.js production build' -Command {
    Push-Location $projectRoot
    try {
        & $pnpm --filter frontend build
    }
    finally {
        Pop-Location
    }
}

Invoke-CheckedCommand -Name 'Docker Compose configuration' -Command {
    Push-Location $projectRoot
    try {
        & $docker compose --env-file .env.example -f docker-compose.yml config --quiet
    }
    finally {
        Pop-Location
    }
}

Write-Host "`nQuality gate passed." -ForegroundColor Green
