#!/usr/bin/env python3
"""
SYNTHETIC PRODUCTION QUARANTINE TOOL
=============================================================================
Moves every fabricated (synthetic) record out of active production surfaces
and into an evidence-preserving quarantine bundle, leaving ONLY real leads
in production.

Surfaces scanned (default all):
  - mbm-dialer/app/public/leads_database.json  (via single-writer lock)
  - MBM/Artifacts/canonical_deals_memory.json
  - MBM/Artifacts/GTM_TOP25_EXECUTION_QUEUE.json
  - MBM/Artifacts/lead_history_ledger.json
  - MBM/Artifacts/GTM/daily/*/lead_GEN-*.json + script_GEN-*.json artifacts

Classification uses STRONG synthetic fingerprints only (never ambiguous):
  - generated id        GEN-NEW-* / GEN-FAC-*
  - template company    <City> <Vertical> <Suffix>  (pool-based)
  - persona contact     known synthetic first+last name pools
  - sequential ref      /entity/{index} registry URL pattern

Generated-domain alone is NOT used: real NPI businesses legitimately own
slug-matching domains (e.g. ACTIVE PT SVCS -> activeptsvcs.com).

Usage:
  python quarantine_synthetic_production.py            # dry-run report
  python quarantine_synthetic_production.py --apply    # move synthetic out
=============================================================================
"""

from __future__ import annotations

import sys
import json
import shutil
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.lead_provenance import (
    is_template_company,
    is_persona_contact,
    is_sequential_registry_ref,
    is_fake_registry_ref,
)
from MBM.LeadEngine.dialer_db_lock import DialerDatabaseLock

DIALER_DB = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
CANONICAL_DB = ROOT_DIR / "MBM" / "Artifacts" / "canonical_deals_memory.json"
QUEUE_DB = ROOT_DIR / "MBM" / "Artifacts" / "GTM_TOP25_EXECUTION_QUEUE.json"
LEDGER_DB = ROOT_DIR / "MBM" / "Artifacts" / "lead_history_ledger.json"
DAILY_DIR = ROOT_DIR / "MBM" / "Artifacts" / "GTM" / "daily"
QUARANTINE_ROOT = ROOT_DIR / "MBM" / "Artifacts" / "GTM" / "quarantine"


def strong_synthetic(r: Dict[str, Any], id_keys=("id", "lead_id")) -> List[str]:
    """Strong synthetic fingerprints. Returns list of reasons ([] = real)."""
    reasons: List[str] = []
    idv = ""
    for k in id_keys:
        v = str(r.get(k, "") or "")
        if v:
            idv = v
            break
    if idv.startswith("GEN-NEW") or idv.startswith("GEN-FAC"):
        reasons.append("generated_id")
    company = str(r.get("company", "") or r.get("company_name", "") or "")
    if is_template_company(company):
        reasons.append("template_company")
    contact = str(
        r.get("decision_maker", "")
        or r.get("contact", "")
        or r.get("owner_name", "")
        or r.get("person_name", "")
        or ""
    )
    if is_persona_contact(contact):
        reasons.append("persona_contact")
    ref = str(r.get("source_reference", "") or r.get("source_url", "") or "")
    if is_sequential_registry_ref(ref) or is_fake_registry_ref(ref):
        reasons.append("sequential_ref")
    return reasons


def classify_rows(rows: List[Dict[str, Any]], id_keys=("id", "lead_id")):
    kept: List[Dict[str, Any]] = []
    synthetic: List[Tuple[Dict[str, Any], List[str]]] = []
    for r in rows:
        reasons = strong_synthetic(r, id_keys=id_keys)
        if reasons:
            synthetic.append((r, reasons))
        else:
            kept.append(r)
    return kept, synthetic


def report_surface(name: str, path: Path, id_keys=("id", "lead_id")):
    rows = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(rows, dict):
        rows = rows.get("leads", []) if isinstance(rows.get("leads"), list) else []
    kept, synthetic = classify_rows(rows, id_keys=id_keys)
    print(f"[{name}] total={len(rows)} synthetic={len(synthetic)} kept={len(kept)}")
    return rows, kept, synthetic


def run_dry_scan() -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    for name, path, idk in [
        ("dialer", DIALER_DB, ("id", "lead_id")),
        ("canonical", CANONICAL_DB, ("id", "lead_id")),
        ("queue", QUEUE_DB, ("id", "lead_id")),
        ("ledger", LEDGER_DB, ("lead_id", "id")),
    ]:
        if not path.exists():
            print(f"[{name}] MISSING {path}")
            continue
        _, kept, synthetic = report_surface(name, path, idk)
        summary[name] = {"total": len(kept) + len(synthetic), "synthetic": len(synthetic), "kept": len(kept)}
    # Daily artifact files (GEN-NEW leads/scripts) — JSON + stale markdown cards
    gen_files = (
        list(DAILY_DIR.rglob("lead_GEN-*.json"))
        + list(DAILY_DIR.rglob("script_GEN-*.json"))
        + list(DAILY_DIR.rglob("lead_GEN-*.md"))
        + list(DAILY_DIR.rglob("script_GEN-*.md"))
    )
    summary["daily_artifacts"] = {"total": len(gen_files), "synthetic": len(gen_files), "kept": 0}
    print(f"[daily_artifacts] total={len(gen_files)} synthetic={len(gen_files)} kept=0 (GEN-NEW files)")
    return summary


def apply_quarantine() -> Dict[str, Any]:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle = QUARANTINE_ROOT / ts
    bundle.mkdir(parents=True, exist_ok=True)
    manifest: Dict[str, Any] = {"timestamp": ts, "surfaces": {}}

    for name, path, idk in [
        ("dialer", DIALER_DB, ("id", "lead_id")),
        ("canonical", CANONICAL_DB, ("id", "lead_id")),
        ("queue", QUEUE_DB, ("id", "lead_id")),
        ("ledger", LEDGER_DB, ("lead_id", "id")),
    ]:
        if not path.exists():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(rows, dict):
            rows = rows.get("leads", []) if isinstance(rows.get("leads"), list) else []
        kept, synthetic = classify_rows(rows, id_keys=idk)

        # Preserve an unmodified backup for evidence.
        shutil.copy2(path, bundle / f"{name}_original_backup.json")

        if synthetic:
            # Quarantined records file.
            (bundle / f"{name}_synthetic.json").write_text(
                json.dumps([{"record": r, "reasons": rs} for r, rs in synthetic], indent=2),
                encoding="utf-8",
            )

        # Rewrite the production surface with ONLY real records.
        if name == "dialer":
            with DialerDatabaseLock() as lock:
                total = lock.write(
                    kept,
                    author="QUARANTINE_SYNTHETIC_PRODUCTION",
                    reason="quarantine",
                    allow_shrink=True,
                )
        else:
            path.write_text(json.dumps(kept, indent=2), encoding="utf-8")
            total = len(kept)
        manifest["surfaces"][name] = {
            "before": len(rows),
            "quarantined": len(synthetic),
            "after": total,
        }
        print(f"[{name}] quarantined={len(synthetic)} kept={len(kept)} written={total}")

    # Daily GEN-NEW artifact files -> move into the quarantine bundle.
    gen_files = (
        list(DAILY_DIR.rglob("lead_GEN-*.json"))
        + list(DAILY_DIR.rglob("script_GEN-*.json"))
        + list(DAILY_DIR.rglob("lead_GEN-*.md"))
        + list(DAILY_DIR.rglob("script_GEN-*.md"))
    )
    art_dir = bundle / "daily_artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for f in gen_files:
        rel = f.relative_to(DAILY_DIR)
        dest = art_dir / str(rel).replace("..", "__")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(f), str(dest))
        moved += 1
    manifest["surfaces"]["daily_artifacts"] = {"before": len(gen_files), "quarantined": moved, "after": 0}

    (bundle / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\n[OK] Quarantine bundle written to {bundle}")
    print(json.dumps(manifest, indent=2))
    return manifest


def verify_clean() -> Dict[str, Any]:
    """Re-scan every surface and assert zero strong-synthetic records remain."""
    results: Dict[str, Any] = {}
    for name, path, idk in [
        ("dialer", DIALER_DB, ("id", "lead_id")),
        ("canonical", CANONICAL_DB, ("id", "lead_id")),
        ("queue", QUEUE_DB, ("id", "lead_id")),
        ("ledger", LEDGER_DB, ("lead_id", "id")),
    ]:
        if not path.exists():
            continue
        rows = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(rows, dict):
            rows = rows.get("leads", []) if isinstance(rows.get("leads"), list) else []
        _, synthetic = classify_rows(rows, id_keys=idk)
        results[name] = {"total": len(rows), "synthetic": len(synthetic)}
    gen_files = (
        list(DAILY_DIR.rglob("lead_GEN-*.json"))
        + list(DAILY_DIR.rglob("script_GEN-*.json"))
        + list(DAILY_DIR.rglob("lead_GEN-*.md"))
        + list(DAILY_DIR.rglob("script_GEN-*.md"))
    )
    results["daily_artifacts"] = {"total": len(gen_files), "synthetic": len(gen_files)}
    print("POST-QUARANTINE VERIFICATION:")
    for name, res in results.items():
        print(f"  {name}: total={res['total']} synthetic={res['synthetic']}")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Quarantine synthetic leads from production.")
    parser.add_argument("--apply", action="store_true", help="Commit the quarantine (default is dry-run)")
    parser.add_argument("--verify", action="store_true", help="Re-scan surfaces and assert zero synthetic")
    args = parser.parse_args()

    if args.verify:
        results = verify_clean()
        bad = {k: v["synthetic"] for k, v in results.items() if v["synthetic"] > 0}
        print("\nRESULT:", "CLEAN - zero synthetic in production" if not bad else f"DIRTY {bad}")
        return 0 if not bad else 1

    if args.apply:
        apply_quarantine()
        print()
        verify_clean()
        return 0

    print("SYNTHETIC PRODUCTION QUARANTINE (dry-run) - use --apply to commit")
    run_dry_scan()
    return 0


if __name__ == "__main__":
    sys.exit(main())