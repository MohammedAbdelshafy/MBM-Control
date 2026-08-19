"""pipeline -- daily code-violation lead pipeline orchestrator.

Flow:  collect -> group by property -> enrich (owner+phone) -> dedupe
       (case ledger + live dialer match) -> score/tier -> dialer sync via
       patch_dialer_db -> GTM daily artifacts + founder report.

Safety contract:
  - Writes to the live dialer DB ONLY through dialer_gateway.patch_dialer_db
    (DialerSingleWriter single-writer lock; zero-shrink enforced).
  - Only TIER 1 / TIER 2 (callable phone) ever enter the dialer segment
    CODE_VIOLATION_DAILY. TIER 3 goes to artifacts only.
  - State + case ledger live under MBM/Artifacts/code_violation/. A dry run
    never writes state, ledger, dialer DB, or GTM artifacts.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..dialer_gateway import patch_dialer_db
from ..lead_provenance import build_provenance_fields
from .collector import (
    REGISTRY_PATH,
    active_sources,
    collect_source,
    enrich_violation,
    is_rejected_violation,
    load_source_registry,
    record_key,
    utcnow,
)
from .enrichment import (
    PhoneResult,
    county_for_city,
    enrich_phone,
    resolve_owner,
)
from .scoring import (
    ScoreResult,
    build_property_record,
    score_property,
)

DIALER_DB_PATH = Path("mbm-dialer/app/public/leads_database.json")
GTM_QUEUE_PATH = Path("MBM/Artifacts/GTM_TOP25_EXECUTION_QUEUE.json")
GTM_DAILY_ROOT = Path("MBM/Artifacts/GTM/daily")
CV_ARTIFACTS_ROOT = Path("MBM/Artifacts/code_violation")

QUEUE_BUCKET = "CODE_VIOLATION_DAILY"
VERTICAL = "Code Violation Sellers"
SALES_LANE = "PROPERTY_OWNER"
SOURCE_TYPE = "government_open_data"
VERIFICATION_METHOD = "municipal_open_data_api"

PHONE_RECORDS_MIN = 1
EMPTY = object()


def lead_id(address: str, city: str, state: str) -> str:
    key = f"{address}|{city}|{state}".upper()
    return "CV-" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]


def _today(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def load_live_db(path: Optional[Path] = None) -> list[dict]:
    p = path or DIALER_DB_PATH
    if not p.exists():
        return []
    data = _load_json(p)
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "leads" in data:
        return data["leads"]
    if isinstance(data, dict) and "records" in data:
        return data["records"]
    return []


def normalize_match_addr(addr: str) -> str:
    return re.sub(r"\s+", "", str(addr or "").upper()).rstrip(".").strip()


def find_existing(db_rows: list[dict], address: str, parcel: str) -> Optional[dict]:
    want_addr = normalize_match_addr(address)
    want_parcel = str(parcel or "").strip().upper()
    for row in db_rows:
        row_addr = normalize_match_addr(row.get("address") or "")
        if want_addr and row_addr and want_addr == row_addr:
            return row
        details = row.get("details") or {}
        det_addr = normalize_match_addr(details.get("address") or "")
        det_parcel = str(details.get("parcel_id") or "").strip().upper()
        if want_addr and det_addr and want_addr == det_addr:
            return row
        if want_parcel and det_parcel and want_parcel == det_parcel:
            return row
    return None


class CodeViolationDailyPipeline:
    def __init__(
        self,
        root_dir: Path,
        registry_path: Optional[Path] = None,
        artifacts_root: Optional[Path] = None,
        gtm_daily_root: Optional[Path] = None,
        gtm_queue_path: Optional[Path] = None,
        dialer_db_path: Optional[Path] = None,
        now: Optional[datetime] = None,
        fetch_json: Optional[Callable[..., Any]] = None,
        dcad_fn: Optional[Any] = None,
        verify_fn: Optional[Any] = None,
        skip_tracer: Optional[Any] = None,
        suppression: Optional[set] = None,
    ):
        self.root = Path(root_dir)
        self.registry_path = Path(registry_path) if registry_path else (self.root / REGISTRY_PATH)
        self.artifacts_root = Path(artifacts_root) if artifacts_root else (self.root / CV_ARTIFACTS_ROOT)
        self.gtm_daily_root = Path(gtm_daily_root) if gtm_daily_root else (self.root / GTM_DAILY_ROOT)
        self.gtm_queue_path = Path(gtm_queue_path) if gtm_queue_path else (self.root / GTM_QUEUE_PATH)
        self.dialer_db_path = Path(dialer_db_path) if dialer_db_path else (self.root / DIALER_DB_PATH)
        self.now = now or utcnow()
        self.fetch_json = fetch_json
        self.dcad_fn = dcad_fn
        self.verify_fn = verify_fn
        self.skip_tracer = skip_tracer
        self.suppression = suppression
        self.state_path = self.artifacts_root / "state.json"
        self.ledger_path = self.artifacts_root / "ledger.json"

    # ── state / ledger ─────────────────────────────────────────────────────
    def load_state(self) -> dict:
        state = _load_json(self.state_path) or {}
        return state.get("sources", {})

    def load_ledger(self) -> dict:
        ledger = _load_json(self.ledger_path) or {}
        return ledger.get("cases", {})

    def _persist_ledger(self, ledger: dict) -> None:
        _write_json(self.ledger_path, {"cases": ledger, "updated": iso(self.now)})

    def _persist_state(self, state: dict) -> None:
        _write_json(self.state_path, {
            "sources": state,
            "updated": iso(self.now),
            "last_run_id": getattr(self, "_run_id", ""),
        })

    # ── collect ────────────────────────────────────────────────────────────
    def collect(self, days_back: int, source_filter: Optional[str] = None,
                last_since: Optional[dict] = None) -> tuple[list[dict], dict]:
        registry = load_source_registry(self.registry_path)
        sources = active_sources(registry)
        raw: list[dict] = []
        manifest: dict[str, Any] = {}
        state = last_since or self.load_state()
        for name, cfg in sources.items():
            if source_filter and name != source_filter:
                continue
            last_run = state.get(name, {})
            since_iso = (last_run.get("last_seen_max") or "").strip() or (
                last_run.get("last_successful_run") or ""
            ).strip()
            entry: dict[str, Any] = {
                "status": "skipped", "records_seen": 0, "records_new": 0,
                "records_updated": 0, "records_rejected": 0, "errors": [],
                "last_seen_max": since_iso,
            }
            try:
                conn = cfg.get("connector", {})
                inc_field = conn.get("incremental_field")
                collect_kwargs = {}
                if self.fetch_json is not None:
                    collect_kwargs["fetch_json"] = self.fetch_json
                rows = collect_source(
                    name, cfg,
                    since_iso=since_iso,
                    days_back=days_back,
                    **collect_kwargs,
                )
                # offline fixtures may be keyed by source name (fetch_json(name))
                if self.fetch_json is not None and not rows:
                    rows = self.fetch_json(name) or []
                entry["status"] = "success"
                entry["records_seen"] = len(rows)
                seen = [enrich_violation(r) for r in rows]
                for r in seen:
                    if is_rejected_violation(r):
                        entry["records_rejected"] += 1
                        continue
                    if inc_field:
                        marker = r.get("opened_iso") or r.get("updated_iso") or ""
                        if marker and marker > entry["last_seen_max"]:
                            entry["last_seen_max"] = marker
                    raw.append(r)
                entry["records_new"] = len(seen)
                entry["errors"] = []
            except Exception as exc:  # noqa: BLE001
                entry["status"] = "error"
                entry["errors"].append(f"{name}: {exc}")
            manifest[name] = entry
        return raw, manifest

    # ── group + enrich ─────────────────────────────────────────────────────
    def group_properties(self, raw: list[dict]) -> list[dict]:
        by_addr: dict[str, dict] = {}
        for rec in raw:
            key = normalize_match_addr(rec.get("address", ""))
            if not key:
                continue
            city = rec.get("city", "")
            state = rec.get("state", "")
            county = rec.get("county") or county_for_city(city)
            addr_key = f"{key}|{city}|{state}".upper()
            prop = by_addr.setdefault(addr_key, {
                "address": rec.get("address", ""),
                "city": city, "state": state, "county": county,
                "parcel_id": rec.get("parcel_id", ""),
                "violations": [],
            })
            prop["violations"].append(rec)
            if rec.get("parcel_id"):
                prop["parcel_id"] = rec.get("parcel_id")
        return list(by_addr.values())

    def enrich(self, properties: list[dict], enrich_limit: int, do_enrich: bool) -> list[dict]:
        out: list[dict] = []
        enriched = 0
        for prop in properties:
            owner = resolve_owner(
                prop, live=True,
                dcad_fn=self.dcad_fn, verify_fn=self.verify_fn,
            )
            phone: Optional[PhoneResult] = None
            if do_enrich and enriched < enrich_limit and owner.owner_name:
                phone = enrich_phone(
                    owner, prop,
                    skip_tracer=self.skip_tracer,
                    suppression=self.suppression,
                )
                if phone.status == "OK":
                    enriched += 1
            rec = build_property_record(
                address=prop["address"], city=prop["city"], state=prop["state"],
                county=prop["county"], violations=prop["violations"],
                owner=owner.to_dict(),
                phone=phone.to_dict() if phone else None,
            )
            out.append(rec)
        return out

    # ── dedupe ─────────────────────────────────────────────────────────────
    def dedupe(self, props: list[dict], live_db: list[dict], ledger: dict) -> tuple[list[dict], list[dict], list[dict]]:
        new: list[dict] = []
        upgrades: list[dict] = []
        dupes: list[dict] = []
        for prop in props:
            existing = find_existing(live_db, prop.get("address", ""), prop.get("parcel_id", ""))
            if existing:
                prop["existing_id"] = existing.get("id")
                upgrades.append(prop)
                continue
            # only mark a case-duplicate when we already saw every case id
            fresh_cases = [c for c in prop.get("violation_ids", [])
                           if not ledger.get(record_key({"source": prop.get("sources", ["?"])[0], "case_id": c}))]
            if not fresh_cases and prop.get("violation_ids"):
                dupes.append(prop)
                continue
            new.append(prop)
        return new, upgrades, dupes

    # ── dialer sync ────────────────────────────────────────────────────────
    def build_dialer_records(self, props: list[dict]) -> tuple[list[dict], int]:
        records: list[dict] = []
        ranked: list[tuple[int, dict, ScoreResult]] = []
        for prop in props:
            score = score_property(prop)
            if score.tier not in ("TIER 1", "TIER 2"):
                continue
            ranked.append((score.score, prop, score))
        ranked.sort(key=lambda t: (-t[0], t[1].get("violation_count", 0)))
        for rank, (prop, score) in enumerate((r[1:] for r in ranked), start=1):
            records.append(self._to_dialer_record(prop, score, rank))
        return records, len(ranked)

    def _to_dialer_record(self, prop: dict, score: ScoreResult, rank: int) -> dict:
        address = prop.get("address", "")
        owner = prop.get("owner_name") or prop.get("existing_company") or f"Property Owner {address}"
        prov = build_provenance_fields(
            source="Municipal Open Data (Code Violations)",
            source_reference=",".join(prop.get("violation_ids", [])),
            source_type=SOURCE_TYPE,
            verification_method=VERIFICATION_METHOD,
        )
        if prop.get("owner_verified"):
            prov["verified_at"] = iso(self.now)
            prov["verification_method"] = "county_record"
        script = (
            f"Hi, this is about your property at {address}, {prop.get('city')}, {prop.get('state')}. "
            f"We pulled the city code-violation record ({', '.join(prop.get('violation_ids', []))}) and can "
            f"make a quick cash offer to take it off your hands."
        )
        return {
            "id": prop.get("existing_id") or lead_id(address, prop.get("city", ""), prop.get("state", "")),
            "company": f"{owner} - {address}",
            "contact": owner,
            "title": "Property Owner",
            "owner_status": prop.get("owner_status", ""),
            "source_class": "CODE_VIOLATION",
            "decision_maker_confidence": prop.get("owner_confidence", 0.0),
            "contact_confidence": prop.get("phone_confidence", 0.0),
            "phone": prop.get("phone", ""),
            "email": prop.get("email", ""),
            "vertical": VERTICAL,
            "sales_lane": SALES_LANE,
            "stage": "QUALIFIED",
            "motivation_score": score.score,
            "deal_score": score.score,
            "callability_score": min(100, score.score),
            "tier": score.tier.replace("TIER ", "T"),
            "pitch_angle": "Cash offer on a city code-violation property",
            "details": {
                "address": address,
                "city": prop.get("city", ""),
                "state": prop.get("state", ""),
                "county": prop.get("county", ""),
                "parcel_id": prop.get("parcel_id", ""),
                "Owner_Name": owner,
                "Code Violation Category": ", ".join(prop.get("tags", [])),
                "Case IDs": ", ".join(prop.get("violation_ids", [])),
                "Sources": ", ".join(prop.get("sources", [])),
                "Score Explanation": "; ".join(score.explanation),
                "Call_Script": script,
            },
            "queue_bucket": QUEUE_BUCKET,
            "partition": "PRIMARY",
            "main_queue": "code_violation",
            "callable": True,
            "priority_rank": rank,
            "freshness_score": 100,
            "new_today": True,
            "intent_score": score.score,
            "callability_status": "CALLABLE",
            "verification_status": prop.get("owner_status", "VERIFICATION_REQUIRED"),
            "already_contacted": False,
            "uncalled_verified": False,
            "category": "code_violation",
            "source": prov.get("source", ""),
            "source_reference": prov.get("source_reference", ""),
            "source_type": prov.get("source_type", ""),
            "observed_at": prov.get("observed_at", ""),
            "verified_at": prov.get("verified_at", ""),
            "verification_method": prov.get("verification_method", ""),
        }

    # ── artifacts ──────────────────────────────────────────────────────────
    def write_artifacts(self, props: list[dict], manifest: dict, mode: str,
                        new: list[dict], upgrades: list[dict], dupes: list[dict],
                        errors: list[str], scored: list[tuple[dict, ScoreResult]]) -> dict:
        date_str = _today(self.now)
        day_dir = self.gtm_daily_root / date_str
        day_dir.mkdir(parents=True, exist_ok=True)

        rows = []
        for prop, score in sorted(scored, key=lambda t: (-t[1].score, t[0].get("address", ""))):
            rows.append({
                "rank": score.score,
                "tier": score.tier,
                "address": prop.get("address", ""),
                "city": prop.get("city", ""),
                "state": prop.get("state", ""),
                "county": prop.get("county", ""),
                "parcel_id": prop.get("parcel_id", ""),
                "owner": prop.get("owner_name", ""),
                "owner_status": prop.get("owner_status", ""),
                "phone": prop.get("phone", ""),
                "violation_count": prop.get("violation_count", 0),
                "category": ", ".join(prop.get("tags", [])),
                "score": score.score,
                "explanation": "; ".join(score.explanation),
                "existing_lead": prop.get("existing_id", ""),
            })
        csv_path = day_dir / "code_violation_leads.csv"
        header = [
            "rank", "tier", "address", "city", "state", "county", "parcel_id",
            "owner", "owner_status", "phone", "violation_count", "category",
            "score", "explanation", "existing_lead",
        ]
        with open(csv_path, "w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=header)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
        _write_json(day_dir / "code_violation_daily.csv.json", {"rows": rows})

        tiers = {"TIER 1": 0, "TIER 2": 0, "TIER 3": 0}
        for prop, score in scored:
            tiers[score.tier] = tiers.get(score.tier, 0) + 1
        report = {
            "status": "success" if not errors else "partial",
            "run_id": getattr(self, "_run_id", ""),
            "mode": mode,
            "date": date_str,
            "started_at": getattr(self, "_started_at", ""),
            "finished_at": iso(self.now),
            "sources": manifest,
            "totals": {
                "properties_scored": len(scored),
                "tiers": tiers,
                "new_properties": len(new),
                "upgraded_properties": len(upgrades),
                "case_duplicates": len(dupes),
                "dialer_segment_entries": len(rows),
            },
            "errors": errors,
            "next_action": "Review TIER 1 in the dialer segment CODE_VIOLATION_DAILY and place calls.",
            "owner": "human",
            "timestamp": iso(self.now),
        }
        _write_json(day_dir / "code_violation_daily_report.json", report)
        self._write_founder_report(day_dir, props, scored, manifest, mode)
        return report

    def _write_founder_report(self, day_dir: Path, props: list[dict],
                              scored: list[tuple[dict, ScoreResult]],
                              manifest: dict, mode: str) -> None:
        t1 = [t for t in scored if t[1].tier == "TIER 1"]
        t2 = [t for t in scored if t[1].tier == "TIER 2"]
        lines = [
            f"# Daily Code-Violation Lead Engine — {_today(self.now)}",
            "",
            f"**Mode:** `{mode}`  |  **Properties scored:** {len(scored)}  "
            f"**TIER 1:** {len(t1)}  **TIER 2:** {len(t2)}",
            "",
            "## Money & Progress",
            f"- **{len(t1)} callable TIER 1 sellers** queued for dialing today "
            f"(segment `{QUEUE_BUCKET}`).",
            f"- **{len(t2)} TIER 2** candidates queued as backup.",
            f"- {len(t1) + len(t2)} properties removed from the city's list = "
            "potential cash deals at 50-70% of ARV.",
            "",
            "## Top Today",
        ]
        for i, (prop, score) in enumerate(scored[:10], start=1):
            lines.append(
                f"{i}. **{score.tier}** {prop.get('address', '')}, {prop.get('city', '')} "
                f"— score {score.score} — {', '.join(prop.get('tags', []))} "
                f"({' +'.join(prop.get('phone', '')) or 'no phone'})"
            )
        lines.append("")
        lines.append("## Source Health")
        for name, entry in manifest.items():
            lines.append(f"- `{name}`: {entry.get('status')} "
                         f"({entry.get('records_seen', 0)} seen, "
                         f"{len(entry.get('errors', []))} errors)")
        md_path = day_dir / "code_violation_founder_report.md"
        with open(md_path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")

    # ── GTM ────────────────────────────────────────────────────────────────
    def merge_gtm(self, scored: list[tuple[dict, ScoreResult]], report: dict) -> dict:
        date_str = _today(self.now)
        brief_path = self.gtm_daily_root / f"{date_str}.json"
        latest_path = self.gtm_daily_root / "latest.json"
        t1 = [t for t in scored if t[1].tier == "TIER 1"]
        top = sorted(scored, key=lambda t: (-t[1].score, t[0].get("address", "")))[:10]
        opportunities = [self._to_gtm_opportunity(prop, score) for prop, score in top]

        block = {
            "code_violation": {
                "summary": f"{len(scored)} properties scored, {len(t1)} TIER 1 callable sellers",
                "tiers": report["totals"]["tiers"],
                "opportunities": opportunities,
            }
        }
        merged = {"daily_notes": []}
        for path in (brief_path, latest_path):
            existing = _load_json(path) or {}
            if not isinstance(existing, dict):
                existing = {"daily_notes": []}
            merged = dict(existing)
            merged["code_violation"] = block["code_violation"]
            self._prepend_top(merged, "top_actions", opportunities)
            self._prepend_top(merged, "top_opportunities", opportunities)
            if path == brief_path:
                _write_json(brief_path, merged)
            else:
                _write_json(latest_path, merged)
        return merged

    def _prepend_top(self, merged: dict, key: str, opportunities: list[dict], cap: int = 10) -> None:
        existing = merged.get(key) or []
        if not isinstance(existing, list):
            existing = []
        ids = {o.get("id") for o in opportunities}
        filtered = [e for e in existing if e.get("id") not in ids]
        merged[key] = (opportunities + filtered)[:cap]

    def _to_gtm_opportunity(self, prop: dict, score: ScoreResult) -> dict:
        return {
            "id": lead_id(prop.get("address", ""), prop.get("city", ""), prop.get("state", "")),
            "company": f"{prop.get('owner_name') or 'Property Owner'} - {prop.get('address', '')}",
            "decision_maker": prop.get("owner_name", ""),
            "role": "Property Owner",
            "industry": "Real Estate (Code Violation)",
            "intent_score": score.score,
            "intent_tier": score.tier,
            "priority": "HIGH" if score.tier == "TIER 1" else "MEDIUM",
            "rank": score.score,
            "evidence": {
                "source": ", ".join(prop.get("sources", [])),
                "claim": f"{prop.get('violation_count', 0)} city code violation(s) at "
                         f"{prop.get('address', '')}",
            },
            "pain": "Active city code violations / fines / liens risk",
            "why_now": "City enforcement is active; owner is motivated to sell quickly",
            "recommended_channel": "PHONE",
            "contactability": {"phone": prop.get("phone", ""), "email": prop.get("email", "")},
            "recommended_ai_assistant": "seller_cash_offer",
            "sku": "REAL_ESTATE_CASH_OFFER",
            "offer_summary": "Cash Purchase / Wholesale",
            "primary_offer": "Cash Offer",
            "monthly_retainer_usd": 0,
            "confidence": round((prop.get("owner_confidence", 0.0) + prop.get("phone_confidence", 0.0)) / 2, 2),
            "stage": "QUALIFIED",
        }

    def upsert_gtm_queue(self, scored: list[tuple[dict, ScoreResult]]) -> None:
        t1 = [t for t in scored if t[1].tier == "TIER 1"]
        t2 = [t for t in scored if t[1].tier == "TIER 2"]
        insert = [self._to_gtm_opportunity(p, s) for p, s in t1[:10] + t2[:5]]
        if not insert:
            return
        existing = _load_json(self.gtm_queue_path)
        if not isinstance(existing, list):
            existing = []
        ids = {o.get("id") for o in insert}
        existing = [e for e in existing if e.get("id") not in ids]
        existing = (insert + existing)[:25]
        _write_json(self.gtm_queue_path, existing)

    # ── run ────────────────────────────────────────────────────────────────
    def run(self, apply: bool = False, days_back: int = 45, enrich_limit: int = 40,
            do_enrich: bool = True, source_filter: Optional[str] = None) -> dict:
        self._run_id = f"CV-{_today(self.now)}-{os.urandom(2).hex()}"
        self._started_at = iso(self.now)
        errors: list[str] = []
        try:
            raw, manifest = self.collect(days_back=days_back, source_filter=source_filter)
            properties = self.group_properties(raw)
            enriched = self.enrich(properties, enrich_limit=enrich_limit, do_enrich=do_enrich)
            live_db = load_live_db(self.dialer_db_path)
            ledger = self.load_ledger() if apply else {}
            new, upgrades, dupes = self.dedupe(enriched, live_db, ledger)
            scored: list[tuple[dict, ScoreResult]] = [(p, score_property(p)) for p in new + upgrades]
            dialer_records, segment_count = self.build_dialer_records(new + upgrades)

            if apply:
                for prop in new:
                    for c in prop.get("violation_ids", []):
                        src = (prop.get("sources") or ["?"])[0]
                        ledger[record_key({"source": src, "case_id": c})] = {
                            "first_seen": iso(self.now),
                            "address": prop.get("address", ""),
                        }
                self._persist_ledger(ledger)
                if dialer_records:
                    patch_dialer_db(dialer_records, reason="code_violation_daily", author="CODE_VIOLATION_DAILY")
                for name, entry in manifest.items():
                    entry["last_successful_run"] = iso(self.now)
                self._persist_state(manifest)

            report = self.write_artifacts(enriched, manifest, "apply" if apply else "dry-run",
                                          new, upgrades, dupes, errors, scored)
            if apply:
                self.merge_gtm(scored, report)
                self.upsert_gtm_queue(scored)

            report["outputs"] = {
                "raw_violations": len(raw),
                "properties": len(enriched),
                "new_properties": len(new),
                "upgraded_properties": len(upgrades),
                "dialer_segment_entries": segment_count,
                "tiers": report["totals"]["tiers"],
                "artifacts_dir": str(self.gtm_daily_root / _today(self.now)),
            }
            return report
        except Exception as exc:  # noqa: BLE001
            return {
                "status": "failure",
                "run_id": getattr(self, "_run_id", ""),
                "mode": "apply" if apply else "dry-run",
                "errors": [str(exc)],
                "outputs": {},
                "next_action": "Inspect traceback, fix, and re-run.",
                "owner": "human",
                "timestamp": iso(self.now),
            }


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_pipeline(
    root_dir: str = ".", apply: bool = False, days_back: int = 45,
    enrich_limit: int = 40, do_enrich: bool = True, source_filter: Optional[str] = None,
) -> dict:
    root = Path(root_dir)
    if str(root) != ".":
        os.chdir(root)
    pipeline = CodeViolationDailyPipeline(root_dir=root)
    return pipeline.run(apply=apply, days_back=days_back, enrich_limit=enrich_limit,
                        do_enrich=do_enrich, source_filter=source_filter)
