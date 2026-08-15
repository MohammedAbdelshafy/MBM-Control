"""auction_freshness -- Auction.com foreclosure/auction discovery + freshness.

Responsibilities (jarvis-mbm#23):
  - Ingest Auction.com residential listings (live Playwright scrape, best-effort)
    or a pre-collected JSON/CSV file.
  - Normalize address/city/state/county/parcel + auction date/status + bid/value.
  - Prioritize genuinely fresh opportunities (auction-date recency, foreclosure
    status, vacancy/distress, bid-vs-value, APN presence, source evidence).
  - NEVER fabricate: a blocked/failed scrape yields an empty result + a
    'blocked' diagnostic, never mock rows. Owner fields are never set here.

CLI:
  python auction_freshness.py --state TX --county Dallas            # live scrape
  python auction_freshness.py --source FILE.json --apply            # pre-collected
  python auction_freshness.py --max-pages 2 --debug
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .normalize import dedupe_key, normalize_record
from .schema import AuctionRecord, PropertyRecord, money_to_float

BASE = Path(__file__).resolve().parent
ARTIFACTS = BASE / "artifacts"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

AuctionResidential = "https://www.auction.com/residential"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ── Live Playwright scrape (best-effort; no mock fallback) ────────────────

def _extract_row(card) -> Optional[dict]:
    def txt(sel: str, default: str = "") -> str:
        try:
            return card.locator(sel).inner_text(timeout=1200).strip()
        except Exception:  # noqa: BLE001
            return default

    address1 = txt('h4[data-elm-id="asset_address_1"]')
    address2 = txt('h4[data-elm-id="asset_address_2"]')
    if not address1 and not address2:
        return None
    return {
        "address": f"{address1}, {address2}".strip(" ,"),
        "opening_bid": txt('span[data-elm-id="asset_starting_bid"]'),
        "estimated_value": txt('span[data-elm-id="asset_est_value"]'),
        "auction_date": txt('[data-elm-id="asset_auction_date"], [data-elm-id="sale_date"]'),
        "auction_status": "foreclosure",
        "source": "auction.com",
        "source_url": AuctionResidential,
        "raw": {"address1": address1, "address2": address2},
    }


def scrape_auction_com(state: str = "", county: str = "", max_pages: int = 1, debug: bool = False) -> tuple[list[dict], dict]:
    """Scrape Auction.com residential pages. Returns (rows, diagnostics).

    On Cloudflare/block/failure returns ([], {"blocked": True, "error": ...})
    -- never mock data.
    """
    diag: dict[str, Any] = {"blocked": False, "pages": 0, "rows": 0}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        return [], {"blocked": True, "error": f"playwright not installed: {exc}"}

    rows: list[dict] = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()
            page.set_default_timeout(30000)

            base = AuctionResidential
            if county and state:
                slug = f"{county.lower().replace(' ', '-')}_{state.lower()}"
                base = f"{AuctionResidential}/{slug}"
            elif state:
                base = f"{AuctionResidential}?state={state}"

            for page_no in range(1, max_pages + 1):
                url = base if page_no == 1 else f"{base}?p={page_no}"
                diag["pages"] += 1
                try:
                    page.goto(url, timeout=30000)
                    page.wait_for_selector('div[data-elm-id="asset_root"]', timeout=15000)
                except Exception as exc:  # noqa: BLE001
                    diag["blocked"] = True
                    diag["error"] = f"page {page_no}: {type(exc).__name__}: {exc}"
                    if debug:
                        try:
                            (ARTIFACTS / "auction_debug.html").write_text(
                                page.content(), encoding="utf-8"
                            )
                        except Exception:  # noqa: BLE001
                            pass
                    break
                cards = page.locator('div[data-elm-id="asset_root"]').all()
                for card in cards:
                    row = _extract_row(card)
                    if row:
                        rows.append(row)
                if len(cards) == 0:
                    diag["blocked"] = True
                    diag["error"] = f"page {page_no}: no asset cards found"
                    break
            browser.close()
    except Exception as exc:  # noqa: BLE001
        return [], {"blocked": True, "error": f"{type(exc).__name__}: {exc}"}

    diag["rows"] = len(rows)
    return rows, diag


# ── Freshness scoring (issue #23 auction freshness) ───────────────────────

AUCTION_DATE_STATUS = {
    "foreclosure": 30,
    "pre-foreclosure": 25,
    "tax_deed": 26,
    "bankruptcy": 22,
    "reo": 14,
}


def days_until_auction(auction_date: str) -> Optional[int]:
    if not auction_date:
        return None
    try:
        dt = datetime.fromisoformat(auction_date.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (dt - datetime.now(timezone.utc)).days
    except ValueError:
        return None


def score_freshness(rec: dict) -> dict:
    """0-100 freshness: recency, status, distress, bid/value, APN, evidence.

    Returns {score, components, reasons}. Missing data lowers the score but is
    never invented.
    """
    reasons: list[str] = []
    components: dict[str, int] = {}

    # Auction-date recency (most important).
    days = days_until_auction(rec.get("auction_date", ""))
    if days is None:
        recency = 20
        reasons.append("no auction date")
    elif days < 0:
        recency = 45
        reasons.append(f"auction already passed ({-days}d ago)")
    elif days <= 7:
        recency = 95
        reasons.append(f"auction within 7 days ({days}d)")
    elif days <= 30:
        recency = 80
        reasons.append(f"auction within 30 days ({days}d)")
    elif days <= 90:
        recency = 55
        reasons.append(f"auction within 90 days ({days}d)")
    else:
        recency = 30
        reasons.append(f"auction far out ({days}d)")
    components["recency"] = recency

    # Auction status severity.
    status = str(rec.get("auction_status") or "").strip().lower()
    if status:
        status_score = AUCTION_DATE_STATUS.get(status, 15)
        reasons.append(f"status={status}")
    else:
        status_score = 10
        reasons.append("status unknown")
    components["status"] = status_score

    # Distress / vacancy signals.
    signals = rec.get("distress_signals") or []
    vac = str(rec.get("occupancy_signal") or "").strip().lower()
    if vac == "vacant":
        signals = list(signals) + ["vacant"]
    distress = min(100, len(signals) * 25 + (20 if vac == "vacant" else 0))
    components["distress"] = distress
    if signals:
        reasons.append(f"distress={','.join(signals)}")

    # Opening bid vs estimated value opportunity.
    bid = money_to_float(rec.get("opening_bid"))
    value = money_to_float(rec.get("estimated_value"))
    if bid is not None and value and value > 0:
        ratio = bid / value
        equity = max(0, int((1.0 - ratio) * 100))
        components["bid_value"] = equity
        reasons.append(f"bid/value={ratio:.0%}")
    else:
        components["bid_value"] = 30
        reasons.append("no bid/value data")

    # APN availability (evidence strength).
    parcel = str(rec.get("parcel_id") or "").strip()
    apn = 100 if parcel else 25
    components["apn"] = apn
    reasons.append("apn present" if parcel else "no apn")

    # Source evidence.
    src = str(rec.get("source") or "").strip()
    src_url = str(rec.get("source_url") or "").strip()
    evidence = 100 if (src and src_url) else 40
    components["evidence"] = evidence
    reasons.append(f"source={src or 'unknown'}")

    score = int(round(
        0.30 * recency
        + 0.20 * status_score
        + 0.15 * distress
        + 0.15 * components["bid_value"]
        + 0.10 * apn
        + 0.10 * evidence
    ))
    return {"score": score, "components": components, "reasons": reasons}


# ── Normalize scraped/pre-collected rows ──────────────────────────────────

def rows_to_properties(rows: list[dict]) -> list[dict]:
    """Convert raw listing rows into normalized property dicts + freshness."""
    out: list[dict] = []
    for row in rows:
        norm = normalize_record(row)
        norm["parcel_id"] = norm["parcel_id"] or (row.get("parcel_id") or "").strip()
        norm["dedupe_key"] = dedupe_key(
            norm["parcel_id"], norm["address"] or norm["address_normalized"], norm["state"]
        )
        if norm.get("auction_status") in ("", "unknown"):
            norm["auction_status"] = "foreclosure"
        fresh = score_freshness(norm)
        norm["freshness_score"] = fresh["score"]
        norm["freshness_components"] = fresh["components"]
        norm["freshness_reasons"] = fresh["reasons"]
        out.append(norm)
    return out


def load_source(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"source not found: {path}")
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8") as fh:
            return list(csv.DictReader(fh))
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    return data.get("listings", data.get("rows", data.get("leads", [])))


def export(records: list[dict], out_dir: Path) -> tuple[Path, Path]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = out_dir / f"auction_fresh_{ts}.json"
    csv_path = out_dir / f"auction_fresh_{ts}.csv"
    json_path.write_text(json.dumps(records, indent=2, default=str), encoding="utf-8")
    if records:
        fields = list(records[0].keys())
        with csv_path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
    return json_path, csv_path


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Auction.com freshness ingestion")
    ap.add_argument("--source", type=Path, help="Pre-collected JSON/CSV file (skip live scrape)")
    ap.add_argument("--state", default="", help="Scrape state (e.g. TX)")
    ap.add_argument("--county", default="", help="Scrape county (e.g. Dallas)")
    ap.add_argument("--max-pages", type=int, default=1)
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--apply", action="store_true", help="Write artifacts")
    args = ap.parse_args(argv)

    if args.source:
        rows = load_source(args.source)
        diag = {"blocked": False, "source": str(args.source), "rows": len(rows)}
    else:
        rows, diag = scrape_auction_com(args.state, args.county, args.max_pages, args.debug)

    props = rows_to_properties(rows)
    props.sort(key=lambda r: -r.get("freshness_score", 0))

    print(json.dumps({
        "status": "success" if rows else "blocked" if diag.get("blocked") else "failure",
        "inputs": {"source": str(args.source or "auction.com"), "state": args.state, "county": args.county},
        "outputs": {"rows": len(rows), "properties": len(props), "diagnostics": diag},
        "errors": [diag["error"]] if diag.get("error") else [],
        "next_action": "verify_ownership" if props else "resolve_blocker",
    }, indent=2, default=str))

    if props:
        print("\nTop fresh opportunities:")
        for r in props[:10]:
            print(f"  [{r.get('freshness_score')}] {r.get('address')} "
                  f"{r.get('city')} {r.get('state')} county={r.get('county') or '?'} "
                  f"auction={r.get('auction_date')} status={r.get('auction_status')}")

    if args.apply:
        json_p, csv_p = export(props, ARTIFACTS)
        print(f"\nWrote {json_p.name} ({len(props)} rows) and {csv_p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())