$key = (Get-Content "$env:USERPROFILE\.render\cli.yaml" | Where-Object { $_ -match '^\s+key:\s+' }) -replace '.*key:\s+',''
$headers = @("Authorization: Bearer $key", "Accept: application/json")

$servicesJson = curl.exe -s -H $headers[0] -H $headers[1] "https://api.render.com/v1/services?limit=50"
if (-not $servicesJson) { throw "Failed to list Render services" }
Write-Host "services_json_preview=$($servicesJson.Substring(0, [Math]::Min(500, $servicesJson.Length)))"
$services = $servicesJson | ConvertFrom-Json

$serviceId = $null
$serviceName = $null
foreach ($item in $services) {
    $svc = $item.service
    $url = $svc.serviceDetails.url
    $repo = $svc.repo
    Write-Host "found_service name=$($svc.name) id=$($svc.id) url=$url repo=$repo"
    if ($svc.name -eq 'CFBAllenRatings' -or ($url -like '*cfballenratings*') -or ($repo -like '*cfb-allen-ratings*')) {
        $serviceId = $svc.id
        $serviceName = $svc.name
        break
    }
}
if (-not $serviceId) { throw "CFBAllenRatings service not found" }
Write-Host "service_id=$serviceId name=$serviceName"

$deployJson = curl.exe -s -X POST -H $headers[0] -H $headers[1] -H "Content-Type: application/json" -d "{\"clearCache\":\"clear\"}" "https://api.render.com/v1/services/$serviceId/deploys"
if (-not $deployJson) { throw "Failed to trigger deploy" }
$deploy = $deployJson | ConvertFrom-Json
$deployId = $deploy.id
Write-Host "deploy_id=$deployId"

$deadline = (Get-Date).AddMinutes(15)
while ((Get-Date) -lt $deadline) {
    $statusJson = curl.exe -s -H $headers[0] -H $headers[1] "https://api.render.com/v1/services/$serviceId/deploys/$deployId"
    $statusObj = $statusJson | ConvertFrom-Json
    $status = $statusObj.status
    Write-Host "deploy_status=$status"
    if ($status -eq 'live') { break }
    if ($status -in @('build_failed','update_failed','canceled','deactivated')) { throw "Deploy failed: $status" }
    Start-Sleep -Seconds 20
}
if ($status -ne 'live') { throw 'Deploy timed out' }

$html = (curl.exe -s "https://cfballenratings.onrender.com/").ToString()
$hasOverall = ($html -match 'value="overall"') -and ($html -match 'Overall')
$hasBlendedCol = $html -match '>Blended<'
Write-Host "site_overall=$hasOverall site_blended_col=$hasBlendedCol"
if (-not $hasOverall -or $hasBlendedCol) { throw 'Site still shows old UI' }
Write-Host 'SUCCESS'
