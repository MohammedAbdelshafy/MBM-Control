"""
Cloud-based Clipping.com campaign scanner.
Runs standalone in GitHub Actions / Supabase Edge Function — no local backend needed.
Scans clipping.com for new campaigns and stores them in Supabase.
"""
import os
import json
import sys
import urllib.request
import urllib.error
import hmac
import hashlib
import time

SUPABASE_URL = os.environ.get("VITE_SUPABASE_URL", "")
SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
CLIPPING_EMAIL = os.environ.get("CLIPPING_EMAIL", "")
CLIPPING_PASSWORD = os.environ.get("CLIPPING_PASSWORD", "")
WEBHOOK_URL = os.environ.get("CLIPPING_WEBHOOK_URL", "")  # Optional: notify your backend

CAMPAIGNS_TABLE = "campaigns_scan_cache"


def log(msg):
    print(f"[CLOUD-SCAN] {msg}", flush=True)


def supabase_request(method, path, data=None):
    """Make a request to Supabase REST API."""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    headers = {
        "apikey": SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    req = urllib.request.Request(url, method=method, headers=headers)
    if data is not None:
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        log(f"Supabase {method} {path} failed: {e.code} {e.read().decode()[:200]}")
        return None
    except Exception as e:
        log(f"Supabase {method} {path} error: {e}")
        return None


def notify_backend(campaigns):
    """Notify the local/cloud backend about new campaigns via webhook."""
    if not WEBHOOK_URL or not campaigns:
        return
    try:
        data = json.dumps({"campaigns": campaigns, "source": "cloud_scan"}).encode()
        req = urllib.request.Request(
            WEBHOOK_URL, data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15):
            log(f"Webhook notified with {len(campaigns)} campaigns")
    except Exception as e:
        log(f"Webhook failed: {e}")


def scan_campaigns():
    """
    Scan clipping.com for available campaigns.
    Uses the public API or parses the website.
    Falls back gracefully if both fail.
    """
    campaigns = []

    # Method 1: Try public API
    try:
        api_url = "https://clipping.com/api/v1/campaigns?status=open"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            campaigns = data.get("campaigns", data.get("data", []))
            log(f"API scan: found {len(campaigns)} campaigns")
            return campaigns
    except Exception as e:
        log(f"API scan failed: {e}")

    # Method 2: Try authenticated scan (if credentials provided)
    if CLIPPING_EMAIL and CLIPPING_PASSWORD:
        try:
            import base64
            auth = base64.b64encode(f"{CLIPPING_EMAIL}:{CLIPPING_PASSWORD}".encode()).decode()
            req = urllib.request.Request(
                "https://clipping.com/api/v1/auth/login",
                data=json.dumps({"email": CLIPPING_EMAIL, "password": CLIPPING_PASSWORD}).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                token_data = json.loads(resp.read().decode())
                token = token_data.get("token", token_data.get("access_token", ""))
                if token:
                    req2 = urllib.request.Request(
                        "https://clipping.com/api/v1/campaigns",
                        headers={"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"},
                    )
                    with urllib.request.urlopen(req2, timeout=15) as resp2:
                        campaigns = json.loads(resp2.read().decode())
                        campaigns = campaigns.get("campaigns", campaigns.get("data", []))
                        log(f"Auth scan: found {len(campaigns)} campaigns")
                        return campaigns
        except Exception as e:
            log(f"Auth scan failed: {e}")

    log("All scan methods failed — no campaigns found")
    return []


def store_results(campaigns):
    """Store scan results in Supabase for backend pickup."""
    if not SUPABASE_URL or not SERVICE_ROLE_KEY:
        log("Supabase not configured, skipping storage")
        notify_backend(campaigns)
        return

    # Upsert each campaign
    stored = 0
    for c in campaigns:
        campaign_id = c.get("id", c.get("campaign_id", ""))
        if not campaign_id:
            continue
        record = {
            "id": campaign_id,
            "title": c.get("title", ""),
            "brand": c.get("brand_name", c.get("brand", "")),
            "url": c.get("url", c.get("campaign_url", "")),
            "requirements": json.dumps(c.get("requirements", {})),
            "raw_data": json.dumps(c),
            "scanned_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": "discovered",
        }
        supabase_request("POST", CAMPAIGNS_TABLE, record)
        stored += 1

    log(f"Stored {stored}/{len(campaigns)} campaigns in Supabase")
    notify_backend(campaigns)


def main():
    log("Starting cloud campaign scan...")

    if not CLIPPING_EMAIL and not CLIPPING_PASSWORD:
        log("WARNING: No credentials — using public API only")

    campaigns = scan_campaigns()
    if campaigns:
        store_results(campaigns)
    else:
        log("No campaigns found in this cycle")

    log("Scan complete")


if __name__ == "__main__":
    main()
