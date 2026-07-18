#requires -Version 5.1
<#
.SYNOPSIS
    Конвертер RB import-манифеста -> staging-CSV бэкенда (catalog:stage-1c).

.DESCRIPTION
    Читает заполненный бизнесом RB import-манифест и выдаёт CSV ровно под контракт
    Laravel-команды `catalog:stage-1c` (App\Domain\Imports\StageProductValidator):

        external_id ; name ; sku ; mpn ; manufacturer ; voltage ; capacity ; chemistry ; slug

    Честность данных (жёсткое правило проекта):
      - external_id берётся ТОЛЬКО из бизнес-колонки supplier_or_1c_id. Legacy XML_ID
        Bitrix НЕ подставляется — это не стабильный 1С-ID.
      - sku/mpn берутся ТОЛЬКО из подтверждённых бизнес-колонок sku/mpn. Кандидаты
        (mpn_candidate_from_name / brand_candidate) в идентификаторы НЕ попадают.
      - voltage/capacity/chemistry берутся из *_from_name — это явный текст названия
        (правило №2 ТЗ), не декодированный код модели.
      - Цена/наличие НЕ выносятся: в схеме staging-валидатора их нет (отдельный трек).

    Экспортируются только строки с final_disposition = import, у которых заполнены
    external_id и хотя бы один идентификатор (sku|mpn). Остальные строки не выдумываются,
    а честно попадают в отчёт (excluded_by_disposition / not_ready).

    КОДИРОВКА ВЫХОДА: UTF-8 БЕЗ BOM. Это критично: Export-Csv в PS 5.1 пишет BOM и
    квотирует каждое поле, из-за чего PHP fgetcsv на стороне бэкенда получает первый
    заголовок как <BOM>"external_id" (кавычки не снимаются), normalizeHeader срезает
    только BOM, и external_id не распознаётся у 100% строк. Поэтому пишем собственным
    сериализатором без BOM (проверено эмпирически fgetcsv PHP 8.5).

.PARAMETER ManifestPath
    Путь к заполненному манифесту (CSV, разделитель запятая — формат генератора).
    По умолчанию — сгенерированный драфт в docs/audits/generated/.

.PARAMETER OutFile
    Куда писать staging-CSV. По умолчанию docs/audits/generated/rb-staging-1c.csv.

.PARAMETER Delimiter
    Разделитель выходного CSV. По умолчанию ';' (дефолт catalog:stage-1c).

.PARAMETER IncludeBrandCandidate
    Класть brand_candidate в колонку manufacturer. Выключено по умолчанию: бренд —
    неподтверждённый кандидат. Даже при включении бренд кладётся ТОЛЬКО если
    identity_extraction=auto_from_name и нет identity_collision.

.PARAMETER WhatIf
    Только посчитать и напечатать сводку, файл не писать.

.PARAMETER RunSelfTest
    Прогнать встроенный self-test на синтетических строках и выйти. Файл не читается.
#>
[CmdletBinding()]
param(
    [string]$ManifestPath,
    [string]$OutFile,
    [string]$Delimiter = ';',
    [switch]$IncludeBrandCandidate,
    [switch]$WhatIf,
    [switch]$RunSelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot   = Split-Path -Parent $scriptRoot

# Колонки манифеста, без которых конвертация бессмысленна (гейт схемы/разделителя).
$RequiredManifestColumns = @('name', 'final_disposition', 'supplier_or_1c_id', 'sku', 'mpn')

function Get-Field {
    param($Row, [string]$Name)
    # Безопасно достаёт колонку: нет свойства -> пусто; null -> пусто; whitespace -> пусто.
    if ($null -eq $Row) { return '' }
    $prop = $Row.PSObject.Properties[$Name]
    if ($null -eq $prop) { return '' }
    $value = $prop.Value
    if ($null -eq $value) { return '' }
    return ([string]$value).Trim()
}

function Convert-ManifestRows {
    <#
        Ядро. Принимает массив строк-манифеста (объекты со свойствами-колонками),
        возвращает объект с .Output (готовые staging-объекты) и .Report (счётчики+детали).
        И реальный прогон, и self-test зовут именно эту функцию.
    #>
    param(
        [object[]]$Rows,
        [bool]$IncludeBrand
    )

    $output   = New-Object System.Collections.Generic.List[object]
    $excluded = @{}   # disposition -> count
    $notReady = New-Object System.Collections.Generic.List[object]
    $approved = 0
    $pending  = 0

    foreach ($row in $Rows) {
        $disposition = (Get-Field $row 'final_disposition').ToLowerInvariant()

        if ($disposition -ne 'import') {
            $bucket = if ($disposition -eq '') { '(empty)' } else { $disposition }
            if ($excluded.ContainsKey($bucket)) { $excluded[$bucket]++ } else { $excluded[$bucket] = 1 }
            continue
        }

        $externalId = Get-Field $row 'supplier_or_1c_id'
        $name       = Get-Field $row 'name'
        $sku        = Get-Field $row 'sku'
        $mpn        = Get-Field $row 'mpn'

        $missing = New-Object System.Collections.Generic.List[string]
        if ($externalId -eq '') { $missing.Add('external_id (supplier_or_1c_id)') }
        if ($name -eq '')       { $missing.Add('name') }
        if ($sku -eq '' -and $mpn -eq '') { $missing.Add('sku|mpn') }

        if ($missing.Count -gt 0) {
            $notReady.Add([pscustomobject]@{
                name    = if ($name -eq '') { '(no name)' } else { $name }
                missing = ($missing -join ', ')
            })
            continue
        }

        $reviewStatus = (Get-Field $row 'review_status').ToLowerInvariant()
        if ($reviewStatus -eq 'approved') { $approved++ } else { $pending++ }

        # Бренд — только при явном флаге И только если извлечение авто-достоверно
        # и нет коллизии идентичности. Иначе колонка пуста (не показываем неподтверждённое).
        $manufacturer = ''
        if ($IncludeBrand) {
            $extraction = (Get-Field $row 'identity_extraction').ToLowerInvariant()
            $collision  = Get-Field $row 'identity_collision'
            if ($extraction -eq 'auto_from_name' -and $collision -eq '') {
                $manufacturer = Get-Field $row 'brand_candidate'
            }
        }

        $output.Add([pscustomobject][ordered]@{
            external_id  = $externalId
            name         = $name
            sku          = $sku
            mpn          = $mpn
            manufacturer = $manufacturer
            voltage      = Get-Field $row 'voltage_from_name'
            capacity     = Get-Field $row 'capacity_from_name'
            chemistry    = Get-Field $row 'technology_from_name'
            slug         = ''   # бэкенд транслитерирует из name сам
        })
    }

    return [pscustomobject]@{
        Output = $output
        Report = [pscustomobject]@{
            InputRows       = $Rows.Count
            Emitted         = $output.Count
            EmittedApproved = $approved
            EmittedPending  = $pending
            ExcludedByDisp  = $excluded
            NotReady        = $notReady
        }
    }
}

function ConvertTo-CsvText {
    <#
        Собственный CSV-сериализатор. Всегда квотирует каждое поле (внутренние кавычки
        удваиваются) — безопасно для значений с разделителем/кавычкой/переносом строки.
        Возвращает строку; запись в файл (без BOM) — отдельно, в Save-CsvText.
    #>
    param(
        [object[]]$Objects,
        [string]$Delim
    )
    if ($null -eq $Objects -or $Objects.Count -eq 0) { return '' }

    $columns = $Objects[0].PSObject.Properties.Name
    $sb = New-Object System.Text.StringBuilder

    $headerCells = foreach ($c in $columns) { '"' + ($c -replace '"', '""') + '"' }
    [void]$sb.Append(($headerCells -join $Delim)).Append("`r`n")

    foreach ($o in $Objects) {
        $cells = foreach ($c in $columns) {
            $v = [string]$o.$c
            '"' + ($v -replace '"', '""') + '"'
        }
        [void]$sb.Append(($cells -join $Delim)).Append("`r`n")
    }

    return $sb.ToString()
}

function Save-CsvText {
    # UTF-8 БЕЗ BOM — см. заголовочный комментарий про fgetcsv/normalizeHeader.
    param([string]$Text, [string]$Path)
    [System.IO.File]::WriteAllText($Path, $Text, [System.Text.UTF8Encoding]::new($false))
}

function Write-Summary {
    param($Report, [string]$OutPath, [bool]$Written)

    Write-Host ''
    Write-Host '=== RB staging-CSV: сводка ===' -ForegroundColor Cyan
    Write-Host ("  Строк на входе:        {0}" -f $Report.InputRows)
    Write-Host ("  Экспортировано:        {0}" -f $Report.Emitted) -ForegroundColor Green
    Write-Host ("    из них approved:     {0}" -f $Report.EmittedApproved)
    Write-Host ("    из них pending:      {0}" -f $Report.EmittedPending)

    if ($Report.ExcludedByDisp.Count -gt 0) {
        Write-Host '  Исключено по disposition:'
        foreach ($k in ($Report.ExcludedByDisp.Keys | Sort-Object)) {
            Write-Host ("    {0,-28} {1}" -f $k, $Report.ExcludedByDisp[$k])
        }
    }

    if ($Report.NotReady.Count -gt 0) {
        Write-Host ("  import, но не готовы:  {0}" -f $Report.NotReady.Count) -ForegroundColor Yellow
        $preview = $Report.NotReady | Select-Object -First 10
        foreach ($nr in $preview) {
            Write-Host ("    - {0}  [нет: {1}]" -f $nr.name, $nr.missing)
        }
        if ($Report.NotReady.Count -gt 10) {
            Write-Host ("    ... и ещё {0}" -f ($Report.NotReady.Count - 10))
        }
    }

    Write-Host ''
    if ($Written) {
        Write-Host ("Записано (UTF-8 без BOM): {0}" -f $OutPath) -ForegroundColor Green
    } else {
        Write-Host 'Файл не записан (WhatIf).' -ForegroundColor Yellow
    }
}

# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
function Invoke-SelfTest {
    Write-Host 'Self-test: конвертер манифест -> staging-CSV' -ForegroundColor Cyan

    $failures = New-Object System.Collections.Generic.List[string]
    function Assert-Eq { param($actual, $expected, $label)
        if ($actual -ne $expected) { $failures.Add("$label : ожидалось '$expected', получено '$actual'") }
    }

    # Синтетическая строка со всеми колонками, которые читает конвертер.
    $mk = {
        param([hashtable]$Overrides)
        $base = [ordered]@{
            name = ''; final_disposition = ''; supplier_or_1c_id = ''; sku = ''; mpn = ''
            voltage_from_name = ''; capacity_from_name = ''; technology_from_name = ''
            brand_candidate = ''; mpn_candidate_from_name = 'CAND-SHOULD-NOT-LEAK'
            review_status = ''; identity_extraction = ''; identity_collision = ''
        }
        foreach ($k in $Overrides.Keys) { $base[$k] = $Overrides[$k] }
        [pscustomobject]$base
    }

    $rows = @(
        & $mk @{ name = 'Full import row'; final_disposition = 'import'; supplier_or_1c_id = '1C-100'; sku = 'SKU-1'; mpn = 'MPN-1'; voltage_from_name = '12V'; capacity_from_name = '7Ah'; technology_from_name = 'AGM'; brand_candidate = 'BrandX'; review_status = 'approved'; identity_extraction = 'auto_from_name' }
        & $mk @{ name = 'Import only mpn'; final_disposition = 'import'; supplier_or_1c_id = '1C-101'; mpn = 'MPN-2'; brand_candidate = 'BrandY'; review_status = 'pending' }
        & $mk @{ name = 'Import no external'; final_disposition = 'import'; sku = 'SKU-3' }
        & $mk @{ name = 'Import no identifier'; final_disposition = 'import'; supplier_or_1c_id = '1C-103' }
        & $mk @{ name = 'Skip row'; final_disposition = 'skip'; supplier_or_1c_id = '1C-104'; sku = 'SKU-4' }
        & $mk @{ name = 'Merge row'; final_disposition = 'merge_into_series'; supplier_or_1c_id = '1C-105'; sku = 'SKU-5' }
        & $mk @{ name = 'No disposition'; supplier_or_1c_id = '1C-106'; sku = 'SKU-6' }
        & $mk @{ name = 'Brand collision'; final_disposition = 'import'; supplier_or_1c_id = '1C-107'; sku = 'SKU-7'; brand_candidate = 'BrandZ'; review_status = 'approved'; identity_extraction = 'auto_from_name'; identity_collision = 'shared_key_x2' }
    )

    # Прогон БЕЗ бренда (дефолт).
    $r = Convert-ManifestRows -Rows $rows -IncludeBrand $false

    Assert-Eq $r.Output.Count 3 'emitted count'
    Assert-Eq $r.Report.EmittedApproved 2 'approved count'
    Assert-Eq $r.Report.EmittedPending 1 'pending count'
    Assert-Eq $r.Report.NotReady.Count 2 'not_ready count (no external + no identifier)'
    Assert-Eq $r.Report.ExcludedByDisp['skip'] 1 'excluded skip'
    Assert-Eq $r.Report.ExcludedByDisp['merge_into_series'] 1 'excluded merge'
    Assert-Eq $r.Report.ExcludedByDisp['(empty)'] 1 'excluded empty disposition'

    $first = $r.Output[0]
    Assert-Eq $first.external_id '1C-100' 'external_id maps from supplier_or_1c_id'
    Assert-Eq $first.sku 'SKU-1' 'sku maps'
    Assert-Eq $first.mpn 'MPN-1' 'mpn maps'
    Assert-Eq $first.voltage '12V' 'voltage from name'
    Assert-Eq $first.chemistry 'AGM' 'chemistry from technology_from_name'
    Assert-Eq $first.manufacturer '' 'manufacturer empty when brand candidate excluded'
    Assert-Eq $first.slug '' 'slug empty (backend derives)'

    # Кандидат mpn НЕ должен утечь ни в один идентификатор.
    foreach ($o in $r.Output) {
        if ($o.mpn -eq 'CAND-SHOULD-NOT-LEAK' -or $o.sku -eq 'CAND-SHOULD-NOT-LEAK') {
            $failures.Add('mpn_candidate_from_name leaked into an identifier column')
        }
    }

    # Прогон С брендом: авто-достоверный бренд кладётся, а коллизийный — нет.
    $rb = Convert-ManifestRows -Rows $rows -IncludeBrand $true
    Assert-Eq $rb.Output[0].manufacturer 'BrandX' 'brand mapped when auto_from_name and no collision'
    Assert-Eq $rb.Output[2].manufacturer '' 'brand suppressed on identity_collision'
    Assert-Eq $rb.Output[1].manufacturer '' 'brand suppressed when extraction not auto_from_name'

    # Сериализация: файл должен быть БЕЗ BOM, первый заголовок квотирован ("external_id").
    # Это ловит регрессию, из-за которой fgetcsv на бэкенде не распознавал external_id.
    $csv = ConvertTo-CsvText -Objects $r.Output -Delim ';'
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ('rb-staging-selftest-{0}.csv' -f $PID)
    try {
        Save-CsvText -Text $csv -Path $tmp
        $bytes = [System.IO.File]::ReadAllBytes($tmp)
        if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
            $failures.Add('output CSV starts with UTF-8 BOM (breaks backend external_id parsing)')
        }
        $firstLine = ($csv -split "`r`n")[0]
        if (-not $firstLine.StartsWith('"external_id"')) {
            $failures.Add("first header cell is not the quoted external_id: [$firstLine]")
        }
    } finally {
        if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force }
    }

    if ($failures.Count -eq 0) {
        Write-Host 'SELF-TEST OK: все проверки пройдены.' -ForegroundColor Green
        return 0
    }

    Write-Host ("SELF-TEST FAILED: {0}" -f $failures.Count) -ForegroundColor Red
    foreach ($f in $failures) { Write-Host ("  - {0}" -f $f) -ForegroundColor Red }
    return 1
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if ($RunSelfTest) {
    exit (Invoke-SelfTest)
}

if ([string]::IsNullOrWhiteSpace($ManifestPath)) {
    $ManifestPath = Join-Path $repoRoot 'docs/audits/generated/rb-import-manifest-draft.csv'
}
if ([string]::IsNullOrWhiteSpace($OutFile)) {
    $OutFile = Join-Path $repoRoot 'docs/audits/generated/rb-staging-1c.csv'
}

if (-not (Test-Path -LiteralPath $ManifestPath)) {
    Write-Error ("Манифест не найден: {0}`nСгенерируйте его: .\scripts\build-rb-import-manifest.ps1" -f $ManifestPath) -ErrorAction Continue
    exit 1
}

$rows = @(Import-Csv -LiteralPath $ManifestPath)

# Гейт схемы/разделителя: манифест бизнес-редактируемый; если его пересохранили в Excel
# с другим list-разделителем, Import-Csv схлопнет всё в одну колонку. Ловим это явно,
# чтобы не выдать молчаливые «0 строк».
if ($rows.Count -gt 0) {
    $presentColumns = $rows[0].PSObject.Properties.Name
    $missingColumns = @($RequiredManifestColumns | Where-Object { $presentColumns -notcontains $_ })
    if ($missingColumns.Count -gt 0) {
        Write-Error (
            "В манифесте нет обязательных колонок: {0}.`n" -f ($missingColumns -join ', ') +
            "Похоже, сбит разделитель/схема CSV (ожидается запятая, как у генератора). " +
            "Проверьте, не пересохранён ли файл в Excel с другим list-разделителем."
        ) -ErrorAction Continue
        exit 1
    }
}

$result = Convert-ManifestRows -Rows $rows -IncludeBrand ([bool]$IncludeBrandCandidate)

$written = $false
if (-not $WhatIf) {
    $outDir = Split-Path -Parent $OutFile
    if (-not (Test-Path -LiteralPath $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }

    if ($result.Output.Count -eq 0) {
        Write-Host 'Нечего экспортировать: 0 готовых строк. Файл не записан.' -ForegroundColor Yellow
    } else {
        $csv = ConvertTo-CsvText -Objects $result.Output -Delim $Delimiter
        Save-CsvText -Text $csv -Path $OutFile
        $written = $true
    }
}

Write-Summary -Report $result.Report -OutPath $OutFile -Written $written
