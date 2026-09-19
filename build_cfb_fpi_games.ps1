# Build CSV: one row per team per game with ESPN FPI (FBS). Data sources:
# - FPI: site.web.api.espn.com .../powerindex?season=2026
# - Games: site.api.espn.com .../scoreboard?dates=YYYYMMDD&groups=80

$SeasonYear = 2026
$ErrorActionPreference = 'Stop'
$Base = if ($env:CFB_DATA_ROOT) { $env:CFB_DATA_ROOT } else { Split-Path $PSScriptRoot -Parent }
$headers = @{
    'User-Agent' = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    'Accept'     = 'application/json'
}

function Get-JsonFromCurl {
    param([string]$Url)
    $raw = & curl.exe -sS $Url
    if (-not $raw) {
        throw "Empty response from curl for $Url"
    }
    return ($raw | ConvertFrom-Json)
}

function Get-FpiMap {
    param([hashtable]$Hdr, [int]$Year)
    $url = "https://site.web.api.espn.com/apis/fitt/v3/sports/football/college-football/powerindex?region=us&lang=en&season=$Year&sort=fpi.fpi%3Adesc&limit=1000"
    $j = Get-JsonFromCurl -Url $url
    $map = @{}
    foreach ($entry in $j.teams) {
        $tid = [string]$entry.team.id
        $fpi = $null
        foreach ($cat in $entry.categories) {
            if ($cat.name -eq 'fpi' -and $cat.values -and $cat.values.Count -gt 0) {
                $fpi = $cat.values[0]
                break
            }
        }
        $map[$tid] = $fpi
    }
    return $map
}

function Get-ScoreboardDay {
    param([string]$DateStr, [hashtable]$Hdr)
    $url = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard?dates=$DateStr&groups=80&limit=400"
    return Get-JsonFromCurl -Url $url
}

# Overrides for non-FBS / missing ESPN FPI: NDSU, Sacramento State, then default for null
function Resolve-Fpi {
    param([string]$DisplayName, $RawFpi)
    if ($DisplayName -match 'North Dakota State') { return 1 }
    if ($DisplayName -match 'Sacramento State') { return -20 }
    if ($null -eq $RawFpi) { return -36 }
    return $RawFpi
}

$fpiByTeam = Get-FpiMap -Hdr $headers -Year $SeasonYear

# College "2026" season: late Aug 2026 through title game in Jan 2027
$start = [datetime]'2026-08-20'
$end   = [datetime]'2027-01-26'
$gamesById = [ordered]@{}

for ($d = $start; $d -le $end; $d = $d.AddDays(1)) {
    $ds = $d.ToString('yyyyMMdd')
    try {
        $sb = Get-ScoreboardDay -DateStr $ds -Hdr $headers
        if (-not $sb.events) { continue }
        foreach ($ev in $sb.events) {
            if ($ev.season -and [int]$ev.season.year -ne $SeasonYear) { continue }
            $gid = [string]$ev.id
            if (-not $gamesById.Contains($gid)) {
                $gamesById[$gid] = $ev
            }
        }
    }
    catch {
        Write-Warning "Scoreboard failed for $ds : $_"
    }
    Start-Sleep -Milliseconds 80
}

$rows = New-Object System.Collections.Generic.List[object]

foreach ($gid in $gamesById.Keys) {
    $ev = $gamesById[$gid]
    $comp = $ev.competitions[0]
    $neutral = $comp.neutralSite
    $wk = if ($ev.week) { $ev.week.number } else { '' }
    $seasonSlug = if ($ev.season) { $ev.season.slug } else { '' }
    $seasonYear = if ($ev.season) { $ev.season.year } else { '' }

    foreach ($side in $comp.competitors) {
        $tid = [string]$side.team.id
        $oid = $null
        $oname = $null
        foreach ($other in $comp.competitors) {
            if ([string]$other.team.id -ne $tid) {
                $oid = [string]$other.team.id
                $oname = $other.team.displayName
                break
            }
        }
        $tfpiRaw = $fpiByTeam[$tid]
        $ofpiRaw = if ($oid) { $fpiByTeam[$oid] } else { $null }
        $tfpi = Resolve-Fpi -DisplayName $side.team.displayName -RawFpi $tfpiRaw
        $ofpi = if ($oname) { Resolve-Fpi -DisplayName $oname -RawFpi $ofpiRaw } else { $ofpiRaw }

        # Expected margin: team FPI - opp FPI +3 home / -3 away (no HFA at neutral site)
        $hfa = 0
        if (-not $neutral) {
            if ($side.homeAway -eq 'home') { $hfa = 3 }
            elseif ($side.homeAway -eq 'away') { $hfa = -3 }
        }
        $expectedMargin = $null
        if ($null -ne $tfpi -and $null -ne $ofpi) {
            $expectedMargin = [math]::Round([double]$tfpi - [double]$ofpi + $hfa, 3)
        }

        $rows.Add([pscustomobject]@{
            game_id                    = $gid
            game_date_utc              = $ev.date
            season_year                = $seasonYear
            week                       = $wk
            season_type                = $seasonSlug
            neutral_site               = $neutral
            team_id                    = $tid
            team_name                  = $side.team.displayName
            home_away                  = $side.homeAway
            opponent_id                = $oid
            opponent_name              = $oname
            team_fpi                   = $tfpi
            opponent_fpi               = $ofpi
            expected_margin_of_victory = $expectedMargin
            team_score                 = $side.score
            opponent_score             = ($comp.competitors | Where-Object { [string]$_.team.id -ne $tid } | Select-Object -First 1 -ExpandProperty score)
            game_completed             = $comp.status.type.completed
        })
    }
}

if ($gamesById.Count -eq 0) {
    throw "No games collected from ESPN scoreboards; refusing to overwrite schedule CSV."
}

$outPath = Join-Path $Base 'cfb_2026_fbs_games_with_fpi.csv'
$altPath = Join-Path $Base 'cfb_2026_fbs_games_with_fpi_margin.csv'
$sorted = $rows | Sort-Object game_date_utc, game_id, team_id
$tmpPath = Join-Path ([System.IO.Path]::GetTempPath()) ("cfb_fpi_{0}.csv" -f [guid]::NewGuid().ToString('n'))
$sorted | Export-Csv -Path $tmpPath -NoTypeInformation -Encoding UTF8
try {
    Copy-Item -LiteralPath $tmpPath -Destination $outPath -Force -ErrorAction Stop
    Remove-Item -LiteralPath $tmpPath -Force
    Write-Host "Wrote $($rows.Count) rows ($($gamesById.Count) unique games) to $outPath"
}
catch {
    Copy-Item -LiteralPath $tmpPath -Destination $altPath -Force -ErrorAction Stop
    Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue
    Write-Warning "Could not update $outPath (file may be open). Wrote to $altPath instead."
}
Write-Host "FPI teams loaded: $($fpiByTeam.Count)"
