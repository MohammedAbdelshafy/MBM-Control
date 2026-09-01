"""
Per-Brand YouTube Data API OAuth token generator for MBM-Social.

Each brand's channel is owned by a separate Google account. A refresh token is
scoped to ONE Google account, so every brand needs its OWN OAuth consent flow.
This script runs the flow per brand, VERIFIES the returned token actually owns
the brand's expected channel (channels().list mine=True), and only then saves
it to MBM-Social/youtube_tokens.json -- never clobbering other brands' tokens.

Usage:
  python clipping-factory/auth_brand_youtube_token.py --brand dontwatchthis
  python clipping-factory/auth_brand_youtube_token.py --all        # one browser open per brand
  python clipping-factory/auth_brand_youtube_token.py --verify     # audit existing tokens
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import shutil
import sys
import time
import urllib.parse
from pathlib import Path


from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass


os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

BASE_DIR = Path(__file__).parent.resolve()
MBM_SOCIAL_DIR = BASE_DIR / "MBM-Social"
TOKENS_PATH = MBM_SOCIAL_DIR / "youtube_tokens.json"
REGISTRY_PATH = MBM_SOCIAL_DIR / "ChannelRegistry.json"

CLIENT_ID = "708112125852-6c9bg1ddn88g3e3puaus8bi288upsr5l.apps.googleusercontent.com"
CLIENT_SECRET = os.getenv("YOUTUBE_CLIENT_SECRET", "")
SCOPES = sorted([
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
])
SCOPE = " ".join(SCOPES)


BRANDS = ["clippingfactorymbm", "cutedosage", "dontwatchthis", "goalmachinez", "twistsrevealed"]


def load_channel_registry() -> list[dict]:
    if not REGISTRY_PATH.exists():
        print(f"[AUTH] ChannelRegistry not found: {REGISTRY_PATH}")
        return []
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8")).get("channels", [])


def brand_channel(slug: str) -> dict | None:
    for ch in load_channel_registry():
        if ch.get("brand") == slug:
            return ch
    return None


def _load_tokens() -> dict:
    if not TOKENS_PATH.exists():
        return {}
    try:
        return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_tokens(tokens: dict) -> None:
    if TOKENS_PATH.exists():
        backup = TOKENS_PATH.with_suffix(f".json.bak_{int(time.time())}")
        shutil.copy2(TOKENS_PATH, backup)
    TOKENS_PATH.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    print(f"[AUTH] Saved tokens -> {TOKENS_PATH}")


def _owned_channels_info(creds) -> list[dict]:
    from googleapiclient.discovery import build
    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.channels().list(part="id,snippet", mine=True).execute()
    channels = []
    for c in resp.get("items", []):
        cid = c.get("id", "")
        snip = c.get("snippet", {})
        title = snip.get("title", "")
        custom_url = snip.get("customUrl", "")
        channels.append({"id": cid, "title": title, "customUrl": custom_url})
    return channels


def _owned_channel_ids(creds) -> list[str]:
    return [c["id"] for c in _owned_channels_info(creds)]


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("utf-8").rstrip("=")
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode("utf-8").rstrip("=")
    return verifier, challenge


def _classify_token_error(exc: Exception) -> str:
    msg = str(exc).lower()
    if "invalid_grant" in msg:
        return "invalid_grant"
    if "invalid_scope" in msg:
        return "invalid_scope"
    if "invalid_request" in msg and "code_verifier" in msg:
        return "pkce_mismatch"
    return "unknown"


def auth_one_brand(slug: str, force: bool = False, code: str | None = None, debug_auth: bool = False) -> bool:
    ch = brand_channel(slug)
    expected_channel = (ch or {}).get("youtube_channel_id")
    expected_handle = (ch or {}).get("handle", "")
    owner_email = (ch or {}).get("owned_by", "unknown")
    if not ch:
        print(f"[AUTH] No ChannelRegistry entry for brand '{slug}'. Skipping.", flush=True)
        return False

    tokens = _load_tokens()
    entry = tokens.get(slug, {})
    if entry.get("refresh_token") and not force:
        res = input(
            f"[AUTH] Brand '{slug}' already has a refresh_token. Re-run consent flow? [y/N] "
        ).strip().lower()
        if res != "y":
            print(f"[AUTH] Skipped {slug} (keep existing token).", flush=True)
            return True

    import random
    attempt_id = random.randint(10000, 99999)
    print("=" * 70, flush=True)
    print(f"  YouTube OAuth for brand: {slug}", flush=True)
    print(f"  Attempt ID             : {attempt_id}", flush=True)
    print(f"  Expected channel       : {expected_channel} ({expected_handle})", flush=True)
    print(f"  EXPECTED GOOGLE ACCOUNT: {owner_email}", flush=True)
    print("  Scope                  : " + SCOPE, flush=True)
    print("=" * 70, flush=True)

    if debug_auth:
        print(f"[DEBUG] Brand           : {slug}")
        print(f"[DEBUG] Client ID Suffix: ...{CLIENT_ID[-15:]}")
        print(f"[DEBUG] Scopes          : {SCOPES}")

    from google_auth_oauthlib.flow import InstalledAppFlow

    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    # PKCE: generate fresh verifier/challenge per attempt (S256). Stored per-attempt,
    # never reused across attempts, and verified during token exchange.
    pkce_verifier, pkce_challenge = _generate_pkce_pair()
    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=SCOPES,
        redirect_uri="http://localhost:8095/",
        autogenerate_code_verifier=False,
        code_verifier=pkce_verifier,
    )
    if debug_auth:
        print(f"[DEBUG] PKCE enabled: verifier len={len(pkce_verifier)}, challenge={pkce_challenge[:12]}...")

    if code:
        print(f"[AUTH] Exchanging provided authorization code directly...", flush=True)
        try:
            flow.fetch_token(code=code, code_verifier=pkce_verifier)
        except Exception as e:
            kind = _classify_token_error(e)
            if kind == "invalid_grant":
                print(f"[AUTH] FAIL invalid_grant during code exchange: {e}", flush=True)
            elif kind == "invalid_scope":
                print(f"[AUTH] FAIL invalid_scope during code exchange: {e}", flush=True)
            else:
                print(f"[AUTH] Token exchange failed: {e}", flush=True)
            return False
    else:
        import http.server
        import hashlib
        auth_url, state = flow.authorization_url(
            prompt="consent",
            access_type="offline",
            login_hint=owner_email,
            code_challenge=pkce_challenge,
            code_challenge_method="S256",
        )
        print(f"\n👉 [Attempt {attempt_id}] Please visit this URL to authorize:\n{auth_url}\n", flush=True)
        print(f"⚠️  USE ONLY THIS FRESH URL. OLD TABS WILL FAIL. This state expires in 5 minutes.", flush=True)

        if debug_auth:
            state_fp = hashlib.md5(state.encode()).hexdigest()[:8]
            print(f"[DEBUG] Expected State Fingerprint: {state_fp}")

        class CallbackServer(http.server.HTTPServer):
            expected_state = state
            auth_code = None
            last_error = None


        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                parsed = urllib.parse.urlparse(self.path)
                qs = urllib.parse.parse_qs(parsed.query)
                req_state = qs.get("state", [""])[0]
                req_code = qs.get("code", [""])[0]
                req_error = qs.get("error", [""])[0]
                req_error_desc = qs.get("error_description", [""])[0]

                if parsed.path == "/favicon.ico":
                    self.send_response(404)
                    self.end_headers()
                    return

                # Handle OAuth error responses (user denied, etc.)
                if req_error:
                    err_msg = req_error + (f": {req_error_desc}" if req_error_desc else "")
                    print(f"[AUTH] OAuth error from provider: {err_msg}", flush=True)
                    self.server.last_error = err_msg
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(f"<html><body><h3>Authorization failed: {err_msg}</h3><p>Close this tab and run the auth command again to get a fresh URL.</p></body></html>".encode())
                    return

                # Stale-state rejection: state MUST match exactly, otherwise reject.
                # This prevents \"Authorization attempt expired or is no longer active\" reuse
                # from succeeding with a stale tab's code.
                if req_state != self.server.expected_state:
                    if debug_auth:
                        req_fp = hashlib.md5(req_state.encode()).hexdigest()[:8] if req_state else "NONE"
                        expected_fp = hashlib.md5(self.server.expected_state.encode()).hexdigest()[:8] if self.server.expected_state else "NONE"
                        print(f"[DEBUG] STATE MISMATCH: Expected {expected_fp}, got {req_fp}")
                    print("[AUTH] REJECTED stale/invalid state. This authorization URL is expired or was already used. Please use the CURRENT URL from the terminal.", flush=True)
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"<html><body><h3>Authorization attempt expired or is no longer active.</h3><p>Please use the CURRENT authorization URL from the terminal (fresh state required).</p></body></html>")
                    return

                if not req_code:
                    print("[AUTH] ERROR: No authorization code provided in the callback URL.", flush=True)
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"<html><body><h3>Error: No code provided.</h3></body></html>")
                    return

                if debug_auth:
                    print(f"[DEBUG] Valid code received. Exchanging...")

                self.server.auth_code = req_code
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<html><body style='font-family:sans-serif;text-align:center;padding-top:50px;'><h2 style='color:#10b981;'>&#10004; Authorization Received!</h2><p>You can close this tab and return to the terminal. The script will now attempt to verify the token.</p></body></html>")

        server = CallbackServer(("127.0.0.1", 8095), CallbackHandler)
        server.timeout = 1.0  # 1 second poll
        print("[AUTH] Listening on http://127.0.0.1:8095/ for authorization callback...", flush=True)
        if debug_auth:
            print("[DEBUG] Server started on port 8095")

        timeout_budget = 300  # 5 minutes per requirement (fresh URL expires)
        start_time = time.time()

        try:
            while not server.auth_code:
                server.handle_request()
                if server.last_error:
                    print(f"[AUTH] OAuth callback error: {server.last_error}", flush=True)
                    return False
                if time.time() - start_time > timeout_budget:
                    print(f"\n[AUTH] OAUTH_CALLBACK_TIMEOUT: No valid callback received within {timeout_budget} seconds. Please use the current authorization URL.", flush=True)
                    return False
        finally:
            if debug_auth:
                print("[DEBUG] Server shutdown initiated on port 8095")
            server.server_close()
            if debug_auth:
                print("[DEBUG] Server successfully closed.")

        print("[AUTH] Exchanging received code for OAuth credentials (PKCE verifier)...", flush=True)
        try:
            flow.fetch_token(code=server.auth_code, code_verifier=pkce_verifier)
        except Exception as e:
            kind = _classify_token_error(e)
            if kind == "invalid_grant":
                print(f"[AUTH] FAIL invalid_grant during code exchange: {e}", flush=True)
                print("[AUTH] Hint: code may be expired, already used, or state was stale. Re-run with a fresh URL.", flush=True)
            elif kind == "invalid_scope":
                print(f"[AUTH] FAIL invalid_scope during code exchange: {e} -- check SCOPES configuration.", flush=True)
            else:
                print(f"[AUTH] Token exchange failed: {e}", flush=True)
            return False



    print("[AUTH] Verifying the token owns the expected channel...", flush=True)
    ch_info = _owned_channels_info(flow.credentials)
    owned = [c["id"] for c in ch_info]
    print(f"[AUTH] Token owns channels: {ch_info or 'NONE'}", flush=True)

    # Cross-brand auto-saving was removed to prevent accidental overwrites (e.g. cutedosage)


    if expected_channel and expected_channel not in owned:
        owned_titles = ", ".join(f"'{c.get('title')}' ({c.get('id')})" for c in ch_info)
        print(
            f"\n[AUTH] ERROR: Token owns {owned_titles}, but brand '{slug}' requires channel ID '{expected_channel}'.\n"
            f"👉 IMPORTANT: When Google prompts 'Choose an account or Brand Account', you MUST click on the Brand Account matching '{slug}'.",
            flush=True,
        )
        return False




    tokens[slug] = {
        "channel_id": expected_channel or (owned[0] if owned else ""),
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": flow.credentials.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "access_token": flow.credentials.token,
        "google_account_email": owner_email,
        "last_verified": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save_tokens(tokens)
    print(f"[AUTH] SUCCESS: saved distinct refresh token for '{slug}'.")
    return True


def verify_tokens(quiet: bool = False) -> int:
    """Check every brand token actually owns its registered channel. Returns #bad."""
    bad = 0
    tokens = _load_tokens()
    print("=== TOKEN AUDIT ===")
    for slug in BRANDS:
        entry = tokens.get(slug)
        ch_reg = brand_channel(slug) or {}
        expected = ch_reg.get("youtube_channel_id")
        expected_handle = ch_reg.get("handle")
        expected_account = ch_reg.get("owned_by")

        is_unknown = expected_account and "UNKNOWN" in str(expected_account).upper()
        if not entry or not entry.get("refresh_token"):
            if is_unknown:
                print(f"  [{slug}] NEEDS_CONFIRMATION (no token entry, account UNKNOWN)")
                print(f"    Expected Google Account: {expected_account}  [HUMAN CONFIRMATION REQUIRED]")
                print(f"    Expected Channel:        {expected} ({expected_handle})\n")
            else:
                print(f"  [{slug}] MISSING (no token entry)")
                print(f"    Expected Google Account: {expected_account}")
                print(f"    Expected Channel:        {expected} ({expected_handle})\n")
            bad += 1
            continue
            
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            creds = Credentials(
                token=entry.get("access_token", ""),
                refresh_token=entry.get("refresh_token"),
                token_uri=entry.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=entry.get("client_id"),
                client_secret=entry.get("client_secret"),
                scopes=SCOPES,
            )
            creds.refresh(Request())
            ch_info = _owned_channels_info(creds)
            owned = [c["id"] for c in ch_info]
            handles = [c.get("snippet", {}).get("customUrl", "") for c in ch_info]

            if expected and expected not in owned:
                print(f"  [{slug}] FAIL - WRONG CHANNEL")
                print(f"    Expected Channel: {expected} ({expected_handle})")
                print(f"    Auth Channel:     {owned[0] if owned else 'NONE'} ({handles[0] if handles else ''})")
                bad += 1
            else:
                if is_unknown:
                    print(f"  [{slug}] OK (channel verified, but account is UNKNOWN - needs human confirmation)")
                    print(f"    Expected Google Account: {expected_account}  [NEEDS CONFIRMATION]")
                    print(f"    Auth Channel:     {owned[0] if owned else 'NONE'} ({handles[0] if handles else ''})")
                    print(f"    NOTE: Token is valid for channel {expected}, but Google account ownership is not yet confirmed. DO NOT GUESS.")
                else:
                    print(f"  [{slug}] OK")
                    print(f"    Expected Google Account: {expected_account}")
                    print(f"    Expected Channel:        {expected} ({expected_handle})")
                    print(f"    Auth Channel:     {owned[0] if owned else 'NONE'} ({handles[0] if handles else ''})")
                # For UNKNOWN, do not count as bad but flag for human action
                if is_unknown:
                    # Don't increment bad, but keep visible
                    pass
            print()

        except Exception as e:
            err_str = str(e)
            if is_unknown and "UNKNOWN" in str(expected_account).upper():
                print(f"  [{slug}] NEEDS_CONFIRMATION - token check failed but account is UNKNOWN")
                print(f"    Expected Google Account: {expected_account}  [HUMAN CONFIRMATION REQUIRED]")
                print(f"    Expected Channel:        {expected} ({expected_handle})")
            if "invalid_grant" in err_str:
                print(f"  [{slug}] FAIL - INVALID_GRANT (token revoked/expired)")
                print(f"    Expected Google Account: {expected_account}")
                print(f"    Expected Channel:        {expected} ({expected_handle})")
                print(f"    ACTION: Run: python clipping-factory/auth_brand_youtube_token.py --brand {slug} --force --debug-auth")
            elif "invalid_scope" in err_str:
                print(f"  [{slug}] FAIL - INVALID_SCOPE")
                print(f"    Expected Google Account: {expected_account}")
            else:
                print(f"  [{slug}] FAIL - {e}")
                print(f"    Expected Google Account: {expected_account}")
            bad += 1
            print()

    return bad


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Per-brand YouTube OAuth token manager.")
    g = parser.add_mutually_exclusive_group(required=True)
    g.add_argument("--brand", help="a single brand slug, e.g. dontwatchthis")
    g.add_argument("--all", action="store_true", help="run OAuth for every brand")
    g.add_argument("--verify", action="store_true", help="audit existing tokens")
    parser.add_argument("--force", action="store_true", help="re-run consent even if a token exists")
    parser.add_argument("--debug-auth", action="store_true", help="print extra diagnostic info during OAuth")
    parser.add_argument("--code", help="authorization code to exchange directly (if browser redirected)")
    args = parser.parse_args(argv)

    if args.verify:
        bad = verify_tokens()
        print(f"\n[AUTH] Audit complete: {bad} bad/missing token(s).", flush=True)
        return 1 if bad else 0

    brands = BRANDS if args.all else [args.brand]
    results = []
    for slug in brands:
        try:
            ok = auth_one_brand(slug, force=args.force, code=args.code, debug_auth=args.debug_auth)
        except KeyboardInterrupt:
            print(f"[AUTH] Cancelled during '{slug}'.", flush=True)
            ok = False
        except Exception as e:
            import traceback
            print(f"[AUTH] Flow error for '{slug}': {e}", flush=True)
            traceback.print_exc()
            ok = False
        results.append((slug, ok))


    for slug, ok in results:
        print(f"  [{'OK' if ok else 'FAIL'}] {slug}")
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    sys.exit(main())