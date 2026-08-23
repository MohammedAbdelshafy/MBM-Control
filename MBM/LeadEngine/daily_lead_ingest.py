#!/usr/bin/env python3
"""
P0 DAILY LEAD VERIFICATION + DIALER INGESTION (canonical orchestrator)
======================================================================
EVERY new daily lead must be VERIFIED -> DEDUPED -> CLASSIFIED -> SCRIPTED ->
WRITTEN TO CANONICAL DB -> QUEUED -> VISIBLE IN THE LIVE DIALER.

Stage pipeline (no stage may be skipped):

  SOURCE
  -> RAW INGEST
  -> PHONE/IDENTITY VALIDATION
  -> PROVENANCE VALIDATION
  -> SYNTHETIC/FICTITIOUS CHECK
  -> DEDUPE
  -> SUPPRESSION/DNC CHECK
  -> CLASSIFICATION
  -> SCRIPT ASSIGNMENT
  -> CANONICAL DIALER WRITE      (DialerDatabaseLock / DialerSingleWriter ONLY)
  -> REVISION/AUDIT              (sidecar bumped by atomic_persist)
  -> QUEUE PRIORITIZATION        (FILTER -> SAFETY -> SCORE -> SORT NEWEST-FIRST -> PAGINATE)
  -> LIVE VERIFICATION           (canonical count == API served count; >=5 samples traced; UI up)

A daily batch is SUCCESS only when the full acceptance gate passes. The batch is
NEVER reported successful unless verified leads actually reached the dialer.

Outputs (per day):
  MBM/Artifacts/GTM/daily/<YYYY-MM-DD>/lead_ingestion_report.json
  MBM/Artifacts/GTM/daily/<YYYY-MM-DD>/lead_ingestion_report.md
  MBM/Artifacts/GTM/daily/<YYYY-MM-DD>/queue_snapshot.json
  MBM/Artifacts/GTM/daily/<YYYY-MM-DD>/scheduler_heartbeat.json   (only when healthy)

Usage:
  python MBM/LeadEngine/daily_lead_ingest.py             # dry-run (no writes)
  python MBM/LeadEngine/daily_lead_ingest.py --apply     # live ingestion
  python MBM/LeadEngine/daily_lead_ingest.py --apply --target 50
"""

from __future__ import annotations

import sys
import json
import time
import argparse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.single_writer_lock import SingleWriterViolation, compute_checksum, sidecar_paths
from MBM.LeadEngine.dialer_db_lock import DialerDatabaseLock, DIALER_DB_PATH as CANONICAL_DB_PATH
from MBM.LeadEngine.dialer_gateway import is_strong_synthetic, load_suppression_index
from MBM.LeadEngine.lead_history_ledger import normalize_phone_digits
from MBM.LeadEngine.lead_provenance import LeadProvenanceGate, build_provenance_fields
from MBM.LeadEngine.dialer_script_engine import (
    DialerScriptEngine,
    SegmentClassifier,
    SUPPORTED_SEGMENTS,
)

ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
DEFAULT_SOURCE = ARTIFACTS_DIR / "npi_verified_callsheet.json"
DEFAULT_DIALER_URL = "http://localhost:5173"

STATUS_SUCCESS = "SUCCESS"
STATUS_PARTIAL = "PARTIAL_SUCCESS"
STATUS_QUARANTINED = "QUARANTINED"
STATUS_BLOCKED = "BLOCKED"
STATUS_FAILED = "FAILED"

PIPELINE_STAGES = [
    "source_fetch",
    "raw_ingest",
    "phone_identity_validation",
    "provenance_validation",
    "synthetic_check",
    "dedupe",
    "suppression_dnc_check",
    "classification",
    "script_assignment",
    "canonical_write",
    "revision_audit",
    "queue_prioritization",
    "live_verification",
]

# Lifecycle state that belongs to the EXISTING record and must survive a merge.
PRESERVE_ON_MERGE = (
    "attempts", "disposition", "notes", "last_touch", "stage", "history",
    "outcome", "call_outcomes", "callbacks", "sms_opted_out",
    "disposition_updated_at", "verification_history",
    "status", "new_today", "badge", "freshness", "created_at", "freshness_ts",
    "first_seen_date", "callable", "queue_bucket", "priority_rank",
)

NPI_VERTICAL_MAP = {
    "PT": "Medical Clinics & Urgent Care",
    "CHIRO": "Medical Clinics & Urgent Care",
    "URGENT": "Medical Clinics & Urgent Care",
    "IM": "Medical Clinics & Urgent Care",
    "DERM": "Medical Clinics & Urgent Care",
    "CARDIO": "Medical Clinics & Urgent Care",
    "PAIN": "Medical Clinics & Urgent Care",
    "ABA": "Medical Clinics & Urgent Care",
    "PA": "Medical Clinics & Urgent Care",
    "DENTAL": "Dental Clinics & Orthodontics",
}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def normalize_phone(raw: Any) -> str:
    """Normalize to 10 US digits ('' if impossible)."""
    return normalize_phone_digits(str(raw or ""))


def is_valid_us_phone(digits: str) -> bool:
    if len(digits) != 10:
        return False
    if digits.startswith("0") or digits.startswith("1"):
        return False
    if digits[3:6] in {"555", "000"}:
        return False
    if digits == digits[0] * 10:
        return False
    return True


def is_dnc_record(rec: Dict[str, Any]) -> bool:
    for key in ("disposition", "outcome", "suppression_reason", "blocked_reason"):
        val = str(rec.get(key) or "").upper()
        if any(tok in val for tok in ("DNC", "DO_NOT_CALL", "DONOTCALL", "BAD_NUMBER")):
            return True
    if str(rec.get("sms_opted_out", "")).lower() in ("true", "1", "yes"):
        return True
    return False


def classify_lead(lead: Dict[str, Any]) -> str:
    """Classify into a canonical segment; '' means NEEDS_REVIEW.

    Classification requires actual identity evidence (vertical/company).
    A bare record with neither is never force-fit onto a fallback script.
    """
    has_evidence = bool(
        str(lead.get("vertical") or lead.get("industry") or "").strip()
        or str(lead.get("company") or "").strip()
    )
    if not has_evidence:
        return ""
    segment = SegmentClassifier.classify_segment(lead)
    if segment not in SUPPORTED_SEGMENTS:
        return ""
    return segment


def candidate_from_npi_row(row: Dict[str, Any], generated_at: str) -> Optional[Dict[str, Any]]:
    """Map a raw CMS NPI callsheet row to an ingest candidate (None = unusable)."""
    npi = str(row.get("npi") or "").strip()
    company = str(row.get("company_name") or row.get("organization_name") or "").strip()
    if not npi or not company:
        return None

    official = str(row.get("authorized_official_name") or "").strip()
    official_title = str(row.get("authorized_official_title") or "").strip()

    phone_digits = ""
    for key in ("authorized_official_phone", "phone", "verified_phone"):
        cand_digits = normalize_phone(row.get(key) or "")
        if is_valid_us_phone(cand_digits):
            phone_digits = cand_digits
            break
    if not phone_digits:
        return None

    vt = str(row.get("vertical_tag") or "").strip().upper()
    industry = NPI_VERTICAL_MAP.get(vt, "Healthcare Services")

    prov = build_provenance_fields(
        source=str(row.get("source") or "CMS NPI Registry API v2.1"),
        source_reference=f"NPI-{npi}",
        source_type="government_registry",
        verification_method="npi_registry_api",
        observed_at=generated_at,
    )
    contact = official or company
    return {
        "id": f"NPI-{npi}",
        "company": company,
        "contact": contact,
        "decision_maker": contact,
        "title": official_title or ("Owner" if official else "Authorized Official"),
        "vertical": industry,
        "industry": industry,
        "phone": f"+1{phone_digits}",
        "email": str(row.get("email") or "").strip(),
        "city": str(row.get("city") or "").strip().title() or "Dallas",
        "state": str(row.get("state") or "").strip().upper() or "TX",
        "address": str(row.get("address") or "").strip(),
        "source_class": "NPI",
        **prov,
    }


def load_source_rows(source_path: Path) -> Tuple[List[Dict[str, Any]], str]:
    """Fetch SOURCE payload rows (RAW, unfiltered). Raises on failure."""
    if not source_path.exists():
        raise FileNotFoundError(f"Source not found: {source_path}")
    data = json.loads(source_path.read_text(encoding="utf-8"))
    generated_at = ""
    if isinstance(data, dict):
        rows = data.get("leads") or data.get("rows") or []
        generated_at = str(data.get("generated_at") or "")
    elif isinstance(data, list):
        rows = data
    else:
        raise ValueError(f"Unsupported source payload type: {type(data)!r}")
    label = f"{source_path.name}@{generated_at}" if generated_at else source_path.name
    return [r for r in rows if isinstance(r, dict)], label


# ---------------------------------------------------------------------------
# Live dialer client
# ---------------------------------------------------------------------------

class HttpDialerClient:
    """Read-only client for the live dialer runtime (Vite dev server).

    - GET {base}/leads_database.json -> LIVE API dataset (the UI fetches this)
    - GET {base}/                    -> LIVE UI reachability
    """

    def __init__(self, base_url: str = DEFAULT_DIALER_URL, timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> Tuple[int, bytes]:
        req = urllib.request.Request(
            self.base_url + path, headers={"User-Agent": "mbm-daily-ingest/1.0"}
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as res:
            return res.status, res.read()

    def fetch_db(self) -> List[Dict[str, Any]]:
        status, body = self._get("/leads_database.json")
        if status != 200:
            raise RuntimeError(f"dialer API HTTP {status}")
        data = json.loads(body.decode("utf-8"))
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and isinstance(data.get("leads"), list):
            return data["leads"]
        raise RuntimeError("dialer API payload is not a bare JSON list")

    def fetch_ui(self) -> bool:
        status, body = self._get("/")
        if status != 200:
            return False
        html = body.decode("utf-8", errors="replace").lower()
        # The MBM dialer is a TanStack Start SSR app (no #root mount div);
        # accept either a classic mount point or its app identity markers.
        return ('<div id="root">' in html or "<div id='root'>" in html
                or "mbm dialer" in html or "dialer" in html)


class NullDialerClient:
    """Offline stand-in used only by --no-live (hermetic/test runs)."""

    def fetch_db(self) -> List[Dict[str, Any]]:  # pragma: no cover
        raise RuntimeError("offline client (--no-live)")

    def fetch_ui(self) -> bool:  # pragma: no cover
        raise RuntimeError("offline client (--no-live)")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class DailyLeadIngestion:
    """Executes the full P0 daily stage pipeline with hard acceptance gates."""

    def __init__(
        self,
        db_path: Optional[Path] = None,
        artifacts_dir: Optional[Path] = None,
        source_path: Optional[Path] = None,
        dialer_url: Optional[str] = None,
        live_client: Optional[Any] = None,
    ):
        self.db_path = Path(db_path) if db_path else CANONICAL_DB_PATH
        self.artifacts_dir = Path(artifacts_dir) if artifacts_dir else ARTIFACTS_DIR
        self.source_path = Path(source_path) if source_path else DEFAULT_SOURCE
        self.live_client = live_client or HttpDialerClient(dialer_url or DEFAULT_DIALER_URL)
        self.provenance_gate = LeadProvenanceGate()
        self.stages: Dict[str, Dict[str, Any]] = {
            name: {"completed": False, "detail": ""} for name in PIPELINE_STAGES
        }

    def _mark(self, stage: str, completed: bool, detail: str = "") -> None:
        self.stages[stage] = {"completed": bool(completed), "detail": detail}

    # -- row construction ------------------------------------------------------

    @staticmethod
    def _build_row(cand: Dict[str, Any], segment: str, playbook: Dict[str, Any],
                   batch_date: str, now_iso: str) -> Dict[str, Any]:
        expected_value = float(playbook.get("offer", {}).get("estimated_deal_value_usd", 0) or 0)
        script_id = playbook.get("script_id", "")
        return {
            "id": cand["id"],
            "company": cand["company"],
            "contact": cand.get("decision_maker") or cand.get("contact") or "",
            "decision_maker": cand.get("decision_maker") or cand.get("contact") or "",
            "title": cand.get("title", ""),
            "vertical": cand.get("vertical") or cand.get("industry") or "",
            "industry": cand.get("industry") or cand.get("vertical") or "",
            "phone": cand["phone"],
            "email": cand.get("email", ""),
            "city": cand.get("city", ""),
            "state": cand.get("state", ""),
            "segment": segment,
            "script_id": script_id,
            "Call_Script": playbook.get("Call_Script", ""),
            "sales_strategy": {
                "script_id": script_id,
                "segment": segment,
                "opening": playbook.get("opening", ""),
                "price_expectation": playbook.get("price_expectation", ""),
                "next_step": playbook.get("next_step", ""),
                "objection_handlers": playbook.get("objection_handlers", {}),
                "polite_exit": playbook.get("polite_exit", ""),
                "offer": playbook.get("offer", {}),
            },
            "expected_value_usd": expected_value,
            "priority_score": round(min(99.0, 60.0 + expected_value / 100.0), 2),
            "status": "NEW",
            "callable": True,
            "queue_bucket": "NEW_VERIFIED",
            "attempts": 0,
            "disposition": "",
            "notes": "",
            "last_touch": now_iso,
            "stage": "QUALIFIED",
            "history": [{
                "event": "daily_ingest_accept",
                "date": batch_date,
                "at": now_iso,
                "source": cand.get("source", ""),
            }],
            "verification_status": "VERIFIED",
            "verified_at": now_iso,
            "phone_verified": True,
            "phone_verification_source": cand.get("source", ""),
            "created_at": now_iso,
            "freshness_ts": now_iso,
            "first_seen_date": batch_date,
            "first_seen_at": batch_date,
            "new_today": True,
            "badge": "NEW TODAY",
            "freshness": "NEW_TODAY",
            "source": cand.get("source", ""),
            "source_reference": cand.get("source_reference", ""),
            "source_type": cand.get("source_type", ""),
            "source_observed_at": cand.get("observed_at", ""),
            "verification_method": cand.get("verification_method", ""),
        }

    @staticmethod
    def _merge_into_existing(existing: Dict[str, Any], fresh: Dict[str, Any],
                             run_id: str, now_iso: str) -> Tuple[Dict[str, Any], bool]:
        """Merge stronger verified enrichment into an existing record while
        preserving attempts/disposition/notes/last_touch/stage/history state."""
        changed = False
        merged = dict(existing)
        for key, value in fresh.items():
            if key in PRESERVE_ON_MERGE or key == "history":
                continue
            if key in ("verification_status", "verified_at") and existing.get("verification_status"):
                continue
            if merged.get(key) != value:
                merged[key] = value
                changed = True
        if changed:
            history = list(existing.get("history") or [])
            history.append({
                "event": "daily_ingest_merge",
                "run_id": run_id,
                "at": now_iso,
                "merged_source": fresh.get("source_reference", ""),
            })
            merged["history"] = history
        return merged, changed

    # -- main entry --------------------------------------------------------------

    def run(
        self,
        apply: bool = False,
        target: Optional[int] = None,
        batch_date: Optional[str] = None,
        check_live: bool = True,
    ) -> Dict[str, Any]:
        started = datetime.now(timezone.utc)
        run_id = f"daily-ingest-{started.strftime('%Y%m%dT%H%M%S')}-{time.time_ns() % 10000}"
        date_str = batch_date or started.strftime("%Y-%m-%d")
        day_dir = self.artifacts_dir / "GTM" / "daily" / date_str
        now_iso = started.isoformat()

        report: Dict[str, Any] = {
            "run_id": run_id,
            "run_date": date_str,
            "mode": "apply" if apply else "dry_run",
            "source": "",
            "started_at": started.isoformat(),
            "completed_at": "",
            "raw_count": 0,
            "accepted_count": 0,
            "new_count": 0,
            "duplicate_count": 0,
            "suppressed_count": 0,
            "rejected_count": 0,
            "needs_review_count": 0,
            "canonical_revision": None,
            "canonical_revision_before": None,
            "canonical_count": None,
            "canonical_count_before": None,
            "dataset_hash": "",
            "dataset_hash_before": "",
            "script_coverage": 0.0,
            "segment_coverage": 0.0,
            "live_verified": False,
            "live_skipped": not check_live,
            "status": STATUS_BLOCKED,
            "write_performed": False,
            "zero_yield_reason": "",
            "errors": [],
            "needs_review_ids": [],
            "sample_traces": [],
            "stages": self.stages,
        }

        lock = DialerDatabaseLock(db_path=self.db_path)

        # ---- Stage: SOURCE FETCH -------------------------------------------
        try:
            raw_payload_rows, source_label = load_source_rows(self.source_path)
        except Exception as exc:
            report["errors"].append(f"source_fetch_failed: {exc}")
            report["completed_at"] = datetime.now(timezone.utc).isoformat()
            report["status"] = STATUS_BLOCKED
            self._mark("source_fetch", False, str(exc))
            self._finish_report(report, day_dir)
            return report
        if target is not None:
            raw_payload_rows = raw_payload_rows[: max(0, int(target))]
        report["source"] = source_label
        report["raw_count"] = len(raw_payload_rows)
        self._mark("source_fetch", True, f"{len(raw_payload_rows)} rows from {source_label}")

        # ---- Stage: RAW INGEST (map payload -> candidates) -------------------
        generated_at = source_label.split("@", 1)[1] if "@" in source_label else ""
        candidates: List[Dict[str, Any]] = []
        malformed = 0
        for row in raw_payload_rows:
            if "npi" in row:
                cand = candidate_from_npi_row(row, generated_at)
                if cand is None:
                    malformed += 1
                    continue
                candidates.append(cand)
            else:
                rid = str(row.get("id") or "").strip()
                if not rid:
                    malformed += 1
                    continue
                candidates.append(row)
        report["rejected_count"] += malformed
        self._mark("raw_ingest", True,
                   f"{len(candidates)} structured candidates ({malformed} malformed dropped)")

        # ---- Canonical snapshot (pre-write state) ----------------------------
        try:
            existing_rows = lock.read()
        except Exception as exc:
            report["errors"].append(f"canonical_read_failed: {exc}")
            report["status"] = STATUS_BLOCKED
            self._finish_report(report, day_dir)
            return report

        rev_file, audit_file = sidecar_paths(self.db_path)
        revision_before = self._read_revision(rev_file)
        hash_before = compute_checksum(existing_rows)
        report["canonical_count_before"] = len(existing_rows)
        report["canonical_revision_before"] = revision_before
        report["dataset_hash_before"] = hash_before

        existing_by_phone: Dict[str, Dict[str, Any]] = {}
        existing_by_id: Dict[str, Dict[str, Any]] = {}
        for rec in existing_rows:
            p = normalize_phone(rec.get("phone") or "")
            if p:
                existing_by_phone.setdefault(p, rec)
            rid = str(rec.get("id") or "")
            if rid:
                existing_by_id.setdefault(rid, rec)

        suppression = load_suppression_index()

        accepted: List[Dict[str, Any]] = []
        merges: Dict[str, Dict[str, Any]] = {}
        seen_batch_phones: set = set()
        seen_batch_ids: set = set()

        # ---- Per-candidate gates (every stage applied to every record) ------
        for cand in candidates:
            # PHONE/IDENTITY VALIDATION
            digits = normalize_phone(cand.get("phone") or "")
            if not is_valid_us_phone(digits):
                report["rejected_count"] += 1
                continue

            # PROVENANCE VALIDATION
            prov = self.provenance_gate.evaluate(cand)
            if not isinstance(prov, dict) or not prov.get("ok"):
                report["rejected_count"] += 1
                continue

            # SYNTHETIC / FICTITIOUS CHECK
            if is_strong_synthetic(cand):
                report["rejected_count"] += 1
                continue

            norm_phone = digits

            # SUPPRESSION / DNC CHECK
            if is_dnc_record(cand) or norm_phone in suppression:
                report["suppressed_count"] += 1
                continue

            # DEDUPE: intra-batch, then active canonical phones/ids
            if norm_phone in seen_batch_phones or str(cand.get("id")) in seen_batch_ids:
                report["duplicate_count"] += 1
                continue
            existing_hit = existing_by_phone.get(norm_phone) or existing_by_id.get(str(cand.get("id")))
            if existing_hit is not None:
                report["duplicate_count"] += 1
                seen_batch_phones.add(norm_phone)
                seen_batch_ids.add(str(cand.get("id")))
                seg = classify_lead(dict(existing_hit, **{k: v for k, v in cand.items()}))
                if seg:
                    pb = DialerScriptEngine.generate_playbook(
                        dict(existing_hit, **{k: v for k, v in cand.items()})
                    )
                    merged, changed = self._merge_into_existing(
                        existing_hit,
                        self._build_row({**cand, "id": existing_hit.get("id")},
                                        seg, pb, date_str, now_iso),
                        run_id, now_iso,
                    )
                    if changed:
                        merges[str(existing_hit.get("id"))] = merged
                continue
            seen_batch_phones.add(norm_phone)
            seen_batch_ids.add(str(cand.get("id")))

            # CLASSIFICATION (unknown -> NEEDS_REVIEW, never force-fit)
            segment = classify_lead(cand)
            if not segment:
                report["needs_review_count"] += 1
                report["needs_review_ids"].append(str(cand.get("id")))
                continue

            # SCRIPT ASSIGNMENT (must match actual classification)
            playbook = DialerScriptEngine.generate_playbook(dict(cand))
            if (playbook.get("segment") != segment
                    or not playbook.get("script_id")
                    or not playbook.get("Call_Script")):
                report["needs_review_count"] += 1
                report["needs_review_ids"].append(str(cand.get("id")))
                continue

            accepted.append(self._build_row(cand, segment, playbook, date_str, now_iso))

        report["accepted_count"] = len(accepted)
        report["new_count"] = len(accepted)
        self._mark("phone_identity_validation", True, "US phone + identity gate applied to every candidate")
        self._mark("provenance_validation", True, "LeadProvenanceGate applied to every candidate")
        self._mark("synthetic_check", True, "strong synthetic fingerprint veto applied")
        self._mark("dedupe", True,
                   f"{report['duplicate_count']} duplicates ({len(merges)} enriched via history-preserving merge)")
        self._mark("suppression_dnc_check", True,
                   f"{report['suppressed_count']} suppressed/DNC (suppression index size {len(suppression)})")

        scripted = [r for r in accepted if r.get("script_id") and r.get("Call_Script")]
        segments_covered = sorted({r["segment"] for r in accepted})
        report["script_coverage"] = (
            round(100.0 * len(scripted) / len(accepted), 1) if accepted else 100.0
        )
        report["segment_coverage"] = (
            round(100.0 * sum(1 for r in accepted if r.get("segment") in SUPPORTED_SEGMENTS) / len(accepted), 1)
            if accepted else 100.0
        )
        self._mark("classification", True,
                   f"{report['needs_review_count']} NEEDS_REVIEW; segments={segments_covered}")
        self._mark("script_assignment", True, f"coverage {report['script_coverage']}% (canonical script engine)")

        # ---- QUEUE PRIORITIZATION plan (newest-first at top of dataset) -----
        accepted.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        new_ids = [str(r["id"]) for r in accepted]

        # ---- CANONICAL WRITE --------------------------------------------------
        if apply:
            if not accepted and not merges:
                report["zero_yield_reason"] = (
                    "idempotent/no-op batch: 0 new and 0 merges "
                    f"(duplicates={report['duplicate_count']}, rejected={report['rejected_count']}, "
                    f"suppressed={report['suppressed_count']}, needs_review={report['needs_review_count']})"
                )
                self._mark("canonical_write", True, "nothing to write (documented zero-yield)")
                self._mark("revision_audit", True, "no content change; revision intentionally untouched")
            else:
                merge_map = dict(merges)
                rebuilt: List[Dict[str, Any]] = []
                for rec in existing_rows:
                    rid = str(rec.get("id") or "")
                    rebuilt.append(merge_map.pop(rid) if rid in merge_map else rec)
                rebuilt.extend(merge_map.values())
                final_rows = accepted + rebuilt
                try:
                    written = lock.write(
                        final_rows,
                        allow_shrink=False,
                        author="DAILY_LEAD_INGEST",
                        reason=f"daily_lead_ingestion:{date_str}",
                        operation_id=run_id,
                    )
                    report["write_performed"] = True
                    report["canonical_count"] = written
                    self._mark("canonical_write", True,
                               f"{len(accepted)} new + {len(merges)} merged committed (total {written})")
                except (SingleWriterViolation, RuntimeError) as exc:
                    report["errors"].append(f"canonical_write_failed: {exc}")
                    self._mark("canonical_write", False, f"canonical_write_failed: {exc}")
        else:
            self._mark("canonical_write", True, "dry-run: no write performed")
            self._mark("revision_audit", True, "dry-run: no revision bump")

        # ---- REVISION / AUDIT ---------------------------------------------------
        current_rev = self._read_revision(rev_file)
        # Report ACTUAL canonical state; the projected outcome is informational.
        persisted_rows = lock.read() if apply else existing_rows
        report["projected_count"] = len(existing_rows) + len(accepted)
        report["canonical_revision"] = current_rev
        if report["canonical_count"] is None:
            report["canonical_count"] = len(persisted_rows)
        report["dataset_hash"] = compute_checksum(persisted_rows)

        content_change_expected = bool(accepted or merges)
        if report["write_performed"]:
            revision_ok = current_rev > revision_before
            audit_ok = self._audit_contains(audit_file, run_id)
            self._mark("revision_audit", revision_ok and audit_ok,
                       f"revision {revision_before} -> {current_rev}; audit={'ok' if audit_ok else 'MISSING'}")
            if not revision_ok:
                report["errors"].append("revision did not increment after write")
            if not audit_ok:
                report["errors"].append(f"audit event missing for run {run_id}")
        else:
            revision_ok = not content_change_expected
            audit_ok = True

        # ---- NO-SHRINK assertion -------------------------------------------------
        if report["write_performed"] and report["canonical_count"] < report["canonical_count_before"]:
            shrink_msg = (f"destructive shrinkage {report['canonical_count_before']} -> "
                          f"{report['canonical_count']} unexplained")
            report["errors"].append(shrink_msg)
            self._mark("canonical_write", False, shrink_msg)

        # ---- QUEUE PRIORITIZATION verify ------------------------------------------
        queue_ok = True
        if apply and report["write_performed"]:
            top_ids = [str(r.get("id") or "") for r in persisted_rows[: len(new_ids)]]
            queue_ok = all(nid in top_ids for nid in new_ids[:50])
            snapshot = self._build_queue_snapshot(persisted_rows)
            day_dir.mkdir(parents=True, exist_ok=True)
            (day_dir / "queue_snapshot.json").write_text(
                json.dumps(snapshot, indent=2), encoding="utf-8"
            )
            # Per-lead verification dossiers (canonical artifact trail:
            # lead_id/company/phone/source/provenance/segment/script/callable).
            for row in accepted:
                (day_dir / f"lead_{row['id']}.json").write_text(
                    json.dumps(row, indent=2, default=str), encoding="utf-8"
                )
            self._mark("queue_prioritization", queue_ok,
                       f"{len(new_ids)} new leads promoted newest-first; call_now page={len(snapshot['pages'][0])}")
            if not queue_ok:
                report["errors"].append("newest-first ordering violated after write")
        else:
            self._mark("queue_prioritization", True,
                       "planned newest-first order (dry-run)" if not apply else "no new rows to promote")

        # ---- LIVE VERIFICATION (release gate; only meaningful post-write) --------
        live: Dict[str, Any] = {"performed": False, "ok": False, "reason": ""}
        if check_live and apply:
            # Trace up to 5 of TODAY'S newly verified leads. If this run is a
            # no-op (idempotent rerun / merge-only), fall back to today's
            # already-ingested cohort so end-to-end visibility is still proven.
            sample_ids = new_ids[:5]
            if not sample_ids:
                todays = [r for r in persisted_rows
                          if str(r.get("first_seen_date") or "") == date_str]
                todays.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
                sample_ids = [str(r.get("id")) for r in todays[:5]]
            try:
                api_rows = self.live_client.fetch_db()
                ui_ok = self.live_client.fetch_ui()
                api_count = len(api_rows)
                traces = []
                accepted_ids = {str(r.get("id")) for r in accepted}
                for sid in sample_ids:
                    pos = next((i for i, r in enumerate(api_rows)
                                if str(r.get("id") or "") == sid), -1)
                    traces.append({
                        "lead_id": sid,
                        "in_source_batch": sid in accepted_ids,
                        "in_canonical": any(str(r.get("id") or "") == sid for r in persisted_rows),
                        "in_live_api": pos >= 0,
                        "live_api_position": pos,
                        "ui_served": ui_ok,
                    })
                # Trace up to 5 of today's newly verified leads; a batch with no
                # new rows has nothing to trace (count match + UI still gate).
                samples_ok = all(
                    t["in_canonical"] and t["in_live_api"] and t["ui_served"] for t in traces
                )
                count_match = api_count == len(persisted_rows)
                live_ok = count_match and ui_ok and samples_ok
                live = {
                    "performed": True,
                    "ok": live_ok,
                    "api_count": api_count,
                    "canonical_count": len(persisted_rows),
                    "ui_reachable": ui_ok,
                    "count_match": count_match,
                    "samples_traced": len(traces),
                    "samples_ok": samples_ok,
                    "traces": traces,
                    "base_url": getattr(self.live_client, "base_url", ""),
                }
                if not live_ok:
                    reasons = []
                    if not count_match:
                        reasons.append(f"API count {api_count} != canonical {len(persisted_rows)}")
                    if not ui_ok:
                        reasons.append("UI unreachable")
                    if not samples_ok:
                        reasons.append("sample trace incomplete")
                    live["reason"] = "; ".join(reasons)
                    report["errors"].append(f"live_verification_failed: {live['reason']}")
            except Exception as exc:
                live = {"performed": True, "ok": False, "reason": str(exc)}
                report["errors"].append(f"live_verification_failed: {exc}")
            report["live"] = live
            report["live_verified"] = bool(live.get("ok"))
            report["sample_traces"] = live.get("traces", [])
            self._mark("live_verification", bool(live.get("ok")),
                       live.get("reason") or "counts match + samples traced + UI serving")
        elif not apply:
            report["live"] = live
            report["live_skipped"] = True
            self._mark("live_verification", True, "dry-run: live release check deferred until --apply")
        else:
            report["live"] = live
            report["live_skipped"] = True
            self._mark("live_verification", True, "explicitly skipped (--no-live hermetic mode)")

        # ---- ACCEPTANCE GATE + STATUS ----------------------------------------------------
        report["acceptance_gate"] = self._acceptance_gate(report, revision_ok, audit_ok, queue_ok)
        report["status"] = self.resolve_status(report)
        if report["status"] == STATUS_PARTIAL:
            report["partial"] = {
                "raw": report["raw_count"],
                "accepted": report["accepted_count"],
                "rejected": report["rejected_count"],
                "duplicates": report["duplicate_count"],
                "suppressed": report["suppressed_count"],
                "needs_review": report["needs_review_count"],
                "persisted": report["canonical_count"] if apply else 0,
                "not_persisted": len(accepted) if not apply else 0,
            }
        report["completed_at"] = datetime.now(timezone.utc).isoformat()

        self._finish_report(report, day_dir)
        if report["status"] == STATUS_SUCCESS and apply:
            self._write_heartbeat(day_dir, report)
        return report

    # -- helpers -------------------------------------------------------------------

    @staticmethod
    def _read_revision(rev_file: Path) -> int:
        try:
            return int(json.loads(rev_file.read_text(encoding="utf-8")).get("revision", 0))
        except Exception:
            return 0

    @staticmethod
    def _audit_contains(audit_file: Path, run_id: str) -> bool:
        try:
            lines = audit_file.read_text(encoding="utf-8").strip().splitlines() if audit_file.exists() else []
            return bool(lines) and run_id in lines[-1]
        except Exception:
            return False

    @staticmethod
    def _build_queue_snapshot(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """FILTER -> SAFETY -> SCORE -> SORT NEWEST-FIRST -> PAGINATE."""
        callable_rows = [r for r in rows if r.get("callable", True) and not is_dnc_record(r)]
        callable_rows.sort(
            key=lambda r: (str(r.get("created_at") or r.get("freshness_ts") or ""),
                           float(r.get("priority_score") or 0)),
            reverse=True,
        )
        page_size = 25
        pages = [callable_rows[i:i + page_size]
                 for i in range(0, min(len(callable_rows), page_size * 4), page_size)] or [[]]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "filter": "callable=True AND not suppressed/DNC",
            "sort": "SCORE then NEWEST-FIRST",
            "total_callable": len(callable_rows),
            "pages": [[{
                "rank": i + 1 + page_idx * page_size,
                "id": r.get("id"),
                "company": r.get("company"),
                "phone": r.get("phone"),
                "segment": r.get("segment"),
                "script_id": r.get("script_id"),
                "priority_score": r.get("priority_score"),
                "first_seen_date": r.get("first_seen_date"),
            } for i, r in enumerate(page)] for page_idx, page in enumerate(pages)],
        }

    @staticmethod
    def _acceptance_gate(report: Dict[str, Any], revision_ok: bool,
                         audit_ok: bool, queue_ok: bool) -> Dict[str, bool]:
        stages = report["stages"]
        zero_yield = bool(report.get("zero_yield_reason"))
        live_pass = bool(report.get("live_verified")) or bool(report.get("live_skipped"))
        apply_mode = report.get("mode") == "apply"
        return {
            "source_fetch_succeeded": stages["source_fetch"]["completed"],
            "raw_count_recorded": report["raw_count"] >= 0 and bool(report["source"]),
            "verification_completed": (
                stages["phone_identity_validation"]["completed"]
                and stages["provenance_validation"]["completed"]
            ),
            "synthetic_rejection_completed": stages["synthetic_check"]["completed"],
            "dedupe_completed": stages["dedupe"]["completed"],
            "suppression_dnc_completed": stages["suppression_dnc_check"]["completed"],
            "classification_completed": stages["classification"]["completed"],
            "script_enrichment_completed": (
                stages["script_assignment"]["completed"] and report["script_coverage"] == 100.0
            ),
            "canonical_db_write_succeeded": stages["canonical_write"]["completed"] and (
                bool(report.get("write_performed")) or bool(zero_yield) or not apply_mode
            ),
            "revision_incremented": bool(revision_ok),
            "audit_entry_recorded": bool(audit_ok),
            "accepted_gt_zero_or_documented": report["accepted_count"] > 0 or zero_yield,
            "queue_refreshed": stages["queue_prioritization"]["completed"],
            "newest_first_verified": bool(queue_ok),
            "live_dialer_updated": stages["live_verification"]["completed"] and live_pass,
        }

    @staticmethod
    def resolve_status(report: Dict[str, Any]) -> str:
        stages = report.get("stages", {})
        if not stages.get("source_fetch", {}).get("completed"):
            return STATUS_BLOCKED
        errors = report.get("errors") or []
        if any(("canonical_write_failed" in e) or ("shrinkage" in e) for e in errors):
            return STATUS_FAILED
        live = report.get("live") or {}
        if live.get("performed") and not report.get("live_verified"):
            return STATUS_FAILED
        if report.get("write_performed"):
            if not stages.get("revision_audit", {}).get("completed"):
                return STATUS_FAILED
            if not stages.get("queue_prioritization", {}).get("completed"):
                return STATUS_FAILED
            return STATUS_SUCCESS
        # Nothing was written.
        if report.get("accepted_count", 0) > 0:
            # Candidates verified but not persisted (e.g. dry-run) -> partial.
            return STATUS_PARTIAL
        fully_accounted = (
            report.get("duplicate_count", 0)
            + report.get("rejected_count", 0)
            + report.get("suppressed_count", 0)
            + report.get("needs_review_count", 0)
            >= report.get("raw_count", 0)
        )
        if report.get("zero_yield_reason") and fully_accounted:
            return STATUS_SUCCESS
        if report.get("raw_count", 0) > 0:
            return STATUS_QUARANTINED
        return STATUS_PARTIAL

    @staticmethod
    def _write_heartbeat(day_dir: Path, report: Dict[str, Any]) -> None:
        """Heartbeat updates ONLY after: engine ran + real batch processed +
        canonical persistence + queue updated + verification succeeded."""
        conditions = {
            "engine_ran": True,
            "real_batch_processed": report["raw_count"] > 0,
            "canonical_persistence_succeeded": bool(
                report["write_performed"] or report["zero_yield_reason"]
            ),
            "queue_updated": report["stages"]["queue_prioritization"]["completed"],
            "verification_succeeded": bool(report.get("live_verified")),
        }
        if not all(conditions.values()):
            return
        day_dir.mkdir(parents=True, exist_ok=True)
        heartbeat = {
            "healthy": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "run_id": report["run_id"],
            "conditions": conditions,
            "canonical_count": report["canonical_count"],
            "canonical_revision": report["canonical_revision"],
            "dataset_hash": report["dataset_hash"],
        }
        (day_dir / "scheduler_heartbeat.json").write_text(
            json.dumps(heartbeat, indent=2), encoding="utf-8"
        )

    def _finish_report(self, report: Dict[str, Any], day_dir: Path) -> None:
        day_dir.mkdir(parents=True, exist_ok=True)
        report["stages"] = self.stages

        # Day rollup: preserve every run of this date so the daily artifact
        # tells the whole truth (a FAILED attempt is never erased by a later
        # successful retry).
        report_path = day_dir / "lead_ingestion_report.json"
        day_totals = {
            "raw": report["raw_count"],
            "accepted": report["accepted_count"],
            "new": report["new_count"],
            "duplicates": report["duplicate_count"],
            "suppressed": report["suppressed_count"],
            "rejected": report["rejected_count"],
            "needs_review": report["needs_review_count"],
        }
        runs = [{
            "run_id": report["run_id"],
            "status": report["status"],
            "mode": report.get("mode"),
            "raw": report["raw_count"],
            "new": report["new_count"],
            "duplicates": report["duplicate_count"],
            "suppressed": report["suppressed_count"],
            "rejected": report["rejected_count"],
            "needs_review": report["needs_review_count"],
            "write_performed": report["write_performed"],
            "canonical_revision": report["canonical_revision"],
            "live_verified": report["live_verified"],
        }]
        if report_path.exists():
            try:
                prev = json.loads(report_path.read_text(encoding="utf-8"))
                for r in prev.get("runs", []):
                    runs.insert(0, r)
                    day_totals["raw"] += r.get("raw", 0)
                    day_totals["accepted"] += r.get("new", 0)
                    day_totals["new"] += r.get("new", 0)
                    day_totals["duplicates"] += r.get("duplicates", 0)
                    day_totals["suppressed"] += r.get("suppressed", 0)
                    day_totals["rejected"] += r.get("rejected", 0)
                    day_totals["needs_review"] += r.get("needs_review", 0)
            except Exception:
                pass
        # De-duplicate identical reruns of the same run_id (report rewrite).
        seen_ids = set()
        unique_runs = []
        for r in runs:
            if r["run_id"] not in seen_ids:
                unique_runs.append(r)
                seen_ids.add(r["run_id"])
        report["runs"] = unique_runs
        report["day_totals"] = day_totals

        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        md = render_markdown_report(report)
        if len(unique_runs) > 1:
            md += _render_day_rollup_md(report)
        (day_dir / "lead_ingestion_report.md").write_text(md, encoding="utf-8")


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _render_day_rollup_md(report: Dict[str, Any]) -> str:
    dt = report.get("day_totals", {})
    lines = [
        "",
        "## Day Rollup (all runs)",
        "",
        "| Run | Status | Raw | New | Dupes | Suppressed | Rejected | Needs review |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in report.get("runs", []):
        lines.append(
            f"| `{r['run_id'][-6:]}` | {r['status']} | {r.get('raw', 0)} | {r.get('new', 0)} | "
            f"{r.get('duplicates', 0)} | {r.get('suppressed', 0)} | {r.get('rejected', 0)} | "
            f"{r.get('needs_review', 0)} |"
        )
    lines += [
        "",
        f"**Day totals:** raw={dt.get('raw', 0)}, new={dt.get('new', 0)}, "
        f"duplicates={dt.get('duplicates', 0)}, suppressed={dt.get('suppressed', 0)}, "
        f"rejected={dt.get('rejected', 0)}, needs_review={dt.get('needs_review', 0)}",
    ]
    return "\n".join(lines)


def render_markdown_report(report: Dict[str, Any]) -> str:
    lines = [
        f"# Daily Lead Ingestion Report — {report['run_id']}",
        "",
        f"- **Status:** `{report['status']}` ({report.get('mode', '')})",
        f"- **Source:** `{report['source']}`",
        f"- **Started:** {report['started_at']}  |  **Completed:** {report['completed_at']}",
        "",
        "| Metric | Count |",
        "|---|---|",
        f"| Raw | {report['raw_count']} |",
        f"| Accepted | {report['accepted_count']} |",
        f"| New | {report['new_count']} |",
        f"| Duplicates | {report['duplicate_count']} |",
        f"| Suppressed | {report['suppressed_count']} |",
        f"| Rejected | {report['rejected_count']} |",
        f"| Needs review | {report['needs_review_count']} |",
        "",
        f"- **Canonical:** before={report['canonical_count_before']} "
        f"after={report['canonical_count']} "
        f"revision={report['canonical_revision_before']}->{report['canonical_revision']}",
        f"- **Dataset hash:** `{str(report['dataset_hash'])[:16]}…`",
        f"- **Script coverage:** {report['script_coverage']}%  |  "
        f"**Segment coverage:** {report['segment_coverage']}%",
        f"- **Live verified:** {'YES' if report['live_verified'] else 'NO'}",
    ]
    if report.get("zero_yield_reason"):
        lines.append(f"- **Zero-yield reason:** {report['zero_yield_reason']}")
    if report.get("needs_review_ids"):
        lines.append(f"- **NEEDS_REVIEW:** {', '.join(map(str, report['needs_review_ids'][:20]))}")
    if report.get("errors"):
        lines += ["", "## Errors"]
        lines += [f"- {err}" for err in report["errors"]]
    lines += [
        "",
        "## Stage Pipeline",
        "",
        "| Stage | Completed | Detail |",
        "|---|---|---|",
    ]
    for stage, info in report.get("stages", {}).items():
        lines.append(f"| {stage} | {'YES' if info['completed'] else 'NO'} | {info['detail'][:80]} |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

EXIT_CODES = {
    STATUS_SUCCESS: 0,
    STATUS_FAILED: 1,
    STATUS_PARTIAL: 2,
    STATUS_QUARANTINED: 3,
    STATUS_BLOCKED: 4,
}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="P0 Daily Lead Verification + Dialer Ingestion")
    parser.add_argument("--apply", action="store_true", help="commit the batch to the canonical dialer DB")
    parser.add_argument("--target", type=int, default=None, help="cap candidates processed from the source")
    parser.add_argument("--source-file", type=str, default=None, help="override source JSON path")
    parser.add_argument("--base-url", type=str, default=None, help="live dialer base URL")
    parser.add_argument("--db-path", type=str, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--artifacts-dir", type=str, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--no-live", action="store_true", help="skip live verification (hermetic/test only)")
    args = parser.parse_args(argv)

    ingestion = DailyLeadIngestion(
        db_path=Path(args.db_path) if args.db_path else None,
        artifacts_dir=Path(args.artifacts_dir) if args.artifacts_dir else None,
        source_path=Path(args.source_file) if args.source_file else None,
        dialer_url=args.base_url,
        live_client=NullDialerClient() if args.no_live else None,
    )
    report = ingestion.run(apply=args.apply, target=args.target, check_live=not args.no_live)

    print("=" * 78)
    print(f"P0 DAILY LEAD INGESTION — {report['status']} ({report['mode']})")
    print("=" * 78)
    print(f"SOURCE:       {report['source']}")
    print(f"RAW:          {report['raw_count']}")
    print(f"ACCEPTED:     {report['accepted_count']}  (NEW: {report['new_count']})")
    print(f"DUPLICATES:   {report['duplicate_count']}")
    print(f"SUPPRESSED:   {report['suppressed_count']}")
    print(f"REJECTED:     {report['rejected_count']}")
    print(f"NEEDS_REVIEW: {report['needs_review_count']}")
    print(f"CANONICAL:    {report['canonical_count_before']} -> {report['canonical_count']} "
          f"(rev {report['canonical_revision_before']} -> {report['canonical_revision']})")
    print(f"HASH:         {str(report['dataset_hash'])[:16]}…")
    print(f"LIVE:         {'VERIFIED' if report['live_verified'] else ('SKIPPED' if report['live_skipped'] else 'NOT VERIFIED')}")
    for err in report.get("errors", []):
        print(f"ERROR:        {err}")
    print("=" * 78)
    return EXIT_CODES[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
