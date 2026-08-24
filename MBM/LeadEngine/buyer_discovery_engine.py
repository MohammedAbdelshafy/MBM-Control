"""
MBM LeadEngine — Buyer Discovery Engine
=======================================
Discovers and loads active vacant land buyers, builders, and developers.
"""

import os
import csv
from pathlib import Path
from typing import List, Dict, Any, Tuple
from datetime import datetime, timezone
import uuid
from enum import Enum

from MBM.LeadEngine.canonical_lead_schema import CanonicalBuyer

class SourceStatus(Enum):
    READY = "READY"
    NO_SOURCE_CONFIGURED = "NO_SOURCE_CONFIGURED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    BLOCKED = "BLOCKED"
    RATE_LIMITED = "RATE_LIMITED"
    MANUAL_ONLY = "MANUAL_ONLY"
    TEST_FIXTURE = "TEST_FIXTURE"

class BuyerDiscoveryEngine:
    def __init__(self, buyer_data_path: Path = None):
        if buyer_data_path is None:
            # Look for legitimate MBM source artifact
            root_dir = Path(__file__).resolve().parents[2]
            self.buyer_data_path = root_dir / "MBM" / "Artifacts" / "buyer_contacts.csv"
        else:
            self.buyer_data_path = buyer_data_path

    def discover_active_buyers(self) -> Tuple[SourceStatus, List[CanonicalBuyer]]:
        """
        Loads active buyers and constructs their Buy-Boxes.
        Prioritizes existing buyer intelligence.
        """
        buyers = []
        if self.buyer_data_path.exists() and self.buyer_data_path.name.endswith(".csv"):
            try:
                # Use file mod time if available as provenance timestamp
                mod_time = datetime.fromtimestamp(self.buyer_data_path.stat().st_mtime, tz=timezone.utc).isoformat()
                
                with open(self.buyer_data_path, mode='r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Validation: require Company or Contact Name
                        entity = row.get("Entity_Name", "").strip() or row.get("Company", "").strip()
                        contact = row.get("Contact_Name", "").strip()
                        if not entity and not contact:
                            continue
                            
                        buyers.append(self._parse_buyer(row, mod_time))
            except Exception as e:
                print(f"[WARN] Failed to load buyer data from {self.buyer_data_path}: {e}")
                
        if not buyers:
            return SourceStatus.NO_SOURCE_CONFIGURED, []
            
        return SourceStatus.READY, buyers

    def _parse_buyer(self, data: Dict[str, Any], mod_time: str) -> CanonicalBuyer:
        return CanonicalBuyer(
            buyer_id=data.get("buyer_id", f"BUYER-{uuid.uuid4().hex[:8].upper()}"),
            buyer_name=data.get("Contact_Name", "Unknown").strip(),
            company=data.get("Entity_Name", data.get("Company", "Unknown")).strip(),
            buyer_type=data.get("Category", "UNKNOWN").strip(),
            market=data.get("City", "").strip(),
            state=data.get("State", "").strip(),
            county="",
            target_zip=[],
            min_acres=0.0,  # Legacy sources lack buy-box criteria, default to unknown (0)
            max_acres=0.0,
            target_lot_size="",
            price_min=0.0,
            price_max=0.0,
            price_per_lot=0.0,
            zoning=[],
            utilities=[],
            road_access=[],
            property_type=[],
            lots_per_month=0,
            homes_per_year=0,
            buying_activity="ACTIVE",
            source=data.get("Lead_Source", "PropStream Export").strip(),
            source_url=data.get("Website", "").strip(),
            evidence="Historical MBM Artifact",
            observed_at=mod_time,
            confidence=float(data.get("Confidence") or 80.0) if data.get("Confidence") else 80.0,
            status=data.get("Status", "ACTIVE").strip() or "ACTIVE"
        )
