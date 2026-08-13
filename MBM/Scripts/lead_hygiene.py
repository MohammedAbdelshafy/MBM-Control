#!/usr/bin/env python3
"""
Lead Hygiene Gate — Strip Fabricated/Synthetic Data From Every Feed
====================================================================
THE PROBLEM:
  The pipeline has been producing volume that never converts because much of
  the "data" is synthetic:
    - Placeholder emails (info@<truncated-name>.com guesses of a real org)
    - Generated phone numbers (sequential / 555 / random 10-digit filler)
    - Fake persona rows ("Robert Sterling #1", X company, non-existent domain)

THE FIX (real, verifiable checks — no human judgment calls):
  1. PHONE   -> must be a valid 10-digit US number (no 555 / 000 / dup-mid).
  2. DOMAIN  -> the email's domain must resolve via DNS (MX or A/AAAA record).
  3. DEDUPE  -> collapse on canonical phone; a lead without phone is idle.
  4. FLAG    -> obvious synthetic markers are quarantined, not silently kept.

OUTPUT (non-destructive — originals untouched):
  - Artifacts/lead_hygiene_report.csv : every row + PASS/PHONE_ONLY/FLAG + reason
  - Artifacts/real_leads.csv           : rows that passed, ready for the dialer
  - Artifacts/quarantined_leads.csv    : flagged rows (for manual triage)
  - Scripts/logs/lead_hygiene_summary.json

This gate is the FIRST stage of every revenue run. Nothing dials until it can
prove the phone is real and the owner actually exists.

Usage:
  python MBM/Scripts/lead_hygiene.py                 # run the full gate
  python MBM/Scripts/lead_hygiene.py --verify file   # analyze one file, exit
  python MBM/Scripts/lead_hygiene.py --no-net        # skip DNS lookups
  python MBM/Scripts/lead_hygiene.py --sources       # list searched sources
"""

import csv
import json
import re
import sys
import socket
import argparse
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

BASE = Path(__file__).resolve().parent
MBM = BASE.parent
LE = MBM / "LeadEngine"

DEFAULT_SOURCES = {
    "pipeline.csv": MBM / "Pipeline" / "pipeline.csv",
    "cold_calling_queue.json": LE / "cold_calling_queue.json",
    "real_estate_calling_queue.json": LE / "real_estate_calling_queue.json",
    "enriched_global_leads.json": LE / "enriched_global_leads.json",
    "global_leads.json": LE / "global_leads.json",
    "us_wholesalers.json": LE / "us_wholesalers.json",
    "top_100_prospects.csv": MBM / "Clients" / "top_100_prospects_to_call.csv",
    "top_300_prospects.csv": MBM / "Clients" / "top_300_prospects_to_call.csv",
}

# Text markers of a fabricated / placeholder persona
SYNTHETIC_NAME_MARKERS = [
    "robert sterling", "elena rostova", "john doe", "jane doe",
    "michael smith", "test", "example", "placeholder", "sample",
]
SYNTHETIC_DOMAINS = [
    "propertyleads.com", "example.com", "test.com", "sample.com",
    "placeholder.com", "yourdomain.com",
]
BAD_EXCHANGE = {"555", "000"}


def clean_phone(raw):
    """Return canonical +1<10digits> or '' if not a plausible real US number."""
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 10:
        if digits[3:6] in BAD_EXCHANGE:
            return ""
        return "+1" + digits
    if len(digits) == 11 and digits[0] == "1":
        d10 = digits[1:]
        if d10[3:6] in BAD_EXCHANGE:
            return ""
        return "+1" + d10
    return ""


def _domain_of(email):
    m = re.search(r"@([\w.-]+)\s*$", (email or "").strip().lower())
    return m.group(1) if m else ""


def _mx_record(domain, cache):
    """Check domain has an MX or A record via DNS. Returns bool (cached)."""
    domain = domain.lower().strip(".")
    if not domain or "." not in domain:
        return False
    if domain in cache:
        return cache[domain]
    ok = False
    try:
        socket.setdefaulttimeout(4)
        try:
            import DNS  # dnspython
            mx = DNS.MailServerLookup(domain)
            ok = bool(mx)
        except ImportError:
            ok = False
        except Exception:
            ok = False
        if not ok:
            try:
                socket.getaddrinfo(domain, None)
                ok = True
            except Exception:
                ok = False
    except Exception:
        ok = False
    cache[domain] = ok
    return ok


def _flag_synthetic_name(name):
    n = (name or "").lower()
    return any(m in n for m in SYNTHETIC_NAME_MARKERS)


def _flag_synthetic_domain(domain):
    d = (domain or "").lower().strip(".")
    return any(s in d for s in SYNTHETIC_DOMAINS)


def assess_row(row, mx_cache, with_net=True):
    """Return (clean_phone, verdict, reasons, email_domain)."""
    name = (row.get("contact_name") or row.get("owner_name")
            or row.get("name") or row.get("company_name") or "")
    phone_raw = (row.get("phone_number") or row.get("phone") or row.get("contact_phone")
                 or row.get("agent_phone") or row.get("telephone_number") or "")
    email = (row.get("email") or row.get("contact_email") or row.get("owner_email")
             or row.get("agent_email") or row.get("emails") or "")
    if isinstance(email, list):
        email = email[0] if email else ""

    phone = clean_phone(phone_raw)
    domain = _domain_of(email)
    reasons = []

    if not phone:
        reasons.append("no_valid_phone")
    if not domain:
        reasons.append("no_email_domain")
    if domain and with_net and not _mx_record(domain, mx_cache):
        reasons.append(f"domain_no_dns:{domain}")
    if domain and _flag_synthetic_domain(domain):
        reasons.append(f"synthetic_domain:{domain}")
    if _flag_synthetic_name(name):
        reasons.append(f"synthetic_name:{name}")

    # Hard fail: unusable phone OR unmistakable synthetic persona.
    hard_fail = (
        not phone
        or _flag_synthetic_domain(domain)
        or _flag_synthetic_name(name)
    )

    if hard_fail:
        verdict = "FLAG"
    elif domain and "domain_no_dns" not in reasons:
        verdict = "PASS"
    else:
        # Real phone, missing/unverifiable email -> still dialable.
        verdict = "PHONE_ONLY"

    return phone, verdict, "; ".join(reasons), domain


def _verdict_rank(r):
    return {"FLAG": 0, "PHONE_ONLY": 1, "PASS": 2}.get(r.get("_verdict"), 0)


def read_rows(path):
    p = Path(path)
    if not p.exists():
        return []
    if p.suffix.lower() == ".csv":
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                return list(csv.DictReader(f))
        except Exception:
            return []
    try:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, dict):
        data = (data.get("queue") or data.get("leads")
                or data.get("result") or data.get("data"))
    if not isinstance(data, list):
        return []
    return [d if isinstance(d, dict) else {"contact_name": "Unknown", "phone": d}
            for d in data]


def row_to_flat(row, source, phone, verdict, reason, domain):
    base = dict(row)
    base["_source_file"] = source
    base["_clean_phone"] = phone
    base["_verdict"] = verdict
    base["_reason"] = reason
    base["_domain"] = domain
    return base


def run_gate(sources=None, with_net=True, out_dir=None):
    out_dir = out_dir or (MBM / "Artifacts")
    out_dir.mkdir(parents=True, exist_ok=True)
    (BASE / "logs").mkdir(exist_ok=True)
    mx_cache = {}

    all_rows = []
    for name, path in (sources or DEFAULT_SOURCES).items():
        for r in read_rows(path):
            phone, verdict, reason, domain = assess_row(r, mx_cache, with_net)
            all_rows.append(row_to_flat(r, name, phone, verdict, reason, domain))

    # Dedup by clean phone (keep highest verdict)
    best = {}
    for r in all_rows:
        key = r["_clean_phone"] or (r.get("email") or "").lower() or (
            f"{r['_source_file']}#{r.get('contact_name') or r.get('name') or ''}")
        if key not in best or _verdict_rank(r) > _verdict_rank(best[key]):
            best[key] = r
    deduped = list(best.values())

    pass_rows = [r for r in deduped if r["_verdict"] == "PASS"]
    phone_only = [r for r in deduped if r["_verdict"] == "PHONE_ONLY"]
    flagged = [r for r in deduped if r["_verdict"] == "FLAG"]

    all_keys = sorted({k for r in deduped for k in r.keys()})

    def _write(name, rows):
        with open(out_dir / name, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=all_keys, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

    _write("lead_hygiene_report.csv", deduped)
    _write("real_leads.csv", pass_rows + phone_only)
    _write("quarantined_leads.csv", flagged)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sources_scanned": list((sources or DEFAULT_SOURCES).keys()),
        "total_rows": len(deduped),
        "pass": len(pass_rows),
        "phone_only": len(phone_only),
        "flagged": len(flagged),
        "pass_rate": f"{len(pass_rows) / max(1, len(deduped)) * 100:.1f}%",
        "outputs": {
            "report": str(out_dir / "lead_hygiene_report.csv"),
            "real_leads": str(out_dir / "real_leads.csv"),
            "quarantined": str(out_dir / "quarantined_leads.csv"),
        },
    }
    with open(BASE / "logs" / "lead_hygiene_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    print(json.dumps(summary, indent=2))
    return summary, pass_rows, phone_only, flagged


def analyze_file(path, with_net=True):
    mx_cache = {}
    rows = []
    for r in read_rows(path):
        phone, verdict, reason, domain = assess_row(r, mx_cache, with_net)
        rows.append(row_to_flat(r, Path(path).name, phone, verdict, reason, domain))
    for x in rows:
        print(f"{x['_verdict']:10} {x['_clean_phone']:16} "
              f"{x['_domain']:<28} {x['_reason']}")
    print(dict(Counter(x["_verdict"] for x in rows)))


def list_sources():
    for k, v in DEFAULT_SOURCES.items():
        print(f"{(k):<28} exists={v.exists()}  -> {v}")


def main():
    ap = argparse.ArgumentParser(description="Lead Hygiene Gate")
    ap.add_argument("--no-net", action="store_true", help="Skip DNS lookups (offline)")
    ap.add_argument("--verify", help="Analyze one file then exit", type=str)
    ap.add_argument("--sources", action="store_true", help="List searched sources and exit")
    args = ap.parse_args()

    if args.sources:
        list_sources()
        sys.exit(0)
    if args.verify:
        analyze_file(args.verify, with_net=not args.no_net)
        sys.exit(0)

    run_gate(with_net=not args.no_net)


if __name__ == "__main__":
    main()
