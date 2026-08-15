"""business_prospector -- Business-Owner AI Services Prospecting Lane.

Targets owners/founders/CEOs of businesses that could buy AI automation,
websites, apps, ConTech software, workflow automation and lead-gen systems.

Authorized data only:
  - Google Maps business data via the configured RapidAPI local-business-data
    endpoint (business name, category, phone, website, rating, reviews, URL).
  - No scraping of private contact data. Owner/founder/email fields are only
    populated when an authorized person-level source provides them (adapter
    interface provided; none configured -> stays empty, never invented).

Scoring components (deterministic, evidence-grounded):
  operational_pain, outdated_website, digital_presence, automation_opportunity,
  company_size, growth_activity, ability_to_pay, service_fit.

CLI:
  python business_prospector.py --query "roofing company dallas tx" --limit 20
  python business_prospector.py --source FILE.json --apply
  python business_prospector.py --list-queries
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .schema import BusinessProspect

BASE = Path(__file__).resolve().parent
ARTIFACTS = BASE / "artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

GMAPS_RAPIDAPI_URL = "https://local-business-data.p.rapidapi.com/search"

DEFAULT_QUERIES = [
    "roofing company dallas tx",
    "plumbing contractor dallas tx",
    "hvac contractor dallas tx",
    "construction company dallas tx",
    "electrical contractor dallas tx",
    "general contractor fort worth tx",
    "cleaning service dallas tx",
    "landscaping company dallas tx",
    "logistics trucking company dallas tx",
    "dentist dallas tx",
]

# Categories with labor-heavy / repeatable workflows -> automation + pain.
LABOR_INTENSIVE = {
    "roofing", "plumbing", "hvac", "construction", "contractor", "electrician",
    "cleaning", "landscaping", "lawn", "painting", "remodeling", "home improvement",
    "concrete", "fencing", "paving", "janitorial", "moving", "pest", "tree service",
    "logistics", "trucking", "freight", "warehouse", "manufacturing",
    "accounting", "bookkeeping", "legal", "lawyer", "tax", "insurance",
    "real estate", "property management", "dentist", "dental", "clinic",
    "chiropractor", "physical therapy", "medical", "veterinary",
    "auto repair", "auto body", "tire", "mechanic", "salon", "spa", "barbershop",
    "restaurant", "catering", "bakery", "laundry", "dry cleaning",
}

# Categories with contech / construction software fit.
CONTECH = {
    "construction", "contractor", "engineering", "civil", "architecture",
    "architect", "structural", "general contractor", "roofing", "concrete",
    "steel", "land development", "surveying", "home builder", "remodeling",
}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class ProspectSource(ABC):
    """Authorized business-intelligence source adapter."""

    name: str = "unknown"

    @abstractmethod
    def fetch(self, query: str, limit: int = 20) -> tuple[list[dict], dict]:
        """Return (raw rows, diagnostics). Never invents rows."""

    def requires_key(self) -> bool:
        return True


class GoogleMapsBusinessSource(ProspectSource):
    """Authorized Google Maps business data via configured RapidAPI key."""

    name = "rapidapi-google-maps"

    def __init__(self, api_key: str = ""):
        if not api_key:
            try:
                from dotenv import load_dotenv

                load_dotenv(Path(__file__).resolve().parents[3] / ".env")
            except Exception:  # noqa: BLE001
                pass
        self.api_key = api_key or os.getenv("RAPIDAPI_KEY", "")

    def requires_key(self) -> bool:
        return not bool(self.api_key)

    def fetch(self, query: str, limit: int = 20) -> tuple[list[dict], dict]:
        if not self.api_key:
            return [], {"blocked": True, "error": "RAPIDAPI_KEY not configured"}
        import requests

        resp = requests.get(
            GMAPS_RAPIDAPI_URL,
            headers={
                "x-rapidapi-key": self.api_key,
                "x-rapidapi-host": "local-business-data.p.rapidapi.com",
            },
            params={"query": query, "limit": limit, "language": "en"},
            timeout=20,
        )
        if resp.status_code != 200:
            return [], {"blocked": True, "error": f"http {resp.status_code}"}
        data = resp.json()
        rows = data.get("data", []) if isinstance(data, dict) else []
        return rows, {"rows": len(rows)}


class NullPersonSource(ProspectSource):
    """No person-level source configured. owner/founder stays empty."""

    name = "none"

    def fetch(self, query: str, limit: int = 20) -> tuple[list[dict], dict]:
        return [], {"blocked": True, "error": "no person/company-source configured"}


class FileBusinessSource(ProspectSource):
    """Local pre-collected business rows (e.g. exported Google Maps results).

    Rows must be from an authorized export; this adapter only re-scores them.
    """

    name = "file-export"

    def __init__(self, path: Path):
        self.path = path

    def requires_key(self) -> bool:
        return False

    def fetch(self, query: str, limit: int = 20) -> tuple[list[dict], dict]:
        if not self.path.exists():
            return [], {"blocked": True, "error": f"file not found: {self.path}"}
        data = json.loads(self.path.read_text(encoding="utf-8"))
        rows = data if isinstance(data, list) else data.get("businesses", data.get("rows", []))
        return rows[:limit], {"rows": min(len(rows), limit)}


# ── deterministic scoring ─────────────────────────────────────────────────

def score_business(row: dict) -> dict:
    """Evidence-grounded component scores + reason trace (0-100 each)."""
    name = str(row.get("name") or "").strip()
    category = str(row.get("category") or row.get("categories") or "").strip()
    cat_lower = category.lower()
    website = str(row.get("website") or "").strip()
    phone = str(row.get("phone_number") or row.get("phone") or "").strip()
    rating = _as_float(row.get("rating"))
    reviews = int(row.get("review_count") or row.get("reviews") or 0 or 0)

    reasons: list[str] = []
    comps: dict[str, int] = {}

    # Outdated website / modernization opportunity.
    if not website:
        comps["outdated_website"] = 85
        reasons.append("no website (modernization candidate)")
    elif any(d in website.lower() for d in (".wix", "weebly", "wordpress.com", ".blogspot")):
        comps["outdated_website"] = 65
        reasons.append("template site")
    else:
        comps["outdated_website"] = 40
        reasons.append("has website")

    # Digital presence.
    presence = 30
    if website:
        presence += 20
    if rating and rating >= 4.0:
        presence += 20
    if reviews >= 10:
        presence += 15
    if phone:
        presence += 15
    comps["digital_presence"] = min(100, presence)
    reasons.append(f"reviews={reviews} rating={rating or 'n/a'}")

    # Operational pain (labor-heavy + signals).
    pain = 20
    if any(k in cat_lower for k in LABOR_INTENSIVE):
        pain += 40
        reasons.append("labor-intensive category")
    if reviews == 0:
        pain += 10
        reasons.append("low review volume")
    comps["operational_pain"] = min(100, pain)

    # Automation opportunity.
    auto = 25
    if any(k in cat_lower for k in LABOR_INTENSIVE):
        auto += 30
    if any(k in cat_lower for k in CONTECH):
        auto += 20
        reasons.append("contech fit")
    if not website:
        auto += 15
    comps["automation_opportunity"] = min(100, auto)

    # Company size (review-count + category proxy).
    if reviews >= 100:
        size = 90
    elif reviews >= 30:
        size = 70
    elif reviews >= 10:
        size = 50
    elif reviews >= 1:
        size = 35
    else:
        size = 25
    comps["company_size"] = size
    reasons.append(f"size proxy: {reviews} reviews")

    # Growth / activity (rating recency + volume proxy).
    growth = 30
    if rating and rating >= 4.5 and reviews >= 10:
        growth += 40
        reasons.append("active + highly rated")
    elif rating and rating >= 4.0:
        growth += 20
    comps["growth_activity"] = min(100, growth)

    # Ability to pay (size + presence of phone/website).
    pay = comps["company_size"]
    if phone:
        pay += 10
    if website:
        pay += 5
    comps["ability_to_pay"] = min(100, pay)

    # Service fit.
    fit = 25
    if any(k in cat_lower for k in LABOR_INTENSIVE):
        fit += 30
    if any(k in cat_lower for k in CONTECH):
        fit += 30
    comps["service_fit"] = min(100, fit)

    total = int(round(
        comps["operational_pain"] * 0.20
        + comps["outdated_website"] * 0.15
        + comps["digital_presence"] * 0.10
        + comps["automation_opportunity"] * 0.20
        + comps["company_size"] * 0.10
        + comps["growth_activity"] * 0.10
        + comps["ability_to_pay"] * 0.10
        + comps["service_fit"] * 0.05
    ))
    trace = [{"component": k, "score": comps[k], "reason": ""} for k in comps]
    return {"total": total, "fit_score": comps["service_fit"],
            "pay_score": comps["ability_to_pay"], "component_scores": comps,
            "reasons": reasons, "trace": trace, "category": category}


def _as_float(x: Any) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def to_prospect(row: dict, source_name: str, query: str) -> BusinessProspect:
    scored = score_business(row)
    name = str(row.get("name") or "").strip()
    url = str(row.get("link") or row.get("url") or row.get("website") or "").strip()
    city = str(row.get("city") or "").strip()
    state = str(row.get("state") or "").strip()
    phone = str(row.get("phone_number") or row.get("phone") or "").strip()
    owner = str(row.get("owner_name") or row.get("founder") or "").strip()

    return BusinessProspect(
        prospect_id=f"BIZ-{abs(hash(name or url)):08x}" if (name or url) else "",
        company_name=name,
        category=scored["category"],
        website=str(row.get("website") or "").strip(),
        business_phone=phone,
        owner_name=owner,
        city=city,
        state=state,
        rating=_as_float(row.get("rating")),
        review_count=int(row.get("review_count") or row.get("reviews") or 0 or 0),
        source=source_name,
        source_url=url or GMAPS_RAPIDAPI_URL,
        signals=[r.split("(")[0].strip() for r in scored["reasons"][:3]],
        scores=scored["component_scores"],
        fit_score=scored["fit_score"],
        pay_score=scored["pay_score"],
        reason_trace=scored["trace"],
        verification_status="VERIFIED" if phone else "PARTIAL",
        confidence=0.9 if phone else 0.5,
        raw={"query": query},
    )


# ── pipeline / CLI ─────────────────────────────────────────────────────────

def run_prospecting(queries: list[str], limit: int = 20, source: Optional[ProspectSource] = None,
                    apply: bool = False) -> dict:
    src = source or GoogleMapsBusinessSource()
    if src.requires_key():
        return {
            "status": "blocked",
            "inputs": {"queries": queries, "limit": limit},
            "outputs": {"prospects": []},
            "errors": ["RAPIDAPI_KEY not configured — authorized business source required"],
            "next_action": "configure RAPIDAPI_KEY or add an authorized person source",
        }

    all_rows: list[dict] = []
    diagnostics: list[dict] = []
    for q in queries:
        rows, diag = src.fetch(q, limit)
        for r in rows:
            r["_query"] = q
        all_rows.extend(rows)
        diagnostics.append({"query": q, **diag})

    prospects = [to_prospect(r, src.name, r.get("_query", "")) for r in all_rows]
    unique: dict[str, BusinessProspect] = {}
    for p in prospects:
        if p.prospect_id:
            unique.setdefault(p.prospect_id, p)
    prospects = list(unique.values())
    prospects.sort(key=lambda p: -p.fit_score)

    out = {
        "status": "success",
        "inputs": {"queries": queries, "limit": limit, "source": src.name},
        "outputs": {"raw_rows": len(all_rows), "prospects": len(prospects)},
        "errors": [d.get("error") for d in diagnostics if d.get("error")],
        "next_action": "human_review_and_outreach",
    }

    if apply and prospects:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = ARTIFACTS / f"business_prospects_{ts}.json"
        csv_path = ARTIFACTS / f"business_prospects_{ts}.csv"
        json_path.write_text(json.dumps([asdict(p) for p in prospects], indent=2), encoding="utf-8")
        fields = [f for f in asdict(prospects[0]).keys() if f not in ("raw",)]
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for p in prospects:
                d = asdict(p)
                d.pop("raw", None)
                writer.writerow(d)
        out["outputs"]["artifacts"] = [str(json_path), str(csv_path)]

    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Business-owner AI services prospecting")
    ap.add_argument("--query", help="Single search query")
    ap.add_argument("--queries-file", type=Path, help="JSON list of queries")
    ap.add_argument("--source", type=Path, help="Pre-collected business rows JSON (offline scoring)")
    ap.add_argument("--list-queries", action="store_true")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--apply", action="store_true", help="Write artifacts")
    args = ap.parse_args(argv)

    if args.list_queries:
        print("\n".join(DEFAULT_QUERIES))
        return 0

    if args.queries_file:
        queries = json.loads(args.queries_file.read_text(encoding="utf-8"))
    elif args.query:
        queries = [args.query]
    else:
        queries = DEFAULT_QUERIES

    source: Optional[ProspectSource] = None
    if args.source:
        source = FileBusinessSource(args.source)
        queries = [args.source.stem]

    report = run_prospecting(queries, limit=args.limit, source=source, apply=args.apply)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())