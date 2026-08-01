# YouTube Publishing Setup Guide

## Quick Setup (5 minutes)

### Step 1: Create Google Cloud Project
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable **YouTube Data API v3**:
   - Go to APIs & Services > Library
   - Search "YouTube Data API v3"
   - Click Enable

### Step 2: Create OAuth 2.0 Credentials
1. Go to APIs & Services > Credentials
2. Click **+ Create Credentials** > OAuth client ID
3. Application type: **Desktop app**
4. Name: "MBM YouTube Publisher"
5. Click Create
6. **Copy the Client ID and Client Secret**

### Step 3: Get Refresh Token
Run the setup script:
```bash
cd clipping-factory/backend
.venv\Scripts\python.exe scripts\youtube_oauth_setup.py
```

It will:
- Ask for your Client ID, Client Secret, and Refresh Token
- Test the credentials
- Save to `youtube_tokens.json`

### Step 4: Get Refresh Token (if you don't have one)
1. Go to [OAuth 2.0 Playground](https://developers.google.com/oauthplayground/)
2. Click the gear icon (top right) > Use your own OAuth credentials
3. Enter your Client ID and Client Secret
4. Select `https://www.googleapis.com/auth/youtube.upload`
5. Click Authorize APIs
6. Sign in with your YouTube channel's Google account
7. Click Exchange authorization code for tokens
8. Copy the **Refresh Token**

### Step 5: Run Setup Script
```bash
cd clipping-factory/backend
.venv\Scripts\python.exe scripts\youtube_oauth_setup.py
```

## Verification
After setup, test with:
```bash
.venv\Scripts\python.exe -c "
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import json
tokens = json.load(open('../../youtube_tokens.json'))
cid = list(tokens.keys())[0]
info = tokens[cid]
creds = Credentials(token=None, refresh_token=info['refresh_token'],
    token_uri=info['token_uri'], client_id=info['client_id'],
    client_secret=info['client_secret'],
    scopes=['https://www.googleapis.com/auth/youtube.upload'])
creds.refresh(Request())
print(f'OK - token expires in {creds.expiry}')
"
```

## MBM-Social (Cloud Path)
For the AWS SAM Lambda path, set these in `MBM-Social/.env`:
```
YOUTUBE_CLIENT_ID=<your client id>
YOUTUBE_CLIENT_SECRET=<your client secret>
YOUTUBE_REFRESH_TOKEN=<your refresh token>
```

Then deploy:
```bash
cd MBM-Social/Cloud/PublishSlice
sam build && sam deploy --guided
```
