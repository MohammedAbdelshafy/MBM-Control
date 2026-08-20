"""
MBM LeadEngine — Ads Package
=============================
Facebook Ads SDK + Google Ads API integrations for finding leads
in the AI consultancy, website creation, and app development verticals.

All campaign-creation commands default to --dry-run.
Use --apply to create live campaigns that spend money.
"""

from pathlib import Path

ADS_DIR = Path(__file__).resolve().parent
LOGS_DIR = ADS_DIR.parent / "logs" / "ads"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

__all__ = ["ADS_DIR", "LOGS_DIR"]
