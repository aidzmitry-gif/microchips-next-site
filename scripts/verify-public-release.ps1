[CmdletBinding()]
param(
    [string]$BaseUrl,
    [string]$ExpectedHost,
    [string]$ExpectedSiteKey,
    [string[]]$RequiredPaths = @('/'),
    [string[]]$Expected404Paths = @(),
    [hashtable]$ExpectedRedirects = @{},
    [string]$OutputDir = 'docs/audits/generated/public-release',
    [ValidateRange(5, 120)]
    [int]$TimeoutSeconds = 20,
    [switch]$RunSelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-PublicBaseUrl {
    param([string]$Url, [string]$DomainHost)

    if ([string]::IsNullOrWhiteSpace($Url) -or [string]::IsNullOrWhiteSpace($Host)) { return $false }
    try { $uri = [Uri]$Url } catch { return $false }
    $normalizedHost = $DomainHost.Trim().TrimEnd('.').ToLowerInvariant()
    return $uri.Scheme -eq 'https' -and
        $uri.Host.TrimEnd('.').ToLowerInvariant() -eq $normalizedHost -and
        $uri.AbsolutePath -eq '/' -and
        [string]::IsNullOrEmpty($uri.Query) -and
        [string]::IsNullOrEmpty($uri.Fragment) -and
        $uri.Port -eq 443 -and
        $normalizedHost -notin @('localhost', '127.0.0.1', '::1') -and
        -not $normalizedHost.EndsWith('.test')
}

function Invoke-PublicGet {
    param([Uri]$Uri, [int]$Timeout)

    $request = [System.Net.HttpWebRequest]::Create($Uri)
    $request.Method = 'GET'
    $request.AllowAutoRedirect = $false
    $request.Timeout = $Timeout * 1000
    $request.ReadWriteTimeout = $Timeout * 1000
    $request.UserAgent = 'microchips-public-release-verifier/1.0'
    try {
        $response = $request.GetResponse()
    } catch [System.Net.WebException] {
        if ($null -eq $_.Exception.Response) { throw }
        $response = $_.Exception.Response
    }
    try {
        $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
        try { $body = $reader.ReadToEnd() } finally { $reader.Dispose() }
        return [pscustomobject]@{
            StatusCode = [int]$response.StatusCode
            Location = [string]$response.Headers['Location']
            Body = $body
        }
    } finally {
        $response.Dispose()
    }
}

function Get-CanonicalHref {
    param([string]$Html)
    foreach ($tag in [regex]::Matches($Html, '(?is)<link\b[^>]*>')) {
        if ($tag.Value -notmatch '(?i)\brel\s*=\s*["'']canonical["'']') { continue }
        $href = [regex]::Match($tag.Value, '(?i)\bhref\s*=\s*["'']([^"'']+)["'']')
        if ($href.Success) { return $href.Groups[1].Value }
    }
    return $null
}

function Get-SitemapLocations {
    param([string]$Xml)
    [xml]$document = $Xml
    return @($document.SelectNodes('//*[local-name()="loc"]') | ForEach-Object { $_.InnerText.Trim() })
}

function Add-Check {
    param([System.Collections.Generic.List[object]]$Checks, [string]$Name, [bool]$Passed, [string]$Detail)
    $Checks.Add([pscustomobject]@{ name = $Name; passed = $Passed; detail = $Detail })
}

function Invoke-SelfTest {
    if (-not (Test-PublicBaseUrl -Url 'https://staging.microchips.by/' -DomainHost 'staging.microchips.by')) { throw 'Expected valid HTTPS base URL was rejected.' }
    if (Test-PublicBaseUrl -Url 'http://staging.microchips.by/' -DomainHost 'staging.microchips.by') { throw 'HTTP URL was accepted.' }
    if (Test-PublicBaseUrl -Url 'https://localhost/' -DomainHost 'localhost') { throw 'Localhost URL was accepted.' }
    $locations = @(Get-SitemapLocations -Xml '<urlset><url><loc>https://staging.microchips.by/</loc></url></urlset>')
    if ($locations.Count -ne 1 -or $locations[0] -ne 'https://staging.microchips.by/') { throw 'Sitemap fixture was parsed incorrectly.' }
    if ((Get-CanonicalHref -Html '<link href="https://staging.microchips.by/" rel="canonical">') -ne 'https://staging.microchips.by/') { throw 'Canonical fixture was parsed incorrectly.' }
    Write-Output 'PASS: public release verifier self-test passed'
}

if ($RunSelfTest) { Invoke-SelfTest; exit 0 }
if (-not (Test-PublicBaseUrl -Url $BaseUrl -DomainHost $ExpectedHost)) {
    throw 'BaseUrl must be an HTTPS root URL on ExpectedHost, without query, fragment, custom port, localhost, or .test host.'
}

$expectedHostNormalized = $ExpectedHost.Trim().TrimEnd('.').ToLowerInvariant()
$baseUri = [Uri]$BaseUrl
$checks = New-Object 'System.Collections.Generic.List[object]'
$errors = New-Object 'System.Collections.Generic.List[string]'

try {
    $home = Invoke-PublicGet -Uri $baseUri -Timeout $TimeoutSeconds
    Add-Check $checks 'https-home-status' ($home.StatusCode -eq 200) "status=$($home.StatusCode)"
    $canonical = Get-CanonicalHref -Html $home.Body
    Add-Check $checks 'home-canonical' ($canonical -eq "https://$expectedHostNormalized/") "canonical=$canonical"
} catch { $errors.Add("home: $($_.Exception.Message)") }

try {
    $httpResponse = Invoke-PublicGet -Uri ([Uri]"http://$expectedHostNormalized/") -Timeout $TimeoutSeconds
    $target = $httpResponse.Location
    Add-Check $checks 'http-to-https-redirect' (($httpResponse.StatusCode -in 301, 308) -and $target -eq "https://$expectedHostNormalized/") "status=$($httpResponse.StatusCode); location=$target"
} catch { $errors.Add("http redirect: $($_.Exception.Message)") }

foreach ($path in @('/robots.txt', '/sitemap.xml') + $RequiredPaths) {
    try {
        $response = Invoke-PublicGet -Uri ([Uri]::new($baseUri, $path)) -Timeout $TimeoutSeconds
        Add-Check $checks "status:$path" ($response.StatusCode -eq 200) "status=$($response.StatusCode)"
        if ($path -eq '/robots.txt') {
            Add-Check $checks 'robots-sitemap' ($response.Body -match "(?im)^\s*sitemap\s*:\s*https://$([regex]::Escape($expectedHostNormalized))/sitemap\.xml\s*$") 'robots references own sitemap'
        }
        if ($path -eq '/sitemap.xml' -and $response.StatusCode -eq 200) {
            $locations = @(Get-SitemapLocations -Xml $response.Body)
            foreach ($location in $locations) {
                try {
                    $uri = [Uri]$location
                    $valid = $uri.Scheme -eq 'https' -and $uri.Host.TrimEnd('.').ToLowerInvariant() -eq $expectedHostNormalized -and $uri.Port -eq 443 -and [string]::IsNullOrEmpty($uri.Query) -and [string]::IsNullOrEmpty($uri.Fragment)
                } catch { $valid = $false }
                Add-Check $checks "sitemap-url:$location" $valid 'HTTPS same-host URL without query or fragment'
            }
            foreach ($requiredPath in $RequiredPaths) {
                Add-Check $checks "sitemap-includes:$requiredPath" ($locations -contains "https://$expectedHostNormalized$requiredPath") 'required path present in sitemap'
            }
        }
    } catch { $errors.Add("${path}: $($_.Exception.Message)") }
}

foreach ($path in $Expected404Paths) {
    try {
        $response = Invoke-PublicGet -Uri ([Uri]::new($baseUri, $path)) -Timeout $TimeoutSeconds
        Add-Check $checks "not-found:$path" ($response.StatusCode -eq 404) "status=$($response.StatusCode)"
    } catch { $errors.Add("${path}: $($_.Exception.Message)") }
}
foreach ($path in $ExpectedRedirects.Keys) {
    try {
        $response = Invoke-PublicGet -Uri ([Uri]::new($baseUri, [string]$path)) -Timeout $TimeoutSeconds
        $target = [string]$ExpectedRedirects[$path]
        Add-Check $checks "redirect:$path" (($response.StatusCode -in 301, 308) -and $response.Location -eq "https://$expectedHostNormalized$target") "status=$($response.StatusCode); location=$($response.Location)"
    } catch { $errors.Add("${path}: $($_.Exception.Message)") }
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
$passed = $errors.Count -eq 0 -and @($checks | Where-Object { -not $_.passed }).Count -eq 0
$report = [ordered]@{
    generatedAt = (Get-Date).ToUniversalTime().ToString('o')
    baseUrl = $baseUri.AbsoluteUri
    expectedHost = $expectedHostNormalized
    expectedSiteKey = $ExpectedSiteKey
    passed = $passed
    checks = $checks
    errors = $errors
    manualEvidenceRequired = @('legal entity and contacts', 'payment and delivery terms', 'Bitrix24 test lead', 'Search Console, Yandex Webmaster, and analytics verification')
}
$reportPath = Join-Path $OutputDir ((Get-Date).ToString('yyyyMMdd-HHmmss') + '-public-release.json')
$report | ConvertTo-Json -Depth 6 | Set-Content -Path $reportPath -Encoding UTF8
Write-Output "Evidence: $reportPath"
if (-not $passed) { exit 1 }
Write-Output 'PASS: public release checks passed'
