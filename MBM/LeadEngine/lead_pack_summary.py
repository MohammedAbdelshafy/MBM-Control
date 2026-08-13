#!/usr/bin/env python3
"""lead_pack_summary.py — print the lead-pack build result to the CI step summary."""
import json
import sys


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "lead_pack_result.json"
    try:
        d = json.load(open(path))
    except Exception as e:
        print(f"- could not read result json: {e}")
        return
    o = d.get("outputs", {})
    ans = "YES (ship to subscriber)" if o.get("gate_passed") else "NO (fix contact verification)"
    print("- count={} verified={} rate={}".format(o.get("count"), o.get("verified_count"), o.get("verification_rate")))
    print("- gate_passed: **{}**".format(ans))
    print("- csv={}".format(o.get("csv_path")))
    print("- next_action={}".format(d.get("next_action")))


if __name__ == "__main__":
    main()