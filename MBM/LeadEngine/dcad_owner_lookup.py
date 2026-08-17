"""
MBM DCAD Owner Lookup — Authoritative Dallas County parcel owner lookup
========================================================================
Queries the Dallas Central Appraisal District (DCAD) public ArcGIS REST API
by property address and returns the REAL registered owner name and mailing
address. This replaces the fabricated names/phones the free scraper produced.

Source: https://maps.dcad.org/prdwa/rest/services/Property/ParcelQuery/MapServer/4
(free public tax-parcel records, no API key required)

Usage:
    python dcad_owner_lookup.py --address "12124 SCHROEDER RD, DALLAS, TX 75243"
    python dcad_owner_lookup.py --file leads_database.json --vertical "Real Estate Sellers"
"""

import json
import os
import re
import sys
import time
import argparse
import urllib.parse
import urllib.request
from pathlib import Path

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from MBM.GLM.single_writer_lock import DialerSingleWriter
    _SINGLE_WRITER = DialerSingleWriter()
except Exception:
    _SINGLE_WRITER = None

def _save_enrichment(db, out_path):
    if _SINGLE_WRITER is not None:
        _SINGLE_WRITER.full_replace(db, author="DCAD_OWNER_LOOKUP")
    else:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=2, default=str)

DCAD_QUERY_URL = (
    "https://maps.dcad.org/prdwa/rest/services/Property/ParcelQuery/MapServer/4/query"
)
DCAD_FIELDS = (
    "SITEADDRESS,OWNERNME1,OWNERNME2,PSTLADDRESS,PSTLCITY,PSTLSTATE,PSTLZIP5,PARCELID"
)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "..", "..", "mbm-dialer", "app", "public", "leads_database.json")
CONF_PATH = os.path.join(BASE_DIR, "dcad_lookup_results.json")

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def clean_state(state):
    if not state:
        return ""
    m = re.search(r"[A-Za-z]{2}", state or "")
    return m.group(0).upper() if m else ""


def normalize_address(address):
    """Normalize a full address line into (number, street) for DCAD matching."""
    if not address:
        return None
    text = re.sub(r"[,\s]+", " ", str(address)).strip().upper()
    # Remove trailing city/state/zip
    text = re.sub(r"\b(?:DALLAS|TX|TEXAS|US)\b.*$", "", text).strip()
    text = re.sub(r"\s+\d{5}(?:-\d{4})?\s*$", "", text).strip()
    m = re.match(r"^(\d+)\s+(.+)$", text)
    if not m:
        return None
    return {"number": m.group(1), "street": m.group(2)}


def dcad_lookup(address, retries=3):
    """Query DCAD by address. Returns dict with owner name or None."""
    norm = normalize_address(address)
    if not norm:
        return None

    patterns = [
        "UPPER(SITEADDRESS) LIKE UPPER('%%%s%% %%%s%%')"
        % (norm["number"], norm["street"].split()[0]),
        "UPPER(SITEADDRESS) LIKE UPPER('%%%s%%') AND UPPER(SITEADDRESS) LIKE UPPER('%%%s%%')"
        % (norm["number"], norm["street"].split()[0]),
    ]
    for where in patterns:
        qs = urllib.parse.urlencode({
            "where": where,
            "outFields": DCAD_FIELDS,
            "returnGeometry": "false",
            "resultRecordCount": "10",
            "f": "json",
        })
        url = DCAD_QUERY_URL + "?" + qs
        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=25) as resp:
                    data = json.loads(resp.read().decode())
                feats = data.get("features", [])
                if not feats:
                    break
                # Prefer exact site-address match on number + first street word
                for ft in feats:
                    a = ft.get("attributes", {})
                    site = (a.get("SITEADDRESS") or "").strip().upper()
                    if site.startswith(norm["number"]):
                        owner1 = (a.get("OWNERNME1") or "").strip()
                        owner2 = (a.get("OWNERNME2") or "").strip()
                        owner = " & ".join(x for x in (owner1, owner2) if x) or None
                        return {
                            "owner": owner,
                            "site_address": (a.get("SITEADDRESS") or "").strip(),
                            "mail_address": (a.get("PSTLADDRESS") or "").strip(),
                            "mail_city": (a.get("PSTLCITY") or "").strip(),
                            "mail_state": clean_state(a.get("PSTLSTATE")),
                            "mail_zip": (a.get("PSTLZIP5") or "").strip(),
                            "parcel_id": (a.get("PARCELID") or "").strip(),
                        }
                # No exact number match -> first feature
                a = feats[0].get("attributes", {})
                return {
                    "owner": (" & ".join(x for x in (
                        (a.get("OWNERNME1") or "").strip(),
                        (a.get("OWNERNME2") or "").strip()) if x)) or None,
                    "site_address": (a.get("SITEADDRESS") or "").strip(),
                    "mail_address": (a.get("PSTLADDRESS") or "").strip(),
                    "mail_city": (a.get("PSTLCITY") or "").strip(),
                    "mail_state": clean_state(a.get("PSTLSTATE")),
                    "mail_zip": (a.get("PSTLZIP5") or "").strip(),
                    "parcel_id": (a.get("PARCELID") or "").strip(),
                }
            except Exception as exc:
                if attempt == retries - 1:
                    return {"error": str(exc)}
                time.sleep(1.0 * (attempt + 1))
    return None


def title_case_owner(name):
    """Convert 'CHANDLER TAMECA' -> 'Tameca Chandler' (First Last).

    Company/trust entities (LLC, LP, INC, TRUST, GROUP, PROPERTIES, etc.)
    are left in their record form. Trailing '&' from a truncated joint
    owner field is dropped.
    """
    if not name:
        return name
    upper = name.upper()
    is_entity = any(k in upper for k in (
        "LLC", " LP", "INC", "TRUST", "GROUP", "PROPERTIES", "PROPERTY",
        "INVESTMENTS", "REALTY", "HOLDINGS", "LTD", "CORP", "COMPANY", "COMPANY", "PARTNERSHIP", "LLP", "PA"
    ))
    if is_entity:
        return name.strip().rstrip("&").strip()
    parts = [p for p in re.split(r"[&,]", name) if p.strip()]
    out = []
    for part in parts:
        words = [w for w in part.strip().split() if w]
        if not words:
            continue
        named = []
        for w in words:
            if w == "&":
                continue
            if len(w) == 1:
                named.append(w.upper() + ".")
            else:
                named.append(w.title())
        out.append(" ".join(named))
    return " & ".join(out).rstrip("&").strip()


def enrich_file(db_path, verticals=None, out_path=None, dry_run=False):
    with open(db_path, encoding="utf-8") as f:
        db = json.load(f)

    target = [l for l in db if l.get("vertical") in verticals]
    if dry_run:
        print("[dry-run] would process %d leads" % len(target))
        sample = 5
    print("Processing %d leads in verticals %s" % (len(target), verticals or "ALL"))

    stats = {"lookups": 0, "found": 0, "updated": 0, "failed": 0, "no_address": 0}
    cache = {}

    for i, lead in enumerate(target):
        d = lead.get("details") or {}
        address = d.get("Property_Address") or d.get("Address") or ""
        if not address:
            stats["no_address"] += 1
            continue
        key = re.sub(r"[^A-Z0-9]", "", str(address).upper())
        if key in cache:
            result = cache[key]
        else:
            result = dcad_lookup(address)
            cache[key] = result
            stats["lookups"] += 1
            time.sleep(0.2)

        if result and result.get("owner"):
            stats["found"] += 1
            owner_name = title_case_owner(result["owner"])
            if not dry_run:
                lead["contact"] = owner_name
                d["Owner_Name"] = owner_name
                d["DCAD_Owner_Confirmed"] = "yes"
                d["Site_Address"] = result.get("site_address") or ""
                if result.get("mail_address"):
                    d["Owner_Mail_Address"] = result.get("mail_address")
                    d["Owner_Mail_City"] = result.get("mail_city") or ""
                    d["Owner_Mail_State"] = result.get("mail_state") or ""
                    d["Owner_Mail_Zip"] = result.get("mail_zip") or ""
                d["DCAD_Parcel_ID"] = result.get("parcel_id") or ""
                d["Skip_Trace_Source"] = "dcad"
                d["Skip_Trace_Confidence"] = "high"
                if d.get("Call_Script"):
                    prop = d.get("Property_Address") or "your property"
                    d["Call_Script"] = "Hi %s, I'm calling from MBM regarding the property at %s. We're local buyers looking for a few more properties this month and wanted to see if you've considered selling, or would be open to a cash offer?" % (owner_name, prop)
                stats["updated"] += 1
        elif result is None:
            stats["no_address"] += 1
        else:
            stats["failed"] += 1

        if i % 20 == 0:
            print("  %d/%d  found=%d failed=%d" % (i + 1, len(target), stats["found"], stats["failed"]), flush=True)

        # Checkpoint: save partial results every 25 leads so a long run can be resumed
        if not dry_run and out_path and i % 25 == 0 and i > 0:
            _save_enrichment(db, out_path)
            print("  [checkpoint @%d saved]" % (i + 1), flush=True)

    print("STATS: %r" % stats, flush=True)

    if dry_run:
        # Show first 5 found
        shown = 0
        for lead in target:
            d = lead.get("details") or {}
            if d.get("DCAD_Owner_Confirmed") == "yes":
                print("  %s => %s" % (d.get("Property_Address"), lead["contact"]))
                shown += 1
                if shown >= sample:
                    break
        return db

    if out_path:
        _save_enrichment(db, out_path)
        print("Saved enrichment to %s" % out_path)
    return db


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DCAD owner lookup")
    parser.add_argument("--address", type=str, help="Single address lookup")
    parser.add_argument("--file", type=str, help="Leads JSON file to enrich")
    parser.add_argument("--vertical", type=str, default="Real Estate Sellers", help="Vertical(s) comma-separated")
    parser.add_argument("--out", type=str, help="Output file (default: overwrite input)")
    parser.add_argument("--dry-run", action="store_true", help="Report only, no writes")
    args = parser.parse_args()

    if args.address:
        res = dcad_lookup(args.address)
        print(json.dumps(res, indent=2))
    elif args.file:
        verts = [v.strip() for v in args.vertical.split(",")]
        enrich_file(args.file, verticals=verts, out_path=args.out, dry_run=args.dry_run)
    else:
        print("USAGE: python dcad_owner_lookup.py --address '...' | --file <json> [--vertical X,Y]")