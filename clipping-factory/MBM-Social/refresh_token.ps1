$body = @{
    client_id = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com"
    client_secret = "GOOGLE_OAUTH_CLIENT_SECRET_REDACTED"
    refresh_token = "YOUTUBE_REFRESH_CLIPPINGFACTORYMBM_REDACTED"
    grant_type = "refresh_token"
}
Invoke-RestMethod -Uri "https://oauth2.googleapis.com/token" -Method Post -Body $body