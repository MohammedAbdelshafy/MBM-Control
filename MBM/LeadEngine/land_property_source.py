"""
MBM LeadEngine — Land Property Source
=======================================
Discovers properties from county verification artifacts.
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Tuple
from enum import Enum
from MBM.LeadEngine.lead_provenance import build_provenance_fields

ROOT_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"

class SourceStatus(Enum):
    READY = "READY"
    NO_SOURCE_CONFIGURED = "NO_SOURCE_CONFIGURED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    BLOCKED = "BLOCKED"
    RATE_LIMITED = "RATE_LIMITED"
    MANUAL_ONLY = "MANUAL_ONLY"
    TEST_FIXTURE = "TEST_FIXTURE"

class LandPropertySource:
    def __init__(self):
        pass

    def load_properties(self) -> Tuple[SourceStatus, List[Dict[str, Any]]]:
        """
        Ingest real county-verified property owners (DCAD-style) as sellers.
        ONLY authoritative county artifacts are accepted.
        Returns status and a list of normalized property candidates.
        """
        candidates: List[Dict[str, Any]] = []
        property_artifacts = [
            p
            for p in ARTIFACTS_DIR.glob("property_*_verified.json")
            if "fixture" not in p.name.lower()
        ]
        
        intel_dir = ROOT_DIR / "MBM" / "LeadEngine" / "property_intel" / "artifacts"
        intel_artifacts = list(intel_dir.glob("property_pipeline_*.json")) if intel_dir.exists() else []

        all_artifacts = list(property_artifacts) + intel_artifacts

        if not all_artifacts:
            return SourceStatus.NO_SOURCE_CONFIGURED, []

        for path in all_artifacts:
            try:
                rows = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(rows, dict):
                    rows = rows.get("leads") or rows.get("properties") or []
            except Exception:
                continue
                
            for row in rows if isinstance(rows, list) else []:
                # Never ingest sample fixtures
                if str(row.get("source", "")) in {"sample-fixture", "fixture", "demo", "mock"}:
                    continue
                if not row.get("county_resolved") and not row.get("ownership_status") == "VERIFIED":
                    continue
                    
                owner = str(row.get("owner_name", "")).strip()
                addr = str(row.get("address", "")).strip()
                parcel = str(row.get("parcel_id", "")).strip()
                phone = str(row.get("phone") or row.get("verified_phone") or "").strip()
                city = str(row.get("city", "")).strip()
                state = str(row.get("state", "")).strip()
                county_source = str(row.get("county_source_url") or row.get("ownership_source_url") or "").strip()
                
                if not owner or not parcel or not addr:
                    continue
                    
                provenance = build_provenance_fields(
                    source=str(row.get("county_source") or row.get("ownership_source") or "County Appraisal District"),
                    source_reference=county_source or f"parcel:{parcel}",
                    source_type="county_record",
                    verification_method="county_record",
                    observed_at=str(row.get("source_date") or row.get("observed_at") or ""),
                )
                
                cand = {
                    "id": f"SELLER-{parcel}",
                    "company": addr,
                    "decision_maker": owner,
                    "role": "Property Owner",
                    "industry": "Real Estate Sellers",
                    "phone": phone,
                    "email": "",
                    "city": city,
                    "state": state,
                    "property_address": addr,
                    "parcel_id": parcel,
                    "why_this_company": f"County-verified property owner at {addr} (parcel {parcel}).",
                    "source_class": "COUNTY_RECORD",
                    "acreage": float(row.get("acreage", 0.0)),
                    "zoning": str(row.get("zoning", "")),
                    "absentee_owner": bool(row.get("absentee_owner", False))
                }
                cand.update(provenance)
                candidates.append(cand)
                
        status = SourceStatus.READY if candidates else SourceStatus.NO_SOURCE_CONFIGURED
        return status, candidates
