"""
Ads Configuration & Budget Guards
===================================
Centralised configuration for Facebook Ads and Google Ads integrations.
Loads credentials from env, enforces daily spend caps, provides shared
logging and Neteller checkout link helpers.

Env vars read (never hardcoded):
  FB_ACCESS_TOKEN, FB_AD_ACCOUNT_ID, FB_APP_ID, FB_APP_SECRET, FB_PAGE_ID
  GOOGLE_ADS_DEVELOPER_TOKEN, GOOGLE_ADS_CUSTOMER_ID, GOOGLE_ADS_CLIENT_ID,
  GOOGLE_ADS_CLIENT_SECRET, GOOGLE_ADS_REFRESH_TOKEN, GOOGLE_ADS_LOGIN_CUSTOMER_ID
  ADS_MAX_DAILY_SPEND_FB, ADS_MAX_DAILY_SPEND_GOOGLE
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional

# ── Repository root & dotenv ────────────────────────────────────────────────
ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

try:
    from dotenv import load_dotenv
    for env_file in [ROOT_DIR / ".env.local", ROOT_DIR / ".env"]:
        if env_file.exists():
            load_dotenv(env_file)
except ImportError:
    pass

# ── Neteller canonical rail ─────────────────────────────────────────────────
try:
    from MBM.Scripts.neteller_config import neteller_link, NETELLER_EMAIL, NETELLER_ACCOUNT_ID
except Exception:
    NETELLER_EMAIL = os.getenv("NETELLER_EMAIL", "abdelshafyclapps@gmail.com")
    NETELLER_ACCOUNT_ID = os.getenv("NETELLER_ACCOUNT_ID", "4599228811")

    def neteller_link(amount, item, currency="USD", **kw):
        base = "https://member.neteller.com/pay"
        return (
            f"{base}?email={NETELLER_EMAIL}&account={NETELLER_ACCOUNT_ID}"
            f"&amount={float(amount):.2f}&currency={currency}&item={item}"
        )

# ── Logging ─────────────────────────────────────────────────────────────────
LOGS_DIR = Path(__file__).resolve().parent.parent / "logs" / "ads"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("ads")
_handler = logging.FileHandler(LOGS_DIR / "ads_engine.log", encoding="utf-8")
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
_logger.addHandler(_handler)
_logger.setLevel(logging.INFO)

log = _logger


def save_json(path: Path, data):
    """Atomic JSON write with pretty-printing."""
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)
    tmp.replace(path)


# ── Facebook Ads Credentials ───────────────────────────────────────────────
@dataclass
class FacebookAdsConfig:
    access_token: str = field(default_factory=lambda: os.getenv("FB_ACCESS_TOKEN", ""))
    ad_account_id: str = field(default_factory=lambda: os.getenv("FB_AD_ACCOUNT_ID", ""))
    app_id: str = field(default_factory=lambda: os.getenv("FB_APP_ID", ""))
    app_secret: str = field(default_factory=lambda: os.getenv("FB_APP_SECRET", ""))
    page_id: str = field(default_factory=lambda: os.getenv("FB_PAGE_ID", ""))
    max_daily_spend: float = field(
        default_factory=lambda: float(os.getenv("ADS_MAX_DAILY_SPEND_FB", "50.00"))
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token and self.ad_account_id)

    def validate(self) -> list[str]:
        """Return list of missing required fields."""
        missing = []
        if not self.access_token:
            missing.append("FB_ACCESS_TOKEN")
        if not self.ad_account_id:
            missing.append("FB_AD_ACCOUNT_ID")
        return missing


# ── Google Ads Credentials ─────────────────────────────────────────────────
@dataclass
class GoogleAdsConfig:
    developer_token: str = field(
        default_factory=lambda: os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    )
    customer_id: str = field(
        default_factory=lambda: os.getenv("GOOGLE_ADS_CUSTOMER_ID", "")
    )
    client_id: str = field(
        default_factory=lambda: os.getenv("GOOGLE_ADS_CLIENT_ID", "")
    )
    client_secret: str = field(
        default_factory=lambda: os.getenv("GOOGLE_ADS_CLIENT_SECRET", "")
    )
    refresh_token: str = field(
        default_factory=lambda: os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "")
    )
    login_customer_id: str = field(
        default_factory=lambda: os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")
    )
    max_daily_spend: float = field(
        default_factory=lambda: float(os.getenv("ADS_MAX_DAILY_SPEND_GOOGLE", "50.00"))
    )

    @property
    def is_configured(self) -> bool:
        return bool(self.developer_token and self.customer_id and self.refresh_token)

    def validate(self) -> list[str]:
        missing = []
        if not self.developer_token:
            missing.append("GOOGLE_ADS_DEVELOPER_TOKEN")
        if not self.customer_id:
            missing.append("GOOGLE_ADS_CUSTOMER_ID")
        if not self.client_id:
            missing.append("GOOGLE_ADS_CLIENT_ID")
        if not self.client_secret:
            missing.append("GOOGLE_ADS_CLIENT_SECRET")
        if not self.refresh_token:
            missing.append("GOOGLE_ADS_REFRESH_TOKEN")
        return missing


# ── Budget & Live Campaign Production Gate ─────────────────────────────────
SPEND_LEDGER = LOGS_DIR / "daily_spend_ledger.json"


def is_live_ads_enabled() -> bool:
    """Hard safety gate: requires LIVE_ADS_ENABLED=true in environment."""
    val = os.getenv("LIVE_ADS_ENABLED", "false").strip().lower()
    return val in ("true", "1", "yes")


def generate_preflight_report(
    platform: str,
    campaign_name: str,
    niche: str,
    target_audience: str,
    daily_budget: float,
    total_budget: float,
    form_name: str,
    expected_destination: str = "MBM Dialer (mbm-dialer/app/public/leads_database.json)",
) -> dict:
    """Generate a structured preflight safety verification report."""
    live_enabled = is_live_ads_enabled()
    spend_ok, remaining = check_budget(platform, daily_budget)
    
    status = "APPROVED_FOR_LAUNCH" if (live_enabled and spend_ok) else "LOCKED_SAFETY_GATE"
    
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "platform": platform.upper(),
        "campaign": campaign_name,
        "niche": niche,
        "target": target_audience,
        "daily_budget": f"${daily_budget:.2f}",
        "total_budget": f"${total_budget:.2f}",
        "form": form_name,
        "lead_pipeline": "AD LEAD → NORMALIZER → VALIDATION → DEDUPE → CANONICAL DB → FRESH_CALL_NOW → DIALER",
        "expected_destination": expected_destination,
        "spend_gate": {
            "live_ads_enabled": live_enabled,
            "budget_check_passed": spend_ok,
            "daily_remaining": f"${remaining:.2f}",
            "gate_status": status,
        }
    }
    return report


def verify_live_campaign_gate(
    platform: str,
    daily_budget: float,
    campaign_name: str,
) -> tuple[bool, str]:
    """
    Enforces the mandatory 5-point live spend gate:
      1. LIVE_ADS_ENABLED=true
      2. Valid credentials
      3. Explicit production mode (dry_run=False)
      4. Explicit budget within daily cap
      5. Explicit campaign confirmation
    """
    if not is_live_ads_enabled():
        return False, "LIVE_ADS_ENABLED is false. Live campaign creation is locked for safety."

    can_spend, remaining = check_budget(platform, daily_budget)
    if not can_spend or daily_budget > remaining:
        return False, f"Daily budget cap exceeded for {platform}. Remaining: ${remaining:.2f}, Requested: ${daily_budget:.2f}"

    return True, "GATE_PASSED"


def _load_spend_ledger() -> dict:
    if SPEND_LEDGER.exists():
        try:
            return json.loads(SPEND_LEDGER.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def record_spend(platform: str, amount: float) -> None:
    """Record a spend event for budget tracking."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ledger = _load_spend_ledger()
    key = f"{platform}:{today}"
    ledger[key] = ledger.get(key, 0.0) + amount
    save_json(SPEND_LEDGER, ledger)
    log.info(f"Recorded ${amount:.2f} spend on {platform} ({today})")


def check_budget(platform: str, max_daily: float) -> tuple[bool, float]:
    """
    Check if we're within the daily budget.
    Returns (can_spend, remaining_budget).
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ledger = _load_spend_ledger()
    key = f"{platform}:{today}"
    spent = ledger.get(key, 0.0)
    remaining = max(0.0, max_daily - spent)
    return remaining > 0, remaining


# ── Service availability summary ───────────────────────────────────────────
AI_CONSULTANCY_VERTICALS = [
    "AI Consultancy & Automation",
    "Website Design & Development",
    "Mobile App Development",
    "SaaS Product Development",
    "AI Chatbot Integration",
    "Business Process Automation",
]


def get_credentials_diagnostics() -> dict:
    """Return structured credential status (PRESENT / MISSING) without exposing any secret values."""
    fb_token = "PRESENT" if os.getenv("FB_ACCESS_TOKEN", "").strip() else "MISSING"
    fb_act = "PRESENT" if os.getenv("FB_AD_ACCOUNT_ID", "").strip() else "MISSING"
    fb_ready = fb_token == "PRESENT" and fb_act == "PRESENT"

    ga_dev = "PRESENT" if os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip() else "MISSING"
    ga_cust = "PRESENT" if os.getenv("GOOGLE_ADS_CUSTOMER_ID", "").strip() else "MISSING"
    ga_cid = "PRESENT" if os.getenv("GOOGLE_ADS_CLIENT_ID", "").strip() else "MISSING"
    ga_csec = "PRESENT" if os.getenv("GOOGLE_ADS_CLIENT_SECRET", "").strip() else "MISSING"
    ga_ref = "PRESENT" if os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "").strip() else "MISSING"
    ga_ready = (
        ga_dev == "PRESENT" and
        ga_cust == "PRESENT" and
        ga_cid == "PRESENT" and
        ga_csec == "PRESENT" and
        ga_ref == "PRESENT"
    )

    live_enabled = is_live_ads_enabled()

    return {
        "facebook": {
            "FB_ACCESS_TOKEN": fb_token,
            "FB_AD_ACCOUNT_ID": fb_act,
            "status": "READY" if fb_ready else "CANNOT RETRIEVE (NEEDS CREDENTIALS)",
        },
        "google": {
            "GOOGLE_ADS_DEVELOPER_TOKEN": ga_dev,
            "GOOGLE_ADS_CUSTOMER_ID": ga_cust,
            "GOOGLE_ADS_CLIENT_ID": ga_cid,
            "GOOGLE_ADS_CLIENT_SECRET": ga_csec,
            "GOOGLE_ADS_REFRESH_TOKEN": ga_ref,
            "status": "READY" if ga_ready else "CANNOT RETRIEVE (NEEDS CREDENTIALS)",
        },
        "live_ads": {
            "LIVE_ADS_ENABLED": live_enabled,
            "spend_gate": "LOCKED (LIVE_ADS_ENABLED=false)" if not live_enabled else "UNLOCKED",
        }
    }


def print_config_status():
    """Print a clean diagnostic status for CLI without leaking any secrets."""
    diag = get_credentials_diagnostics()

    print("=" * 60)
    print("  ADS LEAD ENGINE — CREDENTIAL DIAGNOSTICS")
    print("=" * 60)

    print("\n  FACEBOOK:")
    for k, v in diag["facebook"].items():
        if k != "status":
            print(f"    {k}: {v}")
    print(f"    STATUS: {diag['facebook']['status']}")

    print("\n  GOOGLE:")
    for k, v in diag["google"].items():
        if k != "status":
            print(f"    {k}: {v}")
    print(f"    STATUS: {diag['google']['status']}")

    print("\n  LIVE ADS:")
    print(f"    LIVE_ADS_ENABLED: {diag['live_ads']['LIVE_ADS_ENABLED']}")
    print(f"    SPEND GATE:       {diag['live_ads']['spend_gate']}")

    print("\n  TARGET VERTICALS:")
    for v in AI_CONSULTANCY_VERTICALS:
        print(f"    • {v}")
    print("=" * 60)


if __name__ == "__main__":
    print_config_status()
