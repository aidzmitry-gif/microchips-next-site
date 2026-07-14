[CmdletBinding()]
param(
    [string]$Path = (Join-Path $PSScriptRoot '..\docs\prototypes\rb-b2b-catalog.html')
)

$ErrorActionPreference = 'Stop'
$resolvedPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
$leadControllerPath = Join-Path $PSScriptRoot '..\backend\app\Http\Controllers\Api\V1\LeadController.php'

if (-not (Test-Path -LiteralPath $resolvedPath -PathType Leaf)) {
    Write-Error "RB HTML prototype was not found: $resolvedPath"
    exit 1
}

$html = [System.IO.File]::ReadAllText($resolvedPath, [System.Text.UTF8Encoding]::new($false))
$errors = [System.Collections.Generic.List[string]]::new()

function Require-Match {
    param(
        [string]$Pattern,
        [string]$Message,
        [System.Text.RegularExpressions.RegexOptions]$Options = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    if (-not [regex]::IsMatch($html, $Pattern, $Options)) {
        $errors.Add($Message)
    }
}

function Forbid-Match {
    param(
        [string]$Pattern,
        [string]$Message,
        [System.Text.RegularExpressions.RegexOptions]$Options = [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
    )

    if ([regex]::IsMatch($html, $Pattern, $Options)) {
        $errors.Add($Message)
    }
}

function Get-AttributeValue {
    param(
        [string]$Element,
        [string]$Name
    )

    $pattern = '\b' + [regex]::Escape($Name) + '\s*=\s*["''](?<value>[^"'']*)["'']'
    $match = [regex]::Match($Element, $pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)

    if ($match.Success) {
        return $match.Groups['value'].Value
    }

    return $null
}

function Get-QuoteFormControl {
    param([string]$Name)

    if ([string]::IsNullOrWhiteSpace($script:quoteFormHtml)) {
        return $null
    }

    $namePattern = [regex]::Escape($Name)
    $pattern = '(?is)<(?<tag>input|textarea)\b(?=[^>]*\bname\s*=\s*["'']' + $namePattern + '["''])[^>]*>'
    return [regex]::Match($script:quoteFormHtml, $pattern)
}

function Require-QuoteFormControl {
    param(
        [string]$Name,
        [string]$ExpectedTag,
        [switch]$Visible,
        [switch]$Required,
        [string]$InputType
    )

    $control = Get-QuoteFormControl -Name $Name
    if ($null -eq $control -or -not $control.Success) {
        $errors.Add("Quote form is missing the '$Name' control.")
        return $null
    }

    $element = $control.Value
    $tag = $control.Groups['tag'].Value.ToLowerInvariant()

    if ($ExpectedTag -and $tag -ne $ExpectedTag) {
        $errors.Add("Quote form control '$Name' must use <$ExpectedTag>.")
    }

    $type = Get-AttributeValue -Element $element -Name 'type'
    if ($Visible -and $type -eq 'hidden') {
        $errors.Add("Quote form control '$Name' must be visible, not hidden.")
    }

    if ($Required -and $element -notmatch '(?i)\brequired(?:\s|=|/|>)') {
        $errors.Add("Quote form control '$Name' must be required by the API contract.")
    }

    if ($InputType -and $type -ne $InputType) {
        $errors.Add("Quote form control '$Name' must use type='$InputType'.")
    }

    return $control
}

function Require-HiddenControl {
    param([string]$Name)

    $control = Require-QuoteFormControl -Name $Name -ExpectedTag 'input'
    if ($null -eq $control) {
        return $null
    }

    if ((Get-AttributeValue -Element $control.Value -Name 'type') -ne 'hidden') {
        $errors.Add("Quote form control '$Name' must be hidden technical data.")
    }

    return $control
}

function Require-JsonHiddenControl {
    param(
        [string]$Name,
        [string]$ExpectedPrefix,
        [string]$ExpectedDataType
    )

    $control = Require-HiddenControl -Name $Name
    if ($null -eq $control) {
        return
    }

    $value = Get-AttributeValue -Element $control.Value -Name 'value'
    if ([string]::IsNullOrWhiteSpace($value) -or -not $value.TrimStart().StartsWith($ExpectedPrefix)) {
        $errors.Add("Quote form control '$Name' must contain a JSON $ExpectedDataType representation.")
        return
    }

    try {
        $null = ConvertFrom-Json -InputObject $value -ErrorAction Stop
    }
    catch {
        $errors.Add("Quote form control '$Name' contains invalid JSON.")
    }

    if ((Get-AttributeValue -Element $control.Value -Name 'data-json') -ne $ExpectedDataType) {
        $errors.Add("Quote form control '$Name' must declare data-json='$ExpectedDataType'.")
    }
}

Require-Match '<!doctype\s+html' 'Missing HTML5 doctype.'
Require-Match '<html\b[^>]*\blang\s*=\s*["'']ru(?:-[A-Z]{2})?["'']' 'The prototype must declare a Russian document language.'
Require-Match '<title>\s*[^<\s][^<]*</title>' 'Missing non-empty <title>.'
Require-Match '<meta\b(?=[^>]*\bname\s*=\s*["'']description["''])(?=[^>]*\bcontent\s*=\s*["'']\s*\S)[^>]*>' 'Missing non-empty meta description.'
Require-Match '<meta\b(?=[^>]*\bname\s*=\s*["'']robots["''])(?=[^>]*\bcontent\s*=\s*["''][^"'']*\bnoindex\b)(?=[^>]*\bcontent\s*=\s*["''][^"'']*\bnofollow\b)[^>]*>' 'Static prototype must be protected by meta robots=noindex, nofollow.'
Require-Match '<main\b' 'Missing semantic <main>.'
Require-Match '<nav\b[^>]*\baria-label\s*=' 'Navigation must have an aria-label.'
Require-Match 'data-site-scope\s*=\s*["'']site_id["'']' 'Missing data-site-scope="site_id" contract marker.'
Require-Match 'data-seo-canonical\s*=\s*["'']self-on-published-route["'']' 'Missing self-canonical SSR contract marker.'
Require-Match 'data-filter-indexing\s*=\s*["'']noindex["'']' 'Missing noindex contract marker for filter state.'
Require-Match 'data-search-indexing\s*=\s*["'']noindex["'']' 'Missing noindex contract marker for search state.'

$quoteFormMatch = [regex]::Match(
    $html,
    '(?is)(?<open><form\b(?=[^>]*\bid\s*=\s*["'']quoteForm["''])[^>]*>)(?<body>.*?)</form\s*>'
)

if (-not $quoteFormMatch.Success) {
    $errors.Add('Missing quote form with id="quoteForm".')
    $quoteFormHtml = ''
    $quoteFormOpen = ''
}
else {
    $quoteFormHtml = $quoteFormMatch.Value
    $quoteFormOpen = $quoteFormMatch.Groups['open'].Value
}

if ($quoteFormOpen) {
    if ((Get-AttributeValue -Element $quoteFormOpen -Name 'data-lead-endpoint') -ne '/api/v1/leads/quote') {
        $errors.Add('Quote form must declare the /api/v1/leads/quote contract endpoint.')
    }

    if ((Get-AttributeValue -Element $quoteFormOpen -Name 'data-prototype-submission') -ne 'disabled') {
        $errors.Add('Static prototype submission must be explicitly disabled.')
    }

    if ((Get-AttributeValue -Element $quoteFormOpen -Name 'data-contact-rule') -ne 'email-or-phone') {
        $errors.Add('Quote form must declare the email-or-phone contact rule.')
    }

    if ($quoteFormOpen -match '(?i)\baction\s*=') {
        $errors.Add('Static prototype quote form must not declare a submission action.')
    }
}

Require-QuoteFormControl -Name 'company' -ExpectedTag 'input' -Visible -Required | Out-Null
Require-QuoteFormControl -Name 'contact_name' -ExpectedTag 'input' -Visible -Required | Out-Null
$emailControl = Require-QuoteFormControl -Name 'email' -ExpectedTag 'input' -Visible -InputType 'email'
$phoneControl = Require-QuoteFormControl -Name 'phone' -ExpectedTag 'input' -Visible -InputType 'tel'
Require-QuoteFormControl -Name 'message' -ExpectedTag 'textarea' -Visible | Out-Null

foreach ($contactControl in @($emailControl, $phoneControl)) {
    if ($null -ne $contactControl -and $contactControl.Value -match '(?i)\brequired(?:\s|=|/|>)') {
        $errors.Add('Email and phone must remain separate optional fields with the email-or-phone rule, not two required fields.')
    }
}

$siteKey = Require-HiddenControl -Name 'site_key'
$locale = Require-HiddenControl -Name 'locale'
$pageUrl = Require-HiddenControl -Name 'page_url'
Require-JsonHiddenControl -Name 'cart' -ExpectedPrefix '[' -ExpectedDataType 'array'
Require-JsonHiddenControl -Name 'utm' -ExpectedPrefix '{' -ExpectedDataType 'object'

if ($null -ne $siteKey -and (Get-AttributeValue -Element $siteKey.Value -Name 'value') -ne 'microchips-by') {
    $errors.Add("Quote form site_key must be the RB profile key 'microchips-by'.")
}

if ($null -ne $locale -and (Get-AttributeValue -Element $locale.Value -Name 'value') -ne 'ru-BY') {
    $errors.Add("Quote form locale must be the RB profile locale 'ru-BY'.")
}

if ($null -ne $pageUrl) {
    $pageUrlValue = Get-AttributeValue -Element $pageUrl.Value -Name 'value'
    if ($pageUrlValue -notmatch '^https://microchips\.by(?:/|$)') {
        $errors.Add('Quote form page_url must be an absolute https://microchips.by URL, never a relative path.')
    }

    if ((Get-AttributeValue -Element $pageUrl.Value -Name 'data-page-url') -ne 'absolute-current-route') {
        $errors.Add("Quote form page_url must declare data-page-url='absolute-current-route'.")
    }
}

foreach ($legacyField in @('name', 'contact', 'requirement', 'utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term')) {
    if ((Get-QuoteFormControl -Name $legacyField).Success) {
        $errors.Add("Quote form uses incompatible legacy control '$legacyField'.")
    }
}

if (Test-Path -LiteralPath $leadControllerPath -PathType Leaf) {
    $leadController = [System.IO.File]::ReadAllText($leadControllerPath, [System.Text.UTF8Encoding]::new($false))
    $serverRequiredFields = @(
        [regex]::Matches($leadController, "(?m)^\s*'(?<field>[a-z_]+)'\s*=>\s*\[\s*'required'(?:\s*,|\s*\])") |
            ForEach-Object { $_.Groups['field'].Value } |
            Sort-Object -Unique
    )

    if ($serverRequiredFields.Count -eq 0) {
        $errors.Add('Could not read required lead fields from LeadController validation.')
    }
    else {
        foreach ($serverField in $serverRequiredFields) {
            $control = Get-QuoteFormControl -Name $serverField
            if ($null -eq $control -or -not $control.Success) {
                $errors.Add("LeadController requires '$serverField', but the prototype form does not expose or map it.")
            }
        }
    }
}
else {
    $errors.Add("LeadController validation source was not found: $leadControllerPath")
}

$h1Count = [regex]::Matches($html, '<h1\b', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase).Count
if ($h1Count -ne 1) {
    $errors.Add("Expected exactly one <h1>; found $h1Count.")
}

Forbid-Match '<link\b[^>]*\brel\s*=\s*["'']canonical["'']' 'A static noindex prototype must not publish a fake canonical URL.'
Forbid-Match '<meta\b[^>]*\bname\s*=\s*["'']robots["''][^>]*\bcontent\s*=\s*["''][^"'']*\b(?:index|all)\b' 'Robots metadata must not allow indexing of the static prototype.'
Forbid-Match '(?:src|href)\s*=\s*["''](?:https?:)?//' 'External scripts, styles, images and links are not allowed in the prototype.'
Forbid-Match '<script\b[^>]*\bsrc\s*=' 'The prototype must not load a script resource.'
Forbid-Match '\b(?:fetch|XMLHttpRequest|axios)\s*\(' 'The prototype must not make network requests.'
Forbid-Match '<img\b[^>]*\bsrc\s*=\s*["''](?:data:|https?:|//)' 'The prototype must not embed external or data-URI image assets.'
Forbid-Match '<form\b[^>]*\bid\s*=\s*["'']quoteForm["''][^>]*\baction\s*=' 'The static quote form must not submit to an action URL.'

if ($errors.Count -gt 0) {
    Write-Host "RB HTML prototype validation failed: $resolvedPath" -ForegroundColor Red
    foreach ($finding in $errors) {
        Write-Host " - $finding" -ForegroundColor Red
    }

    exit 1
}

Write-Host "RB HTML prototype validation passed: $resolvedPath" -ForegroundColor Green
