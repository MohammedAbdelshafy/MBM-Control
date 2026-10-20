#!/usr/bin/env python3
"""lead_pack_summary.py — print the lead-pack build result to the CI step summary.

Reads the JSON printed by lead_pack_builder.py (dry-run or --apply manifest)
and reports counts + whether the verification gate passed. Tolerates the
builder's trailing human-readable lines after the JSON document.
"""
import json
import sys


def load_result(path):
    text = open(path, encoding="utf-8").read()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Builder appends "Wrote pack: ..." lines after the JSON in --apply mode.
        decoder = json.JSONDecoder()
        doc, _ = decoder.raw_decode(text)
        return doc


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "lead_pack_result.json"
    try:
        d = load_result(path)
    except Exception as e:
        print(f"- could not read result json: {e}")
        return

    status = d.get("status", "unknown")
    o = d.get("outputs") or {}
    # Apply-mode manifest nests counts under outputs; dry-run is flat.
    total = o.get("total_rows", d.get("total_rows"))
    verified = o.get("contact_verified", d.get("contact_verified"))
    rate = o.get("contact_verification_pct", d.get("contact_verification_pct"))
    gated = d.get("gated")
    shippable = (status == "ready") or (status == "dry_run" and gated is True)

    ans = "YES (ship to subscriber)" if shippable else "NO (fix contact verification)"
    print(f"- count={total} verified={verified} rate={rate}")
    print(f"- status={status} gate_passed: **{ans}**")
    csv_path = o.get("csv")
    if csv_path:
        print(f"- csv={csv_path}")
    print(f"- next_action={d.get('next_action')}")


if __name__ == "__main__":
    main()
