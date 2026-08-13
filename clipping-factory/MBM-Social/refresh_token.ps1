$body = @{
    client_id = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com"
    client_secret = "$env:YOUTUBE_CLIENT_SECRET"
    refresh_token = "$env:YOUTUBE_REFRESH_TOKEN"
    grant_type = "refresh_token"
}
Invoke-RestMethod -Uri "https://oauth2.googleapis.com/token" -Method Post -Body $body