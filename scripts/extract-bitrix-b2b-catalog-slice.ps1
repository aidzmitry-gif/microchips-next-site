[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [string]$SourceRoot = '',
    # PS 5.1 does not reliably initialize $PSScriptRoot while parameter
    # default expressions are evaluated. Resolve the default in script scope
    # below so -RunSelfTest works without an unrelated -OutputDir override.
    [string]$OutputDir = '',
    [switch]$RunSelfTest
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    if ([string]::IsNullOrWhiteSpace($PSScriptRoot)) {
        throw 'Unable to resolve the extractor directory for the default OutputDir. Specify -OutputDir explicitly.'
    }
    $OutputDir = Join-Path (Split-Path $PSScriptRoot -Parent) 'docs\audits\generated'
}

$catalogIblockIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
[void]$catalogIblockIds.Add('26')
[void]$catalogIblockIds.Add('65')

$offerIblockIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
[void]$offerIblockIds.Add('28')
[void]$offerIblockIds.Add('67')

# The 2026-06-23 snapshot contains twelve reviewed, orphaned footwear offers in
# iblock 67.  They have no CML2_LINK value and cannot safely be migrated, but
# they are also demonstrably outside this batteries/UPS slice.  Keep this
# exception deliberately narrow: any new, changed, linked, or in-scope offer
# retains the hard reconciliation gate below.
$reviewedOutOfScopeOfferIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
foreach ($reviewedOfferId in @('26838', '26839', '26840', '26841', '26842', '26843', '26844', '26845', '26846', '26847', '26848', '26849')) {
    [void]$reviewedOutOfScopeOfferIds.Add($reviewedOfferId)
}

# This extractor reads positional VALUES tuples. Validate the source schema before
# using those positions so a Bitrix/MySQL upgrade cannot silently remap a field.
$expectedTableColumns = @{
    'b_iblock_section' = @(
        'ID', 'TIMESTAMP_X', 'MODIFIED_BY', 'DATE_CREATE', 'CREATED_BY', 'IBLOCK_ID', 'IBLOCK_SECTION_ID',
        'ACTIVE', 'GLOBAL_ACTIVE', 'SORT', 'NAME', 'PICTURE', 'LEFT_MARGIN', 'RIGHT_MARGIN', 'DEPTH_LEVEL',
        'DESCRIPTION', 'DESCRIPTION_TYPE', 'SEARCHABLE_CONTENT', 'CODE', 'XML_ID', 'TMP_ID', 'DETAIL_PICTURE', 'SOCNET_GROUP_ID'
    )
    'b_iblock_element' = @(
        'ID', 'TIMESTAMP_X', 'MODIFIED_BY', 'DATE_CREATE', 'CREATED_BY', 'IBLOCK_ID', 'IBLOCK_SECTION_ID',
        'ACTIVE', 'ACTIVE_FROM', 'ACTIVE_TO', 'SORT', 'NAME', 'PREVIEW_PICTURE', 'PREVIEW_TEXT', 'PREVIEW_TEXT_TYPE',
        'DETAIL_PICTURE', 'DETAIL_TEXT', 'DETAIL_TEXT_TYPE', 'SEARCHABLE_CONTENT', 'WF_STATUS_ID', 'WF_PARENT_ELEMENT_ID',
        'WF_NEW', 'WF_LOCKED_BY', 'WF_DATE_LOCK', 'WF_COMMENTS', 'IN_SECTIONS', 'XML_ID', 'CODE', 'TAGS', 'TMP_ID',
        'WF_LAST_HISTORY_ID', 'SHOW_COUNTER', 'SHOW_COUNTER_START'
    )
    'b_iblock_section_element' = @('IBLOCK_SECTION_ID', 'IBLOCK_ELEMENT_ID', 'ADDITIONAL_PROPERTY_ID')
    'b_iblock_property' = @(
        'ID', 'TIMESTAMP_X', 'IBLOCK_ID', 'NAME', 'ACTIVE', 'SORT', 'CODE', 'DEFAULT_VALUE', 'PROPERTY_TYPE',
        'ROW_COUNT', 'COL_COUNT', 'LIST_TYPE', 'MULTIPLE', 'XML_ID', 'FILE_TYPE', 'MULTIPLE_CNT', 'TMP_ID',
        'LINK_IBLOCK_ID', 'WITH_DESCRIPTION', 'SEARCHABLE', 'FILTRABLE', 'IS_REQUIRED', 'VERSION', 'USER_TYPE',
        'USER_TYPE_SETTINGS', 'HINT'
    )
    'b_iblock_property_enum' = @('ID', 'PROPERTY_ID', 'VALUE', 'DEF', 'SORT', 'XML_ID', 'TMP_ID')
    'b_iblock_element_property' = @('ID', 'IBLOCK_PROPERTY_ID', 'IBLOCK_ELEMENT_ID', 'VALUE', 'VALUE_TYPE', 'VALUE_ENUM', 'VALUE_NUM', 'DESCRIPTION')
}

function Assert-Condition {
    param([bool]$Condition, [string]$Message)

    if (-not $Condition) {
        throw "Self-test failed: $Message"
    }
}

function Get-RowValue {
    param(
        [string[]]$Row,
        [int]$Index
    )

    if ($Row.Count -gt $Index) {
        return $Row[$Index]
    }

    return $null
}

function ConvertFrom-MySqlToken {
    param([string]$Token)

    $value = $Token.Trim()
    if ($value -eq 'NULL') {
        return $null
    }

    $singleQuote = [char]39
    $backslash = [char]92
    if ($value.Length -lt 2 -or $value[0] -ne $singleQuote -or $value[$value.Length - 1] -ne $singleQuote) {
        return $value
    }

    $raw = $value.Substring(1, $value.Length - 2)
    $builder = [System.Text.StringBuilder]::new($raw.Length)
    for ($index = 0; $index -lt $raw.Length; $index++) {
        $character = $raw[$index]
        if ($character -ne $backslash -or $index -eq ($raw.Length - 1)) {
            [void]$builder.Append($character)
            continue
        }

        $index++
        $escaped = $raw[$index]
        if ($escaped -eq '0') {
            [void]$builder.Append([char]0)
        }
        elseif ($escaped -eq 'b') {
            [void]$builder.Append([char]8)
        }
        elseif ($escaped -eq 'n') {
            [void]$builder.Append([Environment]::NewLine)
        }
        elseif ($escaped -eq 'r') {
            [void]$builder.Append([char]13)
        }
        elseif ($escaped -eq 't') {
            [void]$builder.Append([char]9)
        }
        elseif ($escaped -eq 'Z') {
            [void]$builder.Append([char]26)
        }
        else {
            [void]$builder.Append($escaped)
        }
    }

    return $builder.ToString()
}

function Split-MySqlTuples {
    param([string]$Line)

    $tuples = [System.Collections.Generic.List[string]]::new()
    $singleQuote = [char]39
    $backslash = [char]92
    $depth = 0
    $start = -1
    $insideString = $false
    $escaped = $false

    for ($index = 0; $index -lt $Line.Length; $index++) {
        $character = $Line[$index]
        if ($insideString) {
            if ($escaped) {
                $escaped = $false
            }
            elseif ($character -eq $backslash) {
                $escaped = $true
            }
            elseif ($character -eq $singleQuote) {
                if ($index -lt ($Line.Length - 1) -and $Line[$index + 1] -eq $singleQuote) {
                    $index++
                }
                else {
                    $insideString = $false
                }
            }
            continue
        }

        if ($character -eq $singleQuote) {
            $insideString = $true
        }
        elseif ($character -eq '(') {
            if ($depth -eq 0) {
                $start = $index
            }
            $depth++
        }
        elseif ($character -eq ')') {
            $depth--
            if ($depth -lt 0) {
                throw 'Unexpected closing parenthesis while reading the MySQL dump.'
            }
            if ($depth -eq 0 -and $start -ge 0) {
                $tuples.Add($Line.Substring($start, $index - $start + 1))
                $start = -1
            }
        }
    }

    if ($insideString -or $depth -ne 0) {
        throw 'Unclosed string or tuple while reading the MySQL dump.'
    }

    return $tuples.ToArray()
}

function ConvertFrom-MySqlTuple {
    param([string]$Tuple)

    $trimmed = $Tuple.Trim()
    if ($trimmed.Length -lt 2 -or $trimmed[0] -ne '(' -or $trimmed[$trimmed.Length - 1] -ne ')') {
        throw "Invalid MySQL tuple: $Tuple"
    }

    $body = $trimmed.Substring(1, $trimmed.Length - 2)
    # Keep raw tokens while scanning, then unescape them in one local loop.
    # Calling ConvertFrom-MySqlToken for every field makes the 22k-row element
    # table disproportionately slow in Windows PowerShell 5.1 (hundreds of
    # thousands of script-function invocations before Pass 3 can be printed).
    # The conversion rules below deliberately match ConvertFrom-MySqlToken.
    $rawTokens = [System.Collections.Generic.List[string]]::new()
    $current = [System.Text.StringBuilder]::new()
    $singleQuote = [char]39
    $backslash = [char]92
    $insideString = $false
    $escaped = $false

    for ($index = 0; $index -lt $body.Length; $index++) {
        $character = $body[$index]
        if ($insideString) {
            [void]$current.Append($character)
            if ($escaped) {
                $escaped = $false
            }
            elseif ($character -eq $backslash) {
                $escaped = $true
            }
            elseif ($character -eq $singleQuote) {
                if ($index -lt ($body.Length - 1) -and $body[$index + 1] -eq $singleQuote) {
                    $index++
                    [void]$current.Append($body[$index])
                }
                else {
                    $insideString = $false
                }
            }
            continue
        }

        if ($character -eq $singleQuote) {
            $insideString = $true
            [void]$current.Append($character)
        }
        elseif ($character -eq ',') {
            $rawTokens.Add($current.ToString())
            [void]$current.Clear()
        }
        else {
            [void]$current.Append($character)
        }
    }

    if ($insideString) {
        throw 'Unclosed quoted value while reading a MySQL tuple.'
    }

    $rawTokens.Add($current.ToString())

    $tokens = [System.Collections.Generic.List[object]]::new()
    foreach ($rawToken in $rawTokens) {
        $value = $rawToken.Trim()
        if ($value -eq 'NULL') {
            $tokens.Add($null)
            continue
        }

        if ($value.Length -lt 2 -or $value[0] -ne $singleQuote -or $value[$value.Length - 1] -ne $singleQuote) {
            $tokens.Add($value)
            continue
        }

        $raw = $value.Substring(1, $value.Length - 2)
        $unescaped = [System.Text.StringBuilder]::new($raw.Length)
        for ($rawIndex = 0; $rawIndex -lt $raw.Length; $rawIndex++) {
            $rawCharacter = $raw[$rawIndex]
            if ($rawCharacter -ne $backslash -or $rawIndex -eq ($raw.Length - 1)) {
                [void]$unescaped.Append($rawCharacter)
                continue
            }

            $rawIndex++
            $escapedCharacter = $raw[$rawIndex]
            if ($escapedCharacter -eq '0') {
                [void]$unescaped.Append([char]0)
            }
            elseif ($escapedCharacter -eq 'b') {
                [void]$unescaped.Append([char]8)
            }
            elseif ($escapedCharacter -eq 'n') {
                [void]$unescaped.Append([Environment]::NewLine)
            }
            elseif ($escapedCharacter -eq 'r') {
                [void]$unescaped.Append([char]13)
            }
            elseif ($escapedCharacter -eq 't') {
                [void]$unescaped.Append([char]9)
            }
            elseif ($escapedCharacter -eq 'Z') {
                [void]$unescaped.Append([char]26)
            }
            else {
                [void]$unescaped.Append($escapedCharacter)
            }
        }

        $tokens.Add($unescaped.ToString())
    }

    Write-Output -NoEnumerate ([object[]]$tokens.ToArray())
}

function Assert-MySqlTableSchema {
    param(
        [string]$Table,
        [string[]]$ActualColumns,
        [string[]]$ExpectedColumns
    )

    if ($ActualColumns.Count -ne $ExpectedColumns.Count) {
        throw "Schema drift in ${Table}: expected $($ExpectedColumns.Count) columns, found $($ActualColumns.Count). No output was written."
    }

    for ($index = 0; $index -lt $ExpectedColumns.Count; $index++) {
        if ($ActualColumns[$index] -ne $ExpectedColumns[$index]) {
            throw "Schema drift in ${Table} at column ${index}: expected '$($ExpectedColumns[$index])', found '$($ActualColumns[$index])'. No output was written."
        }
    }
}

function Get-MySqlStatementScanResult {
    param(
        [string]$Text,
        [bool]$InsideString,
        [bool]$Escaped
    )

    $singleQuote = [char]39
    $backslash = [char]92
    $inside = $InsideString
    $escaped = $Escaped
    $terminatorIndex = -1

    for ($index = 0; $index -lt $Text.Length; $index++) {
        $character = $Text[$index]
        if ($inside) {
            if ($escaped) {
                $escaped = $false
            }
            elseif ($character -eq $backslash) {
                $escaped = $true
            }
            elseif ($character -eq $singleQuote) {
                if ($index -lt ($Text.Length - 1) -and $Text[$index + 1] -eq $singleQuote) {
                    $index++
                }
                else {
                    $inside = $false
                }
            }
            continue
        }

        if ($character -eq $singleQuote) {
            $inside = $true
        }
        elseif ($character -eq ';') {
            $terminatorIndex = $index
            break
        }
    }

    return [PSCustomObject]@{
        inside_string    = $inside
        escaped          = $escaped
        terminator_index = $terminatorIndex
    }
}

function Invoke-MySqlDumpTable {
    param(
        [string]$DumpPath,
        [string]$Table,
        [string[]]$ExpectedColumns,
        [scriptblock]$RowHandler
    )

    $quotedTable = [string]::Concat([char]96, $Table, [char]96)
    $createPattern = '^\s*CREATE TABLE\s+' + [regex]::Escape($quotedTable) + '\s*\('
    $insertPattern = '^\s*INSERT INTO\s+' + [regex]::Escape($quotedTable) + '\s+VALUES(?:\s*(?<payload>.*))?$'
    $capturingSchema = $false
    $schemaVerified = $false
    $schemaColumns = [System.Collections.Generic.List[string]]::new()
    $capturingInsert = $false
    $insertPayload = [System.Collections.Generic.List[string]]::new()
    $insideString = $false
    $escaped = $false
    $file = [System.IO.File]::OpenRead($DumpPath)
    try {
        $gzip = [System.IO.Compression.GzipStream]::new($file, [System.IO.Compression.CompressionMode]::Decompress)
        try {
            $reader = [System.IO.StreamReader]::new($gzip, [System.Text.Encoding]::UTF8)
            try {
                while (-not $reader.EndOfStream) {
                    $line = $reader.ReadLine()

                    if ($capturingSchema) {
                        if ($line -match '^\s*\)') {
                            Assert-MySqlTableSchema -Table $Table -ActualColumns $schemaColumns.ToArray() -ExpectedColumns $ExpectedColumns
                            $schemaVerified = $true
                            $capturingSchema = $false
                        }
                        elseif ($line -match '^\s*`([^`]+)`') {
                            $schemaColumns.Add($matches[1])
                        }
                        continue
                    }

                    if (-not $schemaVerified -and $line -match $createPattern) {
                        $capturingSchema = $true
                        continue
                    }

                    if (-not $capturingInsert) {
                        if ($line -notmatch $insertPattern) {
                            continue
                        }
                        if (-not $schemaVerified) {
                            throw "Schema for $Table was not verified before its INSERT statement. No output was written."
                        }

                        $capturingInsert = $true
                        $insideString = $false
                        $escaped = $false
                        $payload = $matches['payload']
                    }
                    else {
                        $payload = $line
                    }

                    $scan = Get-MySqlStatementScanResult -Text $payload -InsideString $insideString -Escaped $escaped
                    $insideString = $scan.inside_string
                    $escaped = $scan.escaped
                    if ($scan.terminator_index -ge 0) {
                        $insertPayload.Add($payload.Substring(0, $scan.terminator_index))
                        if ($payload.Substring($scan.terminator_index + 1).Trim().Length -gt 0) {
                            throw "Unexpected SQL content after INSERT terminator for $Table. No output was written."
                        }

                        $tupleText = $insertPayload -join [Environment]::NewLine
                        foreach ($tuple in (Split-MySqlTuples -Line $tupleText)) {
                            $row = ConvertFrom-MySqlTuple -Tuple $tuple
                            if ($row.Count -ne $ExpectedColumns.Count) {
                                throw "Tuple-width drift in ${Table}: expected $($ExpectedColumns.Count) fields, found $($row.Count). No output was written."
                            }
                            & $RowHandler -Row $row
                        }

                        $capturingInsert = $false
                        $insideString = $false
                        $escaped = $false
                        $insertPayload.Clear()
                    }
                    else {
                        $insertPayload.Add($payload)
                    }
                }
            }
            finally {
                $reader.Dispose()
            }
        }
        finally {
            $gzip.Dispose()
        }
    }
    finally {
        $file.Dispose()
    }

    if ($capturingSchema) {
        throw "Unclosed CREATE TABLE statement for $Table. No output was written."
    }
    if (-not $schemaVerified) {
        throw "Schema for $Table was not found in the SQL snapshot. No output was written."
    }
    if ($capturingInsert -or $insideString) {
        throw "Unclosed INSERT statement for $Table. No output was written."
    }
}

function Resolve-ElementLinkValue {
    param(
        [psobject]$Property,
        [AllowNull()][string]$Value,
        [hashtable]$ElementIndexById
    )

    # Bitrix property type 'E' stores a foreign element ID (e.g. from a brand
    # reference infoblock) as the raw VALUE. This is a general resolver for
    # any such reference property, not a lookup table of specific brand IDs:
    # it only ever echoes back a name that was actually read from
    # b_iblock_element, and only after confirming the referenced element
    # belongs to the infoblock the property's own LINK_IBLOCK_ID points at
    # (b_iblock_property column 17). Without that check, an element ID that
    # happens to collide with an unrelated infoblock (an article, a staff
    # record, another product) would be echoed back as if it were the
    # intended reference. Statuses:
    #   not_applicable      - property is not a type-E reference at all
    #   empty               - the stored value is blank; there is nothing to link
    #   not_found           - no element with this ID exists anywhere in the dump
    #   scope_unverifiable  - the property itself has no recorded LINK_IBLOCK_ID
    #                         (blank/NULL/missing column, or a non-positive/
    #                         non-numeric value such as '0' - no infoblock has
    #                         ID 0, so it is not a declared scope either), so
    #                         there is no declared scope to check the linked
    #                         element against; this is a gap in the property's
    #                         own metadata, not proof of a broken reference, so
    #                         it must be counted separately from
    #                         iblock_mismatch and must never resolve
    #   iblock_mismatch     - the property DOES declare a LINK_IBLOCK_ID, and
    #                         the linked element exists, but the element's own
    #                         IBLOCK_ID does not match that declared scope -
    #                         i.e. a reference that actually points at the
    #                         wrong infoblock (broken/stale link)
    #   name_missing        - the element exists in the correct scope but its
    #                         NAME column is NULL/blank, so there is no name to
    #                         report; must never be reported as 'resolved'
    #   resolved            - the element exists, is in the correct scope, and
    #                         has a usable name
    if ($Property.property_type -ne 'E') {
        return [PSCustomObject]@{ resolved_name = $null; status = 'not_applicable' }
    }

    if ([string]::IsNullOrWhiteSpace($Value)) {
        return [PSCustomObject]@{ resolved_name = $null; status = 'empty' }
    }

    if (-not $ElementIndexById.ContainsKey($Value)) {
        return [PSCustomObject]@{ resolved_name = $null; status = 'not_found' }
    }

    $linkedElement = $ElementIndexById[$Value]
    $linkIblockIdMember = $Property.PSObject.Properties['link_iblock_id']
    $linkIblockIdRaw = if ($linkIblockIdMember) { $linkIblockIdMember.Value } else { $null }
    # [int]::TryParse already rejects $null/empty/whitespace-only input (no
    # separate IsNullOrWhiteSpace guard needed) and, under the default
    # NumberStyles.Integer it uses, already tolerates surrounding whitespace
    # (see the ' 27' padded-scope self-test below) -- so no .Trim() either.
    $declaredLinkIblockId = 0
    $hasDeclaredLinkIblockId = [int]::TryParse([string]$linkIblockIdRaw, [ref]$declaredLinkIblockId) -and
        ($declaredLinkIblockId -gt 0)
    if (-not $hasDeclaredLinkIblockId) {
        return [PSCustomObject]@{ resolved_name = $null; status = 'scope_unverifiable' }
    }

    $linkedElementIblockId = 0
    $linkedElementInDeclaredScope = [int]::TryParse([string]$linkedElement.iblock_id, [ref]$linkedElementIblockId) -and
        ($linkedElementIblockId -eq $declaredLinkIblockId)
    if (-not $linkedElementInDeclaredScope) {
        return [PSCustomObject]@{ resolved_name = $null; status = 'iblock_mismatch' }
    }

    if ([string]::IsNullOrWhiteSpace($linkedElement.name)) {
        return [PSCustomObject]@{ resolved_name = $null; status = 'name_missing' }
    }

    return [PSCustomObject]@{ resolved_name = $linkedElement.name; status = 'resolved' }
}

function Get-SectionPath {
    param(
        [string]$SectionId,
        [hashtable]$Sections,
        [hashtable]$Cache
    )

    if ($Cache.ContainsKey($SectionId)) {
        return $Cache[$SectionId]
    }

    $parts = [System.Collections.Generic.List[string]]::new()
    $visited = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $currentId = $SectionId
    while (-not [string]::IsNullOrWhiteSpace($currentId) -and $Sections.ContainsKey($currentId)) {
        if (-not $visited.Add($currentId)) {
            throw "Section hierarchy cycle detected at legacy section $currentId."
        }

        $section = $Sections[$currentId]
        $segment = if ([string]::IsNullOrWhiteSpace($section.code)) { "section-$currentId" } else { $section.code }
        $parts.Add($segment)
        $currentId = $section.parent_section_id
    }

    $pathParts = $parts.ToArray()
    [array]::Reverse($pathParts)
    $path = ($pathParts -join '/')
    $Cache[$SectionId] = $path
    return $path
}

function Test-FirstFocusPath {
    param(
        [AllowEmptyString()][string]$Path,
        [string[]]$FocusRootPaths
    )

    foreach ($rootPath in $FocusRootPaths) {
        if ($Path -eq $rootPath -or $Path.StartsWith("$rootPath/", [System.StringComparison]::Ordinal)) {
            return $true
        }
    }

    return $false
}

function Get-NameSignals {
    param([AllowEmptyString()][string]$Name)

    $capacity = [regex]::Match($Name, '(?i)(?<value>\d+(?:[\.,]\d+)?)\s*(?<unit>mah|ah|\u043c\u0430\u0447|\u0430\u0447)\b')
    $voltage = [regex]::Match($Name, '(?i)(?<value>\d+(?:[\.,]\d+)?)\s*(?<unit>v|\u0432)\b')
    $technology = [regex]::Match($Name, '(?i)\b(AGM|GEL|OPzV|OPzS|LiFePO4|Li-ion|Li-Pol|NiMH|NiCd|LTO)\b')

    return [PSCustomObject]@{
        capacity_from_name   = if ($capacity.Success) { $capacity.Value } else { '' }
        voltage_from_name    = if ($voltage.Success) { $voltage.Value } else { '' }
        technology_from_name = if ($technology.Success) { $technology.Value } else { '' }
    }
}

function Test-PropertyKind {
    param(
        [psobject]$Property,
        [ValidateSet('capacity', 'voltage', 'technology', 'identity')]
        [string]$Kind
    )

    $text = "$($Property.property_code) $($Property.property_name)"
    switch ($Kind) {
        'capacity' { return $text -match '(?i)\u0435\u043c\u043a\u043e\u0441\u0442|\u0430\u043c\u043f\u0435\u0440|capacity|ampernost|mah|\u043c\u0430\u0447' }
        'voltage' { return $text -match '(?i)\u043d\u0430\u043f\u0440\u044f\u0436|voltage' }
        'technology' { return $text -match '(?i)\u0442\u0435\u0445\u043d\u043e\u043b\u043e\u0433|\u0445\u0438\u043c\u0438|chemistry|technology' }
        'identity' { return $text -match '(?i)\u0430\u0440\u0442\u0438\u043a\u0443\u043b|article|sku|mpn|\u043a\u043e\u0434.*\u043f\u0440\u043e\u0438\u0437\u0432\u043e\u0434' }
    }
}

function Invoke-SelfTest {
    $line = "(1,'O\'Brien, Inc',NULL,'12 \\ 5'),(2,'GEL',0,'x');"
    $tuples = @(Split-MySqlTuples -Line $line)
    Assert-Condition -Condition ($tuples.Count -eq 2) -Message 'two tuples must be extracted from one INSERT line'

    $first = ConvertFrom-MySqlTuple -Tuple $tuples[0]
    Assert-Condition -Condition ($first.Count -eq 4) -Message 'the first tuple must contain four fields'
    Assert-Condition -Condition ($first[1] -eq "O'Brien, Inc") -Message 'escaped quotes and commas must be preserved'
    Assert-Condition -Condition ($null -eq $first[2]) -Message 'NULL must remain null'
    Assert-Condition -Condition ($first[3] -eq '12 \ 5') -Message 'escaped backslashes must be preserved'

    $signals = Get-NameSignals -Name 'Ventura VG 12-100 UPS (GEL, 100Ah, 12V)'
    Assert-Condition -Condition ($signals.capacity_from_name -eq '100Ah') -Message 'capacity signal must be extracted'
    Assert-Condition -Condition ($signals.voltage_from_name -eq '12V') -Message 'voltage signal must be extracted'
    Assert-Condition -Condition ($signals.technology_from_name -eq 'GEL') -Message 'technology signal must be extracted'

    $amperageProperty = [PSCustomObject]@{ property_code = 'AMPERNOST_AH'; property_name = 'Амперность, Ач' }
    Assert-Condition -Condition (Test-PropertyKind -Property $amperageProperty -Kind 'capacity') -Message 'amperage in Ah must be treated as capacity'

    $elementIndexById = @{
        '4656' = [PSCustomObject]@{ name = 'MNB'; iblock_id = '27' }
        '6000' = [PSCustomObject]@{ name = 'Some Blog Article Title'; iblock_id = '99' }
        '5000' = [PSCustomObject]@{ name = $null; iblock_id = '27' }
    }
    $elementLinkProperty = [PSCustomObject]@{ property_type = 'E'; link_iblock_id = '27' }
    $resolvedLink = Resolve-ElementLinkValue -Property $elementLinkProperty -Value '4656' -ElementIndexById $elementIndexById
    Assert-Condition -Condition ($resolvedLink.status -eq 'resolved' -and $resolvedLink.resolved_name -eq 'MNB') -Message 'element-link property values must resolve to the referenced element name when the element is inside the property''s LINK_IBLOCK_ID scope'

    $missingLink = Resolve-ElementLinkValue -Property $elementLinkProperty -Value '99999' -ElementIndexById $elementIndexById
    Assert-Condition -Condition ($missingLink.status -eq 'not_found' -and $null -eq $missingLink.resolved_name) -Message 'element-link resolution must report not_found rather than guessing when the referenced element is missing'

    $emptyLink = Resolve-ElementLinkValue -Property $elementLinkProperty -Value '' -ElementIndexById $elementIndexById
    Assert-Condition -Condition ($emptyLink.status -eq 'empty' -and $null -eq $emptyLink.resolved_name) -Message 'a blank type-E value must report empty, distinct from not_found, so summary counters are not distorted'

    $mismatchedLink = Resolve-ElementLinkValue -Property $elementLinkProperty -Value '6000' -ElementIndexById $elementIndexById
    Assert-Condition -Condition ($mismatchedLink.status -eq 'iblock_mismatch' -and $null -eq $mismatchedLink.resolved_name) -Message 'an element that exists but belongs to a different infoblock than the property''s LINK_IBLOCK_ID must never be echoed back as resolved'

    $unscopedProperty = [PSCustomObject]@{ property_type = 'E'; link_iblock_id = $null }
    $unscopedLink = Resolve-ElementLinkValue -Property $unscopedProperty -Value '4656' -ElementIndexById $elementIndexById
    Assert-Condition -Condition ($unscopedLink.status -eq 'scope_unverifiable' -and $null -eq $unscopedLink.resolved_name) -Message 'a type-E property with no recorded LINK_IBLOCK_ID cannot have its scope verified and must be reported as scope_unverifiable, distinct from iblock_mismatch, and must not resolve'

    $zeroScopedProperty = [PSCustomObject]@{ property_type = 'E'; link_iblock_id = '0' }
    $zeroScopedLink = Resolve-ElementLinkValue -Property $zeroScopedProperty -Value '4656' -ElementIndexById $elementIndexById
    Assert-Condition -Condition ($zeroScopedLink.status -eq 'scope_unverifiable' -and $null -eq $zeroScopedLink.resolved_name) -Message 'a LINK_IBLOCK_ID of 0 is not a declared scope (no infoblock has ID 0) and must report scope_unverifiable, not iblock_mismatch'

    $paddedScopeProperty = [PSCustomObject]@{ property_type = 'E'; link_iblock_id = ' 27' }
    $paddedScopeLink = Resolve-ElementLinkValue -Property $paddedScopeProperty -Value '4656' -ElementIndexById $elementIndexById
    Assert-Condition -Condition ($paddedScopeLink.status -eq 'resolved' -and $paddedScopeLink.resolved_name -eq 'MNB') -Message 'LINK_IBLOCK_ID and iblock_id must be compared numerically so incidental whitespace such as a leading space does not produce a false iblock_mismatch'

    $unscopedPropertyNoField = [PSCustomObject]@{ property_type = 'E' }
    $unscopedLinkNoField = Resolve-ElementLinkValue -Property $unscopedPropertyNoField -Value '4656' -ElementIndexById $elementIndexById
    Assert-Condition -Condition ($unscopedLinkNoField.status -eq 'scope_unverifiable' -and $null -eq $unscopedLinkNoField.resolved_name) -Message 'a type-E property missing the link_iblock_id field entirely must also report scope_unverifiable, not iblock_mismatch'

    $nameMissingLink = Resolve-ElementLinkValue -Property $elementLinkProperty -Value '5000' -ElementIndexById $elementIndexById
    Assert-Condition -Condition ($nameMissingLink.status -eq 'name_missing' -and $null -eq $nameMissingLink.resolved_name) -Message 'an in-scope element with a NULL name must report name_missing, never resolved with a null name'

    $nonLinkProperty = [PSCustomObject]@{ property_type = 'S' }
    $notApplicableLink = Resolve-ElementLinkValue -Property $nonLinkProperty -Value 'whatever' -ElementIndexById $elementIndexById
    Assert-Condition -Condition ($notApplicableLink.status -eq 'not_applicable') -Message 'non element-link property types must be marked not_applicable, not resolved'

    $scanFirstLine = Get-MySqlStatementScanResult -Text "(1,'semicolon; remains inside text')," -InsideString $false -Escaped $false
    Assert-Condition -Condition ($scanFirstLine.terminator_index -eq -1) -Message 'a semicolon inside a quoted value must not terminate INSERT capture'
    $scanSecondLine = Get-MySqlStatementScanResult -Text "(2,'second row');" -InsideString $scanFirstLine.inside_string -Escaped $scanFirstLine.escaped
    Assert-Condition -Condition ($scanSecondLine.terminator_index -ge 0) -Message 'a semicolon outside a quoted value must terminate INSERT capture'
    $multilineTuples = @(Split-MySqlTuples -Line ("(1,'semicolon; remains inside text')," + [Environment]::NewLine + "(2,'second row')"))
    Assert-Condition -Condition ($multilineTuples.Count -eq 2) -Message 'tuples split across INSERT lines must remain complete'

    $schemaDriftDetected = $false
    try {
        Assert-MySqlTableSchema -Table 'test_table' -ActualColumns @('ID', 'WRONG_NAME') -ExpectedColumns @('ID', 'NAME')
    }
    catch {
        $schemaDriftDetected = $true
    }
    Assert-Condition -Condition $schemaDriftDetected -Message 'schema drift must stop positional tuple extraction'

    $tupleWidthDriftDetected = $false
    try {
        $wrongWidth = ConvertFrom-MySqlTuple -Tuple "(1,'only two fields')"
        if ($wrongWidth.Count -ne 3) {
            throw 'tuple width differs from the expected schema'
        }
    }
    catch {
        $tupleWidthDriftDetected = $true
    }
    Assert-Condition -Condition $tupleWidthDriftDetected -Message 'tuple-width drift must be detectable before positional field reads'

    Write-Output 'Self-test passed: tuple parser, statement termination, schema drift and name-signal checks are safe to run.'
}

if ($RunSelfTest) {
    Invoke-SelfTest
    return
}

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    throw 'SourceRoot is required. No output was written.'
}

$dumpPath = Join-Path $SourceRoot 'db\user_microchips_data.sql.gz'
if (-not (Test-Path -LiteralPath $dumpPath -PathType Leaf)) {
    throw "Read-only Bitrix SQL gzip source was not found: $dumpPath. No output was written."
}

Write-Output "Read-only source: $dumpPath"
Write-Output 'Pass 1/5: reading catalog sections.'
$sections = @{}
Invoke-MySqlDumpTable -DumpPath $dumpPath -Table 'b_iblock_section' -ExpectedColumns $expectedTableColumns['b_iblock_section'] -RowHandler {
    param([string[]]$Row)

    $iblockId = Get-RowValue -Row $Row -Index 5
    if (-not $catalogIblockIds.Contains($iblockId)) {
        return
    }

    $id = Get-RowValue -Row $Row -Index 0
    if ([string]::IsNullOrWhiteSpace($id)) {
        return
    }

    $sections[$id] = [PSCustomObject][ordered]@{
        legacy_section_id        = $id
        legacy_iblock_id         = $iblockId
        parent_section_id        = Get-RowValue -Row $Row -Index 6
        active                   = Get-RowValue -Row $Row -Index 7
        global_active            = Get-RowValue -Row $Row -Index 8
        name                     = Get-RowValue -Row $Row -Index 10
        code                     = Get-RowValue -Row $Row -Index 18
        xml_id                   = Get-RowValue -Row $Row -Index 19
        picture_file_id          = Get-RowValue -Row $Row -Index 11
        detail_picture_file_id   = Get-RowValue -Row $Row -Index 21
    }
}

if ($sections.Count -eq 0) {
    throw 'No catalog sections from infoblocks 26 or 65 were extracted. No output was written.'
}

$childrenByParent = @{}
foreach ($section in $sections.Values) {
    $parentId = [string]$section.parent_section_id
    if (-not $childrenByParent.ContainsKey($parentId)) {
        $childrenByParent[$parentId] = [System.Collections.Generic.List[string]]::new()
    }
    $childrenByParent[$parentId].Add([string]$section.legacy_section_id)
}

$directTargetSectionIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
foreach ($section in $sections.Values) {
    $searchText = "$($section.code) $($section.name)"
    if ($searchText -match '(?i)\u0438\u0431\u043f|\u0431\u0435\u0441\u043f\u0435\u0440\u0435\u0431\u043e\u0439\u043d|\u043f\u0440\u043e\u043c\u044b\u0448\u043b\u0435\u043d|industrial|ups') {
        [void]$directTargetSectionIds.Add([string]$section.legacy_section_id)
    }
}

if ($directTargetSectionIds.Count -eq 0) {
    throw 'No UPS/industrial target sections were detected by code or name. No output was written; review the source taxonomy.'
}

$targetSectionIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
$queue = [System.Collections.Generic.Queue[string]]::new()
foreach ($sectionId in $directTargetSectionIds) {
    [void]$targetSectionIds.Add($sectionId)
    $queue.Enqueue($sectionId)
}
while ($queue.Count -gt 0) {
    $currentId = $queue.Dequeue()
    if (-not $childrenByParent.ContainsKey($currentId)) {
        continue
    }
    foreach ($childId in $childrenByParent[$currentId]) {
        if ($targetSectionIds.Add($childId)) {
            $queue.Enqueue($childId)
        }
    }
}

$sectionPathCache = @{}
$targetSectionRows = foreach ($sectionId in $targetSectionIds) {
    $section = $sections[$sectionId]
    [PSCustomObject][ordered]@{
        legacy_section_id      = $section.legacy_section_id
        legacy_iblock_id       = $section.legacy_iblock_id
        parent_section_id      = $section.parent_section_id
        active                 = $section.active
        global_active          = $section.global_active
        name                   = $section.name
        code                   = $section.code
        source_section_path    = Get-SectionPath -SectionId $sectionId -Sections $sections -Cache $sectionPathCache
        target_selection_reason = if ($directTargetSectionIds.Contains($sectionId)) { 'target_keyword' } else { 'descendant_of_target_section' }
        review_status          = 'needs_review'
    }
}

# The first public RB route is intentionally narrower than the broad industrial
# taxonomy. Membership in any of these sections is retained as evidence.
$firstFocusRootPaths = @(
    'akkumulyatory/dlya_ibp',
    'istochniki-pitaniya/ibp',
    'akkumulyatory/promyshlennye/dlya_rezervnogo_pitaniya'
)
$firstFocusSectionIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
foreach ($sectionId in $targetSectionIds) {
    $path = Get-SectionPath -SectionId $sectionId -Sections $sections -Cache $sectionPathCache
    if (Test-FirstFocusPath -Path $path -FocusRootPaths $firstFocusRootPaths) {
        [void]$firstFocusSectionIds.Add($sectionId)
    }
}
if ($firstFocusSectionIds.Count -eq 0) {
    throw 'No narrow UPS/reserve-power focus sections were detected. No output was written; review the source taxonomy.'
}

Write-Output 'Pass 2/5: reading catalog elements and retaining source identities.'
$catalogElements = @{}
$offerElements = @{}
$elementRowProgress = [PSCustomObject]@{ count = 0 }
# Every element in the dump, regardless of iblock, so that reference/lookup
# infoblocks (e.g. a brand directory) can be resolved by ID later. This is a
# read-only, general-purpose ID->{name, iblock_id} index, not specific to any
# one property. The iblock_id is kept alongside the name so a type-E resolver
# can confirm the referenced element actually belongs to the infoblock the
# reference property points at (LINK_IBLOCK_ID), not just that some element
# with that ID exists somewhere in the dump.
$elementIndexById = @{}
$offerElementCounts = @{
    '28' = 0
    '67' = 0
}
$offerActiveElementCounts = @{
    '28' = 0
    '67' = 0
}
Invoke-MySqlDumpTable -DumpPath $dumpPath -Table 'b_iblock_element' -ExpectedColumns $expectedTableColumns['b_iblock_element'] -RowHandler {
    param([string[]]$Row)

    $elementRowProgress.count++
    if (($elementRowProgress.count % 1000) -eq 0) {
        Write-Output "Pass 2/5 progress: parsed $($elementRowProgress.count) b_iblock_element rows."
    }

    $iblockId = Get-RowValue -Row $Row -Index 5
    $id = Get-RowValue -Row $Row -Index 0
    if (-not [string]::IsNullOrWhiteSpace($id)) {
        $elementIndexById[$id] = [PSCustomObject]@{
            name       = Get-RowValue -Row $Row -Index 11
            iblock_id  = $iblockId
        }
    }
    if ($offerIblockIds.Contains($iblockId)) {
        if ([string]::IsNullOrWhiteSpace($id)) {
            return
        }

        $offerElementCounts[$iblockId]++
        if ((Get-RowValue -Row $Row -Index 7) -eq 'Y') {
            $offerActiveElementCounts[$iblockId]++
        }
        $offerElements[$id] = [PSCustomObject][ordered]@{
            legacy_iblock_id = $iblockId
            active           = Get-RowValue -Row $Row -Index 7
            name             = Get-RowValue -Row $Row -Index 11
        }
        return
    }

    if (-not $catalogIblockIds.Contains($iblockId)) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($id)) {
        return
    }

    $catalogElements[$id] = [PSCustomObject][ordered]@{
        legacy_element_id        = $id
        legacy_iblock_id         = $iblockId
        primary_section_id       = Get-RowValue -Row $Row -Index 6
        active                   = Get-RowValue -Row $Row -Index 7
        name                     = Get-RowValue -Row $Row -Index 11
        preview_picture_file_id  = Get-RowValue -Row $Row -Index 12
        preview_text             = Get-RowValue -Row $Row -Index 13
        preview_text_type        = Get-RowValue -Row $Row -Index 14
        detail_picture_file_id   = Get-RowValue -Row $Row -Index 15
        detail_text              = Get-RowValue -Row $Row -Index 16
        detail_text_type         = Get-RowValue -Row $Row -Index 17
        searchable_content       = Get-RowValue -Row $Row -Index 18
        legacy_xml_id            = Get-RowValue -Row $Row -Index 26
        legacy_code              = Get-RowValue -Row $Row -Index 27
    }
}

Write-Output 'Pass 3/5: reading additional section memberships.'
$matchedSectionsByElement = @{}
foreach ($element in $catalogElements.Values) {
    $primarySectionId = [string]$element.primary_section_id
    if ($targetSectionIds.Contains($primarySectionId)) {
        $matchedSectionsByElement[[string]$element.legacy_element_id] = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
        [void]$matchedSectionsByElement[[string]$element.legacy_element_id].Add($primarySectionId)
    }
}
Invoke-MySqlDumpTable -DumpPath $dumpPath -Table 'b_iblock_section_element' -ExpectedColumns $expectedTableColumns['b_iblock_section_element'] -RowHandler {
    param([string[]]$Row)

    $sectionId = Get-RowValue -Row $Row -Index 0
    $elementId = Get-RowValue -Row $Row -Index 1
    if (-not $targetSectionIds.Contains($sectionId) -or -not $catalogElements.ContainsKey($elementId)) {
        return
    }

    if (-not $matchedSectionsByElement.ContainsKey($elementId)) {
        $matchedSectionsByElement[$elementId] = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    }
    [void]$matchedSectionsByElement[$elementId].Add($sectionId)
}

Write-Output 'Pass 4/5: reading catalog property definitions and enum labels.'
$properties = @{}
$offerCml2LinkPropertyIds = @{}
Invoke-MySqlDumpTable -DumpPath $dumpPath -Table 'b_iblock_property' -ExpectedColumns $expectedTableColumns['b_iblock_property'] -RowHandler {
    param([string[]]$Row)

    $iblockId = Get-RowValue -Row $Row -Index 2
    $propertyId = Get-RowValue -Row $Row -Index 0
    $propertyCode = Get-RowValue -Row $Row -Index 6
    if ($offerIblockIds.Contains($iblockId)) {
        if ($propertyCode -eq 'CML2_LINK' -and -not [string]::IsNullOrWhiteSpace($propertyId)) {
            $offerCml2LinkPropertyIds[$propertyId] = $iblockId
        }
        return
    }

    if (-not $catalogIblockIds.Contains($iblockId)) {
        return
    }

    if ([string]::IsNullOrWhiteSpace($propertyId)) {
        return
    }

    $properties[$propertyId] = [PSCustomObject][ordered]@{
        legacy_property_id = $propertyId
        legacy_iblock_id   = $iblockId
        property_name      = Get-RowValue -Row $Row -Index 3
        property_code      = $propertyCode
        property_type      = Get-RowValue -Row $Row -Index 8
        multiple           = Get-RowValue -Row $Row -Index 12
        link_iblock_id     = Get-RowValue -Row $Row -Index 17
        filterable         = Get-RowValue -Row $Row -Index 20
        mapping_status     = 'needs_review'
    }
}

$enumLabels = @{}
Invoke-MySqlDumpTable -DumpPath $dumpPath -Table 'b_iblock_property_enum' -ExpectedColumns $expectedTableColumns['b_iblock_property_enum'] -RowHandler {
    param([string[]]$Row)

    $propertyId = Get-RowValue -Row $Row -Index 1
    if (-not $properties.ContainsKey($propertyId)) {
        return
    }

    $enumId = Get-RowValue -Row $Row -Index 0
    if (-not [string]::IsNullOrWhiteSpace($enumId)) {
        $enumLabels[$enumId] = Get-RowValue -Row $Row -Index 2
    }
}

Write-Output 'Pass 5/5: reading raw property values for the selected B2B slice.'
$propertyValues = [System.Collections.Generic.List[object]]::new()
$offerCml2LinksToCatalog = 0
$offerCml2LinksMissingCatalogParent = 0
$offerIdsWithCml2LinkValues = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
$attributePresence = @{}
foreach ($elementId in $matchedSectionsByElement.Keys) {
    $attributePresence[$elementId] = [ordered]@{
        capacity   = $false
        voltage    = $false
        technology = $false
        identity   = $false
    }
}
Invoke-MySqlDumpTable -DumpPath $dumpPath -Table 'b_iblock_element_property' -ExpectedColumns $expectedTableColumns['b_iblock_element_property'] -RowHandler {
    param([string[]]$Row)

    $propertyId = Get-RowValue -Row $Row -Index 1
    $elementId = Get-RowValue -Row $Row -Index 2
    if ($offerCml2LinkPropertyIds.ContainsKey($propertyId) -and $offerElements.ContainsKey($elementId)) {
        [void]$offerIdsWithCml2LinkValues.Add($elementId)
        $parentElementId = Get-RowValue -Row $Row -Index 3
        if ($catalogElements.ContainsKey($parentElementId)) {
            $offerCml2LinksToCatalog++
        }
        else {
            $offerCml2LinksMissingCatalogParent++
        }
        return
    }

    if (-not $matchedSectionsByElement.ContainsKey($elementId) -or -not $properties.ContainsKey($propertyId)) {
        return
    }

    $property = $properties[$propertyId]
    $value = Get-RowValue -Row $Row -Index 3
    $enumId = Get-RowValue -Row $Row -Index 5
    $displayValue = if (-not [string]::IsNullOrWhiteSpace($enumId) -and $enumLabels.ContainsKey($enumId)) { $enumLabels[$enumId] } else { $value }
    $linkResolution = Resolve-ElementLinkValue -Property $property -Value $value -ElementIndexById $elementIndexById
    $hasValue = -not [string]::IsNullOrWhiteSpace($displayValue)
    if ($hasValue) {
        foreach ($kind in @('capacity', 'voltage', 'technology', 'identity')) {
            if (Test-PropertyKind -Property $property -Kind $kind) {
                $attributePresence[$elementId][$kind] = $true
            }
        }
    }

    $propertyValues.Add([PSCustomObject][ordered]@{
        legacy_element_id   = $elementId
        legacy_property_id  = $propertyId
        property_code       = $property.property_code
        property_name       = $property.property_name
        property_type       = $property.property_type
        source_value        = $value
        source_value_enum   = $enumId
        source_value_num    = Get-RowValue -Row $Row -Index 6
        source_value_display = $displayValue
        source_value_resolved_name   = $linkResolution.resolved_name
        source_value_resolved_status = $linkResolution.status
        mapping_status      = 'needs_review'
    })
}

$selectedElements = foreach ($elementId in $matchedSectionsByElement.Keys) {
    $element = $catalogElements[$elementId]
    $matchedSectionIds = @($matchedSectionsByElement[$elementId] | Sort-Object)
    $primaryIsTarget = $targetSectionIds.Contains([string]$element.primary_section_id)
    $membership = if ($primaryIsTarget -and $matchedSectionIds.Count -gt 1) { 'primary_and_additional' } elseif ($primaryIsTarget) { 'primary' } else { 'additional' }
    $primarySectionPath = if ($sections.ContainsKey([string]$element.primary_section_id)) { Get-SectionPath -SectionId ([string]$element.primary_section_id) -Sections $sections -Cache $sectionPathCache } else { '' }
    $matchedSectionPaths = @($matchedSectionIds | ForEach-Object { Get-SectionPath -SectionId $_ -Sections $sections -Cache $sectionPathCache })
    $firstFocusMatchedSectionIds = @($matchedSectionIds | Where-Object { $firstFocusSectionIds.Contains($_) })
    $firstFocusMatchedSectionPaths = @($firstFocusMatchedSectionIds | ForEach-Object { Get-SectionPath -SectionId $_ -Sections $sections -Cache $sectionPathCache })
    $primaryIsFirstFocus = $firstFocusSectionIds.Contains([string]$element.primary_section_id)
    $firstFocusMembership = if ($firstFocusMatchedSectionIds.Count -eq 0) {
        'outside_first_focus'
    }
    elseif ($primaryIsFirstFocus -and $firstFocusMatchedSectionIds.Count -gt 1) {
        'primary_and_additional_first_focus'
    }
    elseif ($primaryIsFirstFocus) {
        'primary_first_focus'
    }
    elseif ($primaryIsTarget) {
        'additional_first_focus_primary_in_other_target_section'
    }
    else {
        'additional_first_focus_primary_outside_target_sections'
    }
    $signals = Get-NameSignals -Name $element.name

    [PSCustomObject][ordered]@{
        legacy_element_id        = $element.legacy_element_id
        legacy_iblock_id         = $element.legacy_iblock_id
        legacy_xml_id            = $element.legacy_xml_id
        legacy_code              = $element.legacy_code
        active                   = $element.active
        name                     = $element.name
        primary_section_id       = $element.primary_section_id
        primary_section_path     = $primarySectionPath
        matched_section_ids      = $matchedSectionIds -join ' | '
        matched_section_paths    = $matchedSectionPaths -join ' | '
        section_membership       = $membership
        is_first_focus_candidate = ([string]($firstFocusMatchedSectionIds.Count -gt 0)).ToLowerInvariant()
        first_focus_membership   = $firstFocusMembership
        first_focus_section_ids  = $firstFocusMatchedSectionIds -join ' | '
        first_focus_section_paths = $firstFocusMatchedSectionPaths -join ' | '
        legacy_url_candidate     = if ($primaryIsTarget -and $primarySectionPath) { "/catalog/$primarySectionPath/$($element.legacy_element_id)/" } else { '' }
        url_candidate_status     = if ($primaryIsTarget) { 'requires_url_registry_match' } else { 'primary_section_is_outside_slice' }
        preview_picture_file_id  = $element.preview_picture_file_id
        detail_picture_file_id   = $element.detail_picture_file_id
        capacity_from_name       = $signals.capacity_from_name
        voltage_from_name        = $signals.voltage_from_name
        technology_from_name     = $signals.technology_from_name
        derived_attribute_status = 'name_signals_only_needs_property_review'
        review_status            = 'needs_review'
    }
}

$duplicateNameCounts = @{}
foreach ($element in $selectedElements) {
    $key = if ([string]::IsNullOrWhiteSpace($element.name)) { '' } else { $element.name.Trim().ToLowerInvariant() }
    if ($duplicateNameCounts.ContainsKey($key)) {
        $duplicateNameCounts[$key]++
    }
    else {
        $duplicateNameCounts[$key] = 1
    }
}

$qualityRows = foreach ($element in $selectedElements) {
    $issues = [System.Collections.Generic.List[string]]::new()
    $presence = $attributePresence[[string]$element.legacy_element_id]
    $nameKey = if ([string]::IsNullOrWhiteSpace($element.name)) { '' } else { $element.name.Trim().ToLowerInvariant() }
    if ($element.active -ne 'Y') { $issues.Add('inactive_source_record') }
    if ([string]::IsNullOrWhiteSpace($element.name)) { $issues.Add('missing_name') }
    if ([string]::IsNullOrWhiteSpace($element.legacy_xml_id)) { $issues.Add('missing_xml_id') }
    if ([string]::IsNullOrWhiteSpace($element.preview_picture_file_id) -and [string]::IsNullOrWhiteSpace($element.detail_picture_file_id)) { $issues.Add('missing_media_reference') }
    if (-not $presence.capacity) { $issues.Add('missing_capacity_property') }
    if (-not $presence.voltage) { $issues.Add('missing_voltage_property') }
    if (-not $presence.technology) { $issues.Add('missing_technology_property') }
    if (-not $presence.identity) { $issues.Add('missing_sku_mpn_article_property') }
    if ($duplicateNameCounts[$nameKey] -gt 1) { $issues.Add('duplicate_name_in_slice') }
    if ($element.legacy_iblock_id -eq '65') { $issues.Add('secondary_catalog_role_unconfirmed') }

    [PSCustomObject][ordered]@{
        legacy_element_id          = $element.legacy_element_id
        legacy_iblock_id           = $element.legacy_iblock_id
        active                     = $element.active
        name                       = $element.name
        section_membership         = $element.section_membership
        has_media_reference        = ([string](-not ($issues -contains 'missing_media_reference'))).ToLowerInvariant()
        has_capacity_property      = ([string]$presence.capacity).ToLowerInvariant()
        has_voltage_property       = ([string]$presence.voltage).ToLowerInvariant()
        has_technology_property    = ([string]$presence.technology).ToLowerInvariant()
        has_sku_mpn_article_property = ([string]$presence.identity).ToLowerInvariant()
        duplicate_name_count       = $duplicateNameCounts[$nameKey]
        issue_codes                = $issues -join ' | '
        review_status              = 'needs_review'
    }
}

# Keep a compact, source-exact media index for the complete catalog alongside
# the narrower B2B audit. This does not approve or publish any image: it only
# preserves the PREVIEW_PICTURE/DETAIL_PICTURE relation of each Bitrix element
# so later category waves do not have to infer media identity from names.
$fullCatalogMediaRows = foreach ($element in $catalogElements.Values) {
    [PSCustomObject][ordered]@{
        legacy_element_id       = $element.legacy_element_id
        legacy_iblock_id        = $element.legacy_iblock_id
        active                   = $element.active
        name                     = $element.name
        primary_section_id       = $element.primary_section_id
        preview_picture_file_id  = $element.preview_picture_file_id
        detail_picture_file_id   = $element.detail_picture_file_id
        has_media_reference      = ([string](-not (
            [string]::IsNullOrWhiteSpace($element.detail_picture_file_id) -and
            [string]::IsNullOrWhiteSpace($element.preview_picture_file_id)
        ))).ToLowerInvariant()
        evidence_status          = 'exact_bitrix_element_media_reference_not_visual_verification'
    }
}

# Preserve the complete catalogue's editorial text separately from the compact
# identity/media index. This is company-owned legacy evidence only: consumers
# must sanitize it, keep the target page noindex and must not treat the copy as
# manufacturer-verified technical facts.
$fullCatalogContentRows = foreach ($element in $catalogElements.Values) {
    [PSCustomObject][ordered]@{
        legacy_element_id  = $element.legacy_element_id
        legacy_iblock_id   = $element.legacy_iblock_id
        active              = $element.active
        name                = $element.name
        preview_text_type   = $element.preview_text_type
        preview_text        = $element.preview_text
        detail_text_type    = $element.detail_text_type
        detail_text         = $element.detail_text
        has_preview_text    = ([string](-not [string]::IsNullOrWhiteSpace($element.preview_text))).ToLowerInvariant()
        has_detail_text     = ([string](-not [string]::IsNullOrWhiteSpace($element.detail_text))).ToLowerInvariant()
        evidence_status     = 'company_owned_legacy_text_requires_sanitization_noindex_only'
    }
}

# Keep legacy editorial fields in a separate evidence artifact. They are not
# trusted product facts and must never be rendered or applied directly. The
# later staging builder sanitizes and reviews them while preserving provenance.
$contentRows = foreach ($element in $selectedElements) {
    $sourceElement = $catalogElements[[string]$element.legacy_element_id]
    [PSCustomObject][ordered]@{
        legacy_element_id  = $element.legacy_element_id
        legacy_iblock_id   = $element.legacy_iblock_id
        active              = $element.active
        name                = $element.name
        preview_text_type   = $sourceElement.preview_text_type
        preview_text        = $sourceElement.preview_text
        detail_text_type    = $sourceElement.detail_text_type
        detail_text         = $sourceElement.detail_text
        searchable_content  = $sourceElement.searchable_content
        has_preview_text    = ([string](-not [string]::IsNullOrWhiteSpace($sourceElement.preview_text))).ToLowerInvariant()
        has_detail_text     = ([string](-not [string]::IsNullOrWhiteSpace($sourceElement.detail_text))).ToLowerInvariant()
        evidence_status     = 'legacy_untrusted_requires_sanitization_and_review'
    }
}

$elementLinkPropertyValues = @($propertyValues | Where-Object { $_.source_value_resolved_status -ne 'not_applicable' })
$elementLinkResolvedCount = @($elementLinkPropertyValues | Where-Object { $_.source_value_resolved_status -eq 'resolved' }).Count
$elementLinkEmptyCount = @($elementLinkPropertyValues | Where-Object { $_.source_value_resolved_status -eq 'empty' }).Count
$elementLinkNotFoundCount = @($elementLinkPropertyValues | Where-Object { $_.source_value_resolved_status -eq 'not_found' }).Count
$elementLinkIblockMismatchCount = @($elementLinkPropertyValues | Where-Object { $_.source_value_resolved_status -eq 'iblock_mismatch' }).Count
$elementLinkScopeUnverifiableCount = @($elementLinkPropertyValues | Where-Object { $_.source_value_resolved_status -eq 'scope_unverifiable' }).Count
$elementLinkNameMissingCount = @($elementLinkPropertyValues | Where-Object { $_.source_value_resolved_status -eq 'name_missing' }).Count

$firstFocusRows = @($selectedElements | Where-Object { $_.is_first_focus_candidate -eq 'true' })
$firstFocusPrimaryRows = @($firstFocusRows | Where-Object { $_.first_focus_membership -like 'primary_*' })
$firstFocusAdditionalFromOtherTargetRows = @($firstFocusRows | Where-Object { $_.first_focus_membership -eq 'additional_first_focus_primary_in_other_target_section' })
$firstFocusAdditionalFromOutsideTargetRows = @($firstFocusRows | Where-Object { $_.first_focus_membership -eq 'additional_first_focus_primary_outside_target_sections' })
$offerElementTotal = ($offerElementCounts.Values | Measure-Object -Sum).Sum
$offerActiveElementTotal = ($offerActiveElementCounts.Values | Measure-Object -Sum).Sum
$reviewedOutOfScopeOfferCount = @($offerElements.Keys | Where-Object {
    $offer = $offerElements[$_]
    $reviewedOutOfScopeOfferIds.Contains($_) -and $offer.legacy_iblock_id -eq '67' -and -not $offerIdsWithCml2LinkValues.Contains($_)
}).Count
$unreviewedOfferIds = @($offerElements.Keys | Where-Object {
    $offer = $offerElements[$_]
    -not ($reviewedOutOfScopeOfferIds.Contains($_) -and $offer.legacy_iblock_id -eq '67' -and -not $offerIdsWithCml2LinkValues.Contains($_))
})
$offerDetectionStatus = if ($unreviewedOfferIds.Count -gt 0) {
    'blocked_offer_infoblocks_require_reconciliation'
}
elseif ($reviewedOutOfScopeOfferCount -gt 0) {
    'reviewed_orphan_offers_outside_b2b_scope'
}
else {
    'no_offer_elements_in_snapshot'
}

$sourceSnapshot = [PSCustomObject][ordered]@{
    generated_at_utc             = [DateTime]::UtcNow.ToString('o')
    source_dump                  = $dumpPath
    source_snapshot_date         = '2026-06-23'
    extractor_mode               = 'read_only_no_database_no_network_no_publish'
    catalog_infoblocks           = @('26', '65')
    offer_infoblocks_checked     = @('28', '67')
    offer_infoblock_28_elements  = $offerElementCounts['28']
    offer_infoblock_28_active_elements = $offerActiveElementCounts['28']
    offer_infoblock_67_elements  = $offerElementCounts['67']
    offer_infoblock_67_active_elements = $offerActiveElementCounts['67']
    offer_cml2_link_properties_detected = $offerCml2LinkPropertyIds.Count
    offer_cml2_links_to_catalog   = $offerCml2LinksToCatalog
    offer_cml2_links_missing_catalog_parent = $offerCml2LinksMissingCatalogParent
    reviewed_out_of_scope_offer_count = $reviewedOutOfScopeOfferCount
    unreviewed_offer_count       = $unreviewedOfferIds.Count
    offer_detection_status        = $offerDetectionStatus
    target_keyword_sections      = $directTargetSectionIds.Count
    target_sections_with_children = $targetSectionIds.Count
    selected_products            = @($selectedElements).Count
    selected_active_products     = @($selectedElements | Where-Object active -eq 'Y').Count
    selected_inactive_products   = @($selectedElements | Where-Object active -ne 'Y').Count
    selected_from_iblock_26      = @($selectedElements | Where-Object legacy_iblock_id -eq '26').Count
    selected_from_iblock_65      = @($selectedElements | Where-Object legacy_iblock_id -eq '65').Count
    full_catalog_elements        = @($fullCatalogMediaRows).Count
    full_catalog_active_elements = @($fullCatalogMediaRows | Where-Object active -eq 'Y').Count
    full_catalog_with_media_reference = @($fullCatalogMediaRows | Where-Object has_media_reference -eq 'true').Count
    full_catalog_with_preview_text = @($fullCatalogContentRows | Where-Object has_preview_text -eq 'true').Count
    full_catalog_with_detail_text = @($fullCatalogContentRows | Where-Object has_detail_text -eq 'true').Count
    first_focus_products_any_section_membership = $firstFocusRows.Count
    first_focus_products_primary_section_membership = $firstFocusPrimaryRows.Count
    first_focus_products_additional_membership_primary_in_other_target_section = $firstFocusAdditionalFromOtherTargetRows.Count
    first_focus_products_additional_membership_primary_outside_target_sections = $firstFocusAdditionalFromOutsideTargetRows.Count
    raw_property_values          = $propertyValues.Count
    element_link_property_values = $elementLinkPropertyValues.Count
    element_link_resolved        = $elementLinkResolvedCount
    element_link_empty           = $elementLinkEmptyCount
    element_link_not_found       = $elementLinkNotFoundCount
    element_link_iblock_mismatch = $elementLinkIblockMismatchCount
    element_link_scope_unverifiable = $elementLinkScopeUnverifiableCount
    element_link_name_missing    = $elementLinkNameMissingCount
    without_media_reference      = @($qualityRows | Where-Object { $_.issue_codes -match 'missing_media_reference' }).Count
    without_identity_property    = @($qualityRows | Where-Object { $_.issue_codes -match 'missing_sku_mpn_article_property' }).Count
    with_preview_text             = @($contentRows | Where-Object has_preview_text -eq 'true').Count
    with_detail_text              = @($contentRows | Where-Object has_detail_text -eq 'true').Count
    review_status                = 'all_rows_need_review'
}

Write-Output "First-focus candidates: $($sourceSnapshot.first_focus_products_any_section_membership) total by any section membership; $($sourceSnapshot.first_focus_products_primary_section_membership) primary; $($sourceSnapshot.first_focus_products_additional_membership_primary_in_other_target_section) additional from another target section; $($sourceSnapshot.first_focus_products_additional_membership_primary_outside_target_sections) additional from outside the target slice."
Write-Output "Offer infoblocks 28/67: $offerElementTotal elements ($offerActiveElementTotal active), $($offerCml2LinkPropertyIds.Count) CML2_LINK properties, $offerCml2LinksToCatalog links to catalog parents; $reviewedOutOfScopeOfferCount reviewed out-of-scope, $($unreviewedOfferIds.Count) unreviewed."
Write-Output "Element-link (type E) property values: $($elementLinkPropertyValues.Count) total, $elementLinkResolvedCount resolved to a source element name, $elementLinkEmptyCount empty, $elementLinkNotFoundCount not found, $elementLinkIblockMismatchCount iblock mismatches, $elementLinkScopeUnverifiableCount scope unverifiable, $elementLinkNameMissingCount with a missing name."

if ($unreviewedOfferIds.Count -gt 0) {
    throw "Offer infoblocks 28/67 contain $($unreviewedOfferIds.Count) unreviewed elements ($offerActiveElementTotal active total; CML2_LINK properties: $($offerCml2LinkPropertyIds.Count); links to catalog: $offerCml2LinksToCatalog). Reconcile offers before treating infoblocks 26/65 as complete. No output was written."
}

if (-not $PSCmdlet.ShouldProcess($OutputDir, 'write generated B2B catalog audit CSV and JSON artifacts')) {
    Write-Output "WhatIf: parsed $($sourceSnapshot.selected_products) broad candidates and $($sourceSnapshot.first_focus_products_any_section_membership) first-focus candidates; no output was written."
    return
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null
@($targetSectionRows | Sort-Object legacy_iblock_id, source_section_path) |
    Export-Csv -LiteralPath (Join-Path $OutputDir 'bitrix-b2b-catalog-sections.csv') -NoTypeInformation -Encoding utf8
@($selectedElements | Sort-Object legacy_iblock_id, legacy_element_id) |
    Export-Csv -LiteralPath (Join-Path $OutputDir 'bitrix-b2b-catalog-products.csv') -NoTypeInformation -Encoding utf8
@($fullCatalogMediaRows | Sort-Object legacy_iblock_id, legacy_element_id) |
    Export-Csv -LiteralPath (Join-Path $OutputDir 'bitrix-full-catalog-media-index.csv') -NoTypeInformation -Encoding utf8
@($fullCatalogContentRows | Sort-Object legacy_iblock_id, legacy_element_id) |
    Export-Csv -LiteralPath (Join-Path $OutputDir 'bitrix-full-catalog-content.csv') -NoTypeInformation -Encoding utf8
@($properties.Values | Sort-Object legacy_iblock_id, property_name) |
    Export-Csv -LiteralPath (Join-Path $OutputDir 'bitrix-b2b-catalog-properties.csv') -NoTypeInformation -Encoding utf8
@($propertyValues | Sort-Object legacy_element_id, legacy_property_id) |
    Export-Csv -LiteralPath (Join-Path $OutputDir 'bitrix-b2b-catalog-property-values.csv') -NoTypeInformation -Encoding utf8
@($qualityRows | Sort-Object legacy_iblock_id, legacy_element_id) |
    Export-Csv -LiteralPath (Join-Path $OutputDir 'bitrix-b2b-catalog-quality.csv') -NoTypeInformation -Encoding utf8
@($contentRows | Sort-Object legacy_iblock_id, legacy_element_id) |
    Export-Csv -LiteralPath (Join-Path $OutputDir 'bitrix-b2b-catalog-content.csv') -NoTypeInformation -Encoding utf8
$sourceSnapshot | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDir 'bitrix-b2b-catalog-summary.json') -Encoding utf8

Write-Output "Created read-only B2B audit artifacts in $OutputDir"
Write-Output "Selected products: $($sourceSnapshot.selected_products) (active: $($sourceSnapshot.selected_active_products))"
Write-Output "Raw property values: $($sourceSnapshot.raw_property_values)"
