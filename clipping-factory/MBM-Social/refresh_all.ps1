$brands = @{
    "clippingfactorymbm" = "YOUTUBE_REFRESH_CLIPPINGFACTORYMBM_REDACTED"
    "cutedosage" = "YOUTUBE_REFRESH_CUTEDOSAGE_REDACTED"
    "dontwatchthis" = "YOUTUBE_REFRESH_DONTWATCHTHIS_REDACTED"
    "goalmachinez" = "YOUTUBE_REFRESH_GOALMACHINEZ_REDACTED"
    "twistsrevealed" = "YOUTUBE_REFRESH_TWISTSREVEALED_REDACTED"
}

$client_id = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com"
$client_secret = "$env:YOUTUBE_CLIENT_SECRET"

foreach ($brand in $brands.Keys) {
    $refresh_token = $brands[$brand]
    $body = @{
        client_id = $client_id
        client_secret = $client_secret
        refresh_token = $refresh_token
        grant_type = "refresh_token"
    }
    try {
        $result = Invoke-RestMethod -Uri "https://oauth2.googleapis.com/token" -Method Post -Body $body
        Write-Host ($brand + ": SUCCESS - access_token: " + $result.access_token.Substring(0,20) + "...")
    } catch {
        Write-Host ($brand + ": ERROR - " + $_.Exception.Message)
    }
}