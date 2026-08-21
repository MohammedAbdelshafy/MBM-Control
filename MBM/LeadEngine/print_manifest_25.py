#!/usr/bin/env python3
import json
from pathlib import Path

p = Path("MBM/Artifacts/GTM/daily/2026-08-16/npi_242_manifest.json")
manifest = json.loads(p.read_text(encoding="utf-8"))
print("Total Manifest Records:", len(manifest["manifest"]))
print(f"{'#':<3} | {'FILENAME':<26} | {'NPI':<12} | {'PHONE':<14} | {'COMPANY':<32} | {'CONTACT':<20} | {'VERIFICATION'}")
print("-" * 125)
for idx, r in enumerate(manifest["manifest"][:25], start=1):
    print(f"{idx:<3} | {r['artifact_filename']:<26} | {r['npi']:<12} | {r['normalized_phone']:<14} | {r['company'][:32]:<32} | {r['contact'][:20]:<20} | {r['verification_method']}")
