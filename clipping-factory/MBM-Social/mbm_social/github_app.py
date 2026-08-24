"""
GitHub App control plane — Phase 9 (optional, least-privilege).

Provides the repo-automation surface WITHOUT broad personal credentials:
  - installation-token flow (JWT signed with the app private key; exchanged for
    an installation token via the GitHub API)
  - webhook signature validation (HMAC-SHA256, stdlib only)
  - repository allow-list
  - event idempotency (dedupe by event id)
  - issue/PR creation via gh CLI or REST (token from env, never hardcoded)

Minimum permissions are declared in platform_registry.GITHUB_APP_MIN_PERMISSIONS.
Secrets (APP_ID, private key, webhook secret) come from env / a gitignored file.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

STATE_DIR = Path(__file__).resolve().parent.parent / "artifacts" / "gh_app"


@dataclass
class GitHubAppConfig:
    app_id: str = ""
    private_key_pem: str = ""
    webhook_secret: str = ""
    installation_id: str = ""
    allowed_repos: list[str] = field(default_factory=list)   # ["owner/name", ...]
    api_base: str = "https://api.github.com"

    @classmethod
    def from_env(cls) -> "GitHubAppConfig":
        return cls(
            app_id=os.getenv("GH_APP_ID", ""),
            private_key_pem=os.getenv("GH_APP_PRIVATE_KEY", "").replace("\\n", "\n"),
            webhook_secret=os.getenv("GH_APP_WEBHOOK_SECRET", ""),
            installation_id=os.getenv("GH_APP_INSTALLATION_ID", ""),
            allowed_repos=[r.strip() for r in os.getenv("GH_APP_ALLOWED_REPOS", "").split(",") if r.strip()],
        )


# ── webhook signature validation ────────────────────────────────────────
def validate_webhook_signature(payload_body: bytes, signature_header: str, secret: str) -> bool:
    """Validate a GitHub webhook X-Hub-Signature-256 header (HMAC-SHA256)."""
    if not secret:
        return False
    expected = hmac.new(secret.encode(), payload_body, hashlib.sha256).hexdigest()
    provided = signature_header.removeprefix("sha256=").strip()
    return hmac.compare_digest(expected, provided)


# ── repository allow-list ───────────────────────────────────────────────
def is_repo_allowed(repo_full_name: str, allowed: list[str]) -> bool:
    if not allowed:
        return False
    return repo_full_name in allowed


# ── event idempotency ───────────────────────────────────────────────────
class IdempotencyStore:
    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file or (STATE_DIR / "event_ids.jsonl")
        self._seen: set[str] = set()
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if not self.state_file.exists():
            return
        try:
            for line in self.state_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line:
                    self._seen.add(line)
        except Exception:
            pass

    def seen(self, event_id: str) -> bool:
        with self._lock:
            return event_id in self._seen

    def mark(self, event_id: str) -> bool:
        """Return True if this is the first time we see the id (i.e. process it)."""
        with self._lock:
            if event_id in self._seen:
                return False
            self._seen.add(event_id)
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "a", encoding="utf-8") as f:
                f.write(event_id + "\n")
            return True


# ── installation token (JWT) flow ───────────────────────────────────────
def _b64url(data: bytes) -> str:
    import base64
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def build_app_jwt(app_id: str, private_key_pem: str, ttl_sec: int = 600) -> str:
    """Build a GitHub App JWT (RS256). Requires `cryptography` for real signing.

    Falls back to raising a clear error if the dependency is absent, rather than
    producing an invalid token.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
    except Exception as e:
        raise RuntimeError(
            "GitHub App JWT requires the 'cryptography' package "
            "(pip install cryptography). Refusing to fabricate a token."
        ) from e

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"iat": now - 60, "exp": now + ttl_sec, "iss": str(app_id)}
    seg = _b64url(json.dumps(header).encode()) + "." + _b64url(json.dumps(payload).encode())
    key = load_pem_private_key(private_key_pem.encode(), password=None)
    sig = key.sign(seg.encode(), padding.PKCS1v15(), hashes.SHA256())
    return seg + "." + _b64url(sig)


def exchange_installation_token(jwt: str, installation_id: str, api_base: str,
                                token_output: Optional[Path] = None) -> str:
    """Exchange an app JWT for an installation token via the GitHub REST API.

    Returns the token. If network/HTTP fails, raises (never fabricates).
    """
    import urllib.request
    url = f"{api_base}/app/installations/{installation_id}/access_tokens"
    req = urllib.request.Request(url, data=b"", method="POST",
                                 headers={"Authorization": f"Bearer {jwt}",
                                           "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.load(r)
    tok = data.get("token")
    if not tok:
        raise RuntimeError("GitHub API did not return an installation token.")
    if token_output:
        token_output.parent.mkdir(parents=True, exist_ok=True)
        token_output.write_text(tok, encoding="utf-8")
    return tok


# ── issue creation (gh CLI if available, else REST) ─────────────────────
def create_issue(repo: str, title: str, body: str, *,
                 labels: Optional[list[str]] = None,
                 token: Optional[str] = None,
                 api_base: str = "https://api.github.com") -> dict:
    """Create a GitHub issue. Uses `gh` CLI when present; else REST with token.

    Returns a dict describing the outcome (never raises on missing tooling —
    returns an error dict so callers can decide to fall back to local logging).
    """
    labels = labels or []
    # Prefer gh CLI (handles auth/token via login or GH_TOKEN env).
    try:
        cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
        for lb in labels:
            cmd += ["--label", lb]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if out.returncode == 0:
            return {"ok": True, "method": "gh", "url": out.stdout.strip()}
    except FileNotFoundError:
        pass
    except Exception as e:
        return {"ok": False, "method": "gh", "error": str(e)}

    # REST fallback (token from arg or GH_TOKEN env).
    tok = token or os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
    if not tok:
        return {"ok": False, "method": "rest", "error": "no gh CLI and no GH_TOKEN"}
    try:
        import urllib.request
        payload = {"title": title, "body": body, "labels": labels}
        req = urllib.request.Request(
            f"{api_base}/repos/{repo}/issues",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {tok}",
                     "Accept": "application/vnd.github+json",
                     "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
        return {"ok": True, "method": "rest", "url": data.get("html_url", "")}
    except Exception as e:
        return {"ok": False, "method": "rest", "error": str(e)}


def report_blocker(repo: str, platform: str, reason: str,
                   config: Optional[GitHubAppConfig] = None) -> dict:
    """Convenience: open a GitHub issue when a platform is BLOCKED/MANUAL."""
    config = config or GitHubAppConfig.from_env()
    if config.allowed_repos and repo not in config.allowed_repos:
        return {"ok": False, "error": f"repo {repo} not in allow-list"}
    title = f"[publish-blocker] {platform}: {reason[:60]}"
    body = (f"Platform `{platform}` cannot be published from the current codebase.\n\n"
            f"Reason: {reason}\n\n"
            f"Action: preserve the package, do NOT mark as Published, and implement "
            f"a real publisher or provision credentials before enabling automation.")
    return create_issue(repo, title, body, labels=["publish-blocker", "automation"],
                        token=os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN"))
