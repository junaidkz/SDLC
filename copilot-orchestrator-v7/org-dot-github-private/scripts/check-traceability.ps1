param(
    [string]$RequirementsPath = "docs/requirements.md",
    [string]$TraceabilityPath = "docs/traceability.md"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $RequirementsPath)) {
    Write-Error "Missing requirements file: $RequirementsPath"
}
if (-not (Test-Path -LiteralPath $TraceabilityPath)) {
    Write-Error "Missing traceability file: $TraceabilityPath"
}

$requirementsText = Get-Content -Raw -LiteralPath $RequirementsPath
$traceLines = Get-Content -LiteralPath $TraceabilityPath

$reqHeaderRegex = '(?m)^##\s+(REQ-[A-Z]+-\d{3})\s*$'
$reqMatches = [regex]::Matches($requirementsText, $reqHeaderRegex)

if ($reqMatches.Count -eq 0) {
    Write-Error "No REQ entries found in $RequirementsPath"
}

$requirements = @()
for ($i = 0; $i -lt $reqMatches.Count; $i++) {
    $start = $reqMatches[$i].Index
    $end = if ($i -lt $reqMatches.Count - 1) { $reqMatches[$i + 1].Index } else { $requirementsText.Length }
    $block = $requirementsText.Substring($start, $end - $start)

    $reqId = $reqMatches[$i].Groups[1].Value
    $statusMatch = [regex]::Match($block, '(?im)^-\s+\*\*Status:\*\*\s*([a-z-]+)\s*$')
    $featureMatch = [regex]::Match($block, '(?im)^-\s+\*\*Feature file:\*\*\s*`([^`]+)`\s*$')
    $acMatches = [regex]::Matches($block, '(?im)^\s*-\s*AC-(\d+)\s*:')

    $acs = @()
    foreach ($acMatch in $acMatches) {
        $acs += "AC-$($acMatch.Groups[1].Value)"
    }

    $requirements += [pscustomobject]@{
        ReqId = $reqId
        Status = if ($statusMatch.Success) { $statusMatch.Groups[1].Value.ToLowerInvariant() } else { "" }
        FeatureFile = if ($featureMatch.Success) { $featureMatch.Groups[1].Value } else { "" }
        ACs = $acs
    }
}

$traceRows = @()
foreach ($line in $traceLines) {
    if ($line -notmatch '^\s*\|') { continue }
    if ($line -match '^\s*\|\s*-+') { continue }

    $cols = $line.Trim().Trim('|').Split('|') | ForEach-Object { $_.Trim() }
    if ($cols.Count -lt 3) { continue }

    $reqId = $cols[0]
    $ac = $cols[2]
    if ($reqId -match '^REQ-[A-Z]+-\d{3}$') {
        $traceRows += [pscustomobject]@{ ReqId = $reqId; AC = $ac }
    }
}

$errors = New-Object System.Collections.Generic.List[string]

foreach ($req in $requirements) {
    if ($req.FeatureFile -and -not (Test-Path -LiteralPath $req.FeatureFile)) {
        $errors.Add("$($req.ReqId): missing feature file '$($req.FeatureFile)'.")
    }

    if ($req.Status -notin @("approved", "in-progress")) {
        continue
    }

    $reqRows = $traceRows | Where-Object { $_.ReqId -eq $req.ReqId }
    if (-not $reqRows -or $reqRows.Count -eq 0) {
        $errors.Add("$($req.ReqId): status '$($req.Status)' but no traceability rows found.")
        continue
    }

    foreach ($ac in $req.ACs) {
        $acFound = $reqRows | Where-Object { $_.AC -eq $ac }
        if (-not $acFound -or $acFound.Count -eq 0) {
            $errors.Add("$($req.ReqId): missing traceability row for $ac.")
        }
    }
}

if ($errors.Count -gt 0) {
    foreach ($err in $errors) {
        Write-Host "::error::$err"
    }
    exit 1
}

Write-Host "Traceability check passed for $RequirementsPath and $TraceabilityPath"
exit 0
