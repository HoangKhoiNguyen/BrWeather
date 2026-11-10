# Week-1 data gate check (OpenAQ PM2.5).
# Reads OPENAQ_API_KEY from the environment or from the repo's .env file; the key is never printed.
#
#   Level 1 (enough to run the pipeline): span >= 90 days and >= 80% of hours present in the last 90 days
#   Level 2 (enough to draw conclusions on models): span >= 180 days, >= 80% of hours present over the span,
#            and >= 720 hours (30 days) present in Nov-Mar (pollution season)
#
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\check_data_gate.ps1
#         powershell -ExecutionPolicy Bypass -File scripts\check_data_gate.ps1 -StationIds 2161306,7441 -Days 730

param(
    [long[]]$StationIds = @(2161306, 2161292, 4946812, 4946813, 6123215),
    [int]$Days = 365
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.Encoding]::UTF8

# --- API key -------------------------------------------------------------
$key = $env:OPENAQ_API_KEY
if (-not $key) {
    $envFile = Join-Path (Split-Path $PSScriptRoot -Parent) '.env'
    if (Test-Path $envFile) {
        foreach ($line in Get-Content $envFile) {
            if ($line -match '^\s*OPENAQ_API_KEY\s*=\s*(.+?)\s*$') { $key = $Matches[1] }
        }
    }
}
if (-not $key) { throw 'OPENAQ_API_KEY not found. Set it in .env (copy .env.example) or as an environment variable.' }

# --- HTTP helper: UTF-8 decode, 1.1 s spacing, wait on 429 ----------------
$script:lastCall = [DateTime]::MinValue
function Get-OpenAQ([string]$path) {
    for ($try = 0; $try -lt 3; $try++) {
        $wait = 1100 - ([DateTime]::UtcNow - $script:lastCall).TotalMilliseconds
        if ($wait -gt 0) { Start-Sleep -Milliseconds ([int]$wait) }
        $script:lastCall = [DateTime]::UtcNow
        try {
            $resp = Invoke-WebRequest -UseBasicParsing -Uri ("https://api.openaq.org/v3" + $path) -Headers @{ 'X-API-Key' = $key }
            return [Text.Encoding]::UTF8.GetString($resp.RawContentStream.ToArray()) | ConvertFrom-Json
        } catch {
            if ($_.Exception.Response -and [int]$_.Exception.Response.StatusCode -eq 429) {
                Write-Host '  rate limited, waiting 60 s...'
                Start-Sleep -Seconds 60
                continue
            }
            throw
        }
    }
    throw "OpenAQ kept rate limiting $path"
}

function To-Utc([string]$s) { [DateTimeOffset]::Parse($s).UtcDateTime }

$now = [DateTime]::UtcNow
$rows = @()

foreach ($id in $StationIds) {
    $loc = (Get-OpenAQ "/locations/$id").results[0]
    $sensor = $loc.sensors | Where-Object { $_.parameter.name -eq 'pm25' } | Select-Object -First 1
    if (-not $sensor -or -not $loc.datetimeLast) {
        $rows += [pscustomobject]@{ Id = $id; Name = $loc.name; Note = 'no PM2.5 sensor or no data' }
        continue
    }

    $first = To-Utc $loc.datetimeFirst.utc
    $last = To-Utc $loc.datetimeLast.utc
    $from = if ($first -gt $now.AddDays(-$Days)) { $first } else { $now.AddDays(-$Days) }
    Write-Host ("Station {0} ({1}): downloading {2:yyyy-MM-dd} to {3:yyyy-MM-dd}..." -f $id, $loc.name, $from, $last)

    $hours = New-Object System.Collections.Generic.List[DateTime]
    $page = 1
    do {
        $q = "/sensors/$($sensor.id)/hours?datetime_from=$($from.ToString('yyyy-MM-ddTHH:mm:ssZ'))&datetime_to=$($last.ToString('yyyy-MM-ddTHH:mm:ssZ'))&limit=1000&page=$page"
        $res = (Get-OpenAQ $q).results
        foreach ($r in $res) { if ($null -ne $r.value) { $hours.Add((To-Utc $r.period.datetimeFrom.utc)) } }
        $page++
    } while ($res.Count -eq 1000)

    $sorted = $hours | Sort-Object
    $spanHours = [Math]::Max(1, ($last - $from).TotalHours)
    $spanDays = ($last - $first).TotalDays
    $from90 = $last.AddDays(-90)
    $in90 = @($sorted | Where-Object { $_ -ge $from90 }).Count
    $winter = @($sorted | Where-Object { $_.Month -ge 11 -or $_.Month -le 3 }).Count

    $longestGap = 0
    for ($i = 1; $i -lt $sorted.Count; $i++) {
        $gap = ($sorted[$i] - $sorted[$i - 1]).TotalHours
        if ($gap -gt $longestGap) { $longestGap = $gap }
    }

    $pctSpan = [Math]::Round(100 * $sorted.Count / $spanHours, 1)
    $pct90 = [Math]::Round(100 * $in90 / [Math]::Min(2160, $spanHours), 1)
    $level1 = ($spanDays -ge 90) -and ($pct90 -ge 80)
    $level2 = ($spanDays -ge 180) -and ($pctSpan -ge 80) -and ($winter -ge 720)

    $rows += [pscustomobject]@{
        Id            = $id
        Name          = $loc.name
        Provider      = $loc.provider.name
        FirstUtc      = $first.ToString('yyyy-MM-dd')
        LastUtc       = $last.ToString('yyyy-MM-dd')
        HoursPresent  = $sorted.Count
        PctLast90d    = $pct90
        PctWindow     = $pctSpan
        WinterHours   = $winter
        LongestGapH   = [Math]::Round($longestGap)
        Level1        = if ($level1) { 'PASS' } else { 'fail' }
        Level2        = if ($level2) { 'PASS' } else { 'fail' }
    }
}

$out = Join-Path $PSScriptRoot 'data_gate_result.csv'
$rows | Export-Csv $out -NoTypeInformation -Encoding UTF8
$rows | Format-Table Id, Level1, Level2, PctLast90d, PctWindow, WinterHours, LongestGapH, FirstUtc, LastUtc -AutoSize
Write-Host "Window checked: last $Days days. Full table (with names and providers): $out"
