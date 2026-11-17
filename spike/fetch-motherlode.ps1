# fetch-motherlode.ps1 - the cargo grid catalog of Motherlode (cryon.rocks) and the ship models (.glb).
# Run in a native PowerShell window:  cd <this repo>; .\fetch-motherlode.ps1
# The operators allowed the use of catalog and models (SC-CargoPlan v0.3.0, session 4). The models are measured and
# turned into holograms and outlines, never shipped as they are.
#
# Sources (SC-CargoPlan session 4b):
#   grids   GET https://cryon.rocks/api/public/v1/cargo-grids, header "Authorization: Bearer <key>". One run makes exactly
#           one API request; a 429 stops the run with its Retry-After, nothing is asked again. The answer is the catalog
#           format below and names the game build (gameBuild), which the import writes into the ships' "source".
#   models  the page https://cryon.rocks/ops/cargo (header "RSC: 1", its React Server Component stream holds a "ships"
#           array) for modelUrl only, until the API lists the models. Joined by className, the model file's name before
#           "-<hash>.glb".
# API key: environment variable MOTHERLODE_API_KEY, else motherlode/api-key.txt (gitignored). It is only read: never in
# this script, never written to a log or to the console.
#
# Output (motherlode/, an archive: files of a day that exists are never overwritten, the run stops before any request):
#   api-<date>.json      the API's answer byte for byte          + api-<date>.sha256
#   page-<date>.json     the page's "ships" array                + page-<date>.sha256
#   catalog-<date>.json  the API's catalog with modelUrl joined  + catalog-<date>.sha256 (what tools/import-motherlode.ps1 reads)
#                        { gameBuild, updatedAt, ships: [ { id, className, name, manufacturer, cargoScu, containerSizes,
#                        grids: [ { name, scu, size, containerSizes, maxContainerScu, external, transform } ], modelUrl? } ] }
#   models/<file>.glb    the models, existing ones are skipped   + models-<date>.sha256
# An answer out of this format stops the run before anything is written.
# Offline (tests, a rerun from the archive): -ApiResponse and -PageResponse read saved answers instead; -OutDir, -SkipModels.
# Runs under Windows PowerShell 5.1 and PowerShell 7. ASCII only: 5.1 reads a script without BOM as ANSI.

param(
    [string]$ApiResponse,
    [string]$PageResponse,
    # Default motherlode/ next to this script, set below: Windows PowerShell 5.1 leaves $PSScriptRoot empty in defaults.
    [string]$OutDir,
    [switch]$SkipModels
)
$ErrorActionPreference = 'Stop'
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot 'motherlode' }
$ApiUrl  = 'https://cryon.rocks/api/public/v1/cargo-grids'
$PageUrl = 'https://cryon.rocks/ops/cargo'
$KeyFile = Join-Path (Join-Path $PSScriptRoot 'motherlode') 'api-key.txt'
$BuildPattern = '^\d+\.\d+(\.\d+)?-[A-Z]+\.\d+$'
$UserAgent = 'sc-cargoplan-outlines/0.2 (fan project)'
$date  = Get-Date -Format 'yyyy-MM-dd'
$noBom = New-Object Text.UTF8Encoding $false

function Get-ApiKey {
    $key = $env:MOTHERLODE_API_KEY
    if (-not $key -and (Test-Path -LiteralPath $KeyFile -PathType Leaf)) { $key = [IO.File]::ReadAllText($KeyFile) }
    if ($key) { $key = $key.Trim() }
    if (-not $key) { throw "No API key: set MOTHERLODE_API_KEY or write it to motherlode/api-key.txt." }
    $key
}

# The one API request. Messages are written here, never taken from the request: they must not carry the header.
function Get-ApiBytes {
    $key = Get-ApiKey
    try {
        $resp = Invoke-WebRequest -Uri $ApiUrl -Headers @{ 'Authorization' = "Bearer $key"; 'User-Agent' = $UserAgent } -UseBasicParsing
    }
    catch {
        $key = $null
        $r = $_.Exception.Response
        if ($null -eq $r) { throw "API request to $ApiUrl failed without an answer (network?)." }
        $code = [int]$r.StatusCode
        if ($code -eq 429) {
            $after = if ($r.Headers -is [Net.WebHeaderCollection]) { $r.Headers['Retry-After'] } else { "$($r.Headers.RetryAfter)" }
            throw "API: 429 Too Many Requests, Retry-After: $after. One request per run: run again after that."
        }
        throw "API answered HTTP $code."
    }
    $key = $null
    , $resp.RawContentStream.ToArray()
}

function Get-PageText {
    $resp = Invoke-WebRequest -Uri $PageUrl -Headers @{ 'User-Agent' = $UserAgent; 'RSC' = '1' } -UseBasicParsing
    [Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray())
}

# The page's "ships" array as text: brackets counted, strings skipped, since names could hold brackets.
function Get-ShipsArrayText([string]$Text) {
    $marker = '"ships":['
    $start = $Text.IndexOf($marker)
    if ($start -lt 0) { throw "No $marker in the page's answer - page format changed?" }
    $start += $marker.Length - 1
    $depth = 0; $inString = $false; $escape = $false
    for ($k = $start; $k -lt $Text.Length; $k++) {
        $c = $Text[$k]
        if ($inString) {
            if ($escape) { $escape = $false } elseif ($c -eq '\') { $escape = $true } elseif ($c -eq '"') { $inString = $false }
            continue
        }
        if ($c -eq '"') { $inString = $true }
        elseif ($c -eq '[' -or $c -eq '{') { $depth++ }
        elseif ($c -eq ']' -or $c -eq '}') { $depth--; if ($depth -eq 0) { return $Text.Substring($start, $k - $start + 1) } }
    }
    throw "The page's ships array has no end - answer cut off?"
}

function Get-ClassName([string]$ModelUrl) { (($ModelUrl -split '/')[-1]) -replace '-[0-9a-f]+\.glb$', '' }

# The API's answer against the catalog format; any field out of it stops the run.
function Assert-Catalog([object]$Api) {
    if (-not ($Api.gameBuild -is [string] -and $Api.gameBuild -match $BuildPattern)) { throw "API answer: gameBuild missing or not like 4.10.2-LIVE.12913470." }
    if (-not $Api.updatedAt) { throw "API answer: updatedAt missing." }
    if (@($Api.ships).Count -eq 0) { throw "API answer: no ships." }
    foreach ($s in @($Api.ships)) {
        if (-not $s.name) { throw "API answer: a ship without name." }
        if ($null -eq $s.grids -or $s.grids -is [string]) { throw "API answer: $($s.name) has no grids list." }
        foreach ($g in @($s.grids)) {
            if (@($g.size).Count -ne 3) { throw "API answer: $($s.name)/$($g.name): size has not 3 values." }
            if ($null -ne $g.transform -and @($g.transform).Count -ne 12) { throw "API answer: $($s.name)/$($g.name): transform has not 12 values." }
        }
    }
}

function Write-Archived([string]$Name, [byte[]]$Bytes) {
    $path = Join-Path $OutDir $Name
    [IO.File]::WriteAllBytes($path, $Bytes)
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText((Join-Path $OutDir ([IO.Path]::ChangeExtension($Name, '.sha256'))), "$hash  $Name`n", $noBom)
    $hash
}

try {
    # 1) The archive of a day is never overwritten: checked before any request.
    foreach ($kind in 'api', 'page', 'catalog') {
        if (Test-Path -LiteralPath (Join-Path $OutDir "$kind-$date.json")) { throw "An archive of $date exists ($kind-$date.json); it is never overwritten. Run again tomorrow." }
    }

    # 2) Grids from the API, model URLs from the page; everything checked before anything is written.
    $apiBytes = if ($ApiResponse) { [IO.File]::ReadAllBytes($ApiResponse) } else { Get-ApiBytes }
    # Assign first, then @(): Windows PowerShell 5.1 passes a JSON array on as ONE object.
    $api = [Text.Encoding]::UTF8.GetString($apiBytes) | ConvertFrom-Json
    Assert-Catalog $api
    Write-Host "API: $(@($api.ships).Count) ships, game build $($api.gameBuild), updated $($api.updatedAt)"

    $pageText = if ($PageResponse) { [IO.File]::ReadAllText($PageResponse) } else { Get-PageText }
    $pageShipsText = Get-ShipsArrayText $pageText
    $pageShips = $pageShipsText | ConvertFrom-Json
    $models = @{}
    foreach ($p in @($pageShips)) { if ($p.modelUrl) { $models[(Get-ClassName $p.modelUrl)] = [string]$p.modelUrl } }
    Write-Host "Page: $(@($pageShips).Count) entries, $($models.Count) models"

    # 3) The catalog: the API's ships as they come, modelUrl joined by className.
    $joined = @{}
    $ships = foreach ($s in @($api.ships)) {
        $ship = [ordered]@{}
        foreach ($p in $s.PSObject.Properties) { if ($p.Name -ne 'modelUrl') { $ship[$p.Name] = $p.Value } }
        if ($s.className -and $models.ContainsKey([string]$s.className)) {
            $ship['modelUrl'] = $models[[string]$s.className]; $joined[[string]$s.className] = $true
        }
        elseif ($s.className) { Write-Host "  no model on the page for $($s.className) ($($s.name))" }
        [pscustomobject]$ship
    }
    foreach ($c in @($models.Keys | Sort-Object)) { if (-not $joined.ContainsKey($c)) { Write-Host "  model on the page without an API ship: $c" } }
    $catalog = [pscustomobject][ordered]@{ gameBuild = $api.gameBuild; updatedAt = $api.updatedAt; ships = @($ships) }

    # 4) Write the archive.
    New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
    $null = Write-Archived "api-$date.json" $apiBytes
    $null = Write-Archived "page-$date.json" $noBom.GetBytes($pageShipsText)
    $hash = Write-Archived "catalog-$date.json" $noBom.GetBytes(($catalog | ConvertTo-Json -Depth 8))
    Write-Host ("Catalog {0} ({1}): {2} ships, {3} with a model, SHA-256 {4}" -f $date, $api.gameBuild, @($ships).Count,
        @($ships | Where-Object { $_.modelUrl }).Count, $hash)

    # 5) Models and their hash list.
    if (-not $SkipModels) {
        $modelDir = Join-Path $OutDir 'models'
        New-Item -ItemType Directory -Force -Path $modelDir | Out-Null
        $list = @($ships | Where-Object { $_.modelUrl } | ForEach-Object { $_.modelUrl } | Sort-Object -Unique)
        $lines = New-Object System.Collections.Generic.List[string]
        $i = 0
        foreach ($modelUrl in $list) {
            $i++
            $name = ($modelUrl -split '/')[-1]
            $file = Join-Path $modelDir $name
            if (-not (Test-Path -LiteralPath $file)) {
                Invoke-WebRequest -Uri $modelUrl -OutFile $file -Headers @{ 'User-Agent' = $UserAgent } -UseBasicParsing
                Start-Sleep -Milliseconds 200
            }
            $lines.Add(('{0}  models/{1}' -f (Get-FileHash -Algorithm SHA256 -LiteralPath $file).Hash.ToLowerInvariant(), $name))
            Write-Host ("[{0}/{1}] {2}" -f $i, $list.Count, $name)
        }
        [IO.File]::WriteAllText((Join-Path $OutDir "models-$date.sha256"), (($lines -join "`n") + "`n"), $noBom)
    }
    Write-Host "Done. Files in $OutDir"
    exit 0
}
catch {
    [Console]::Error.WriteLine("fetch-motherlode: $($_.Exception.Message)")
    exit 1
}
