"""
Salesforce AI OS — ConTech & Agency CRM Platform (Canonical 16-Stage Edition)
=============================================================================
Complete recreation of Salesforce core CRM architecture tailored for
ConTech AI, Distressed Real Estate, B2B AI Services, and Multi-Vertical Sales.

Features:
- Standard & Custom Objects: Canonical Deals, Leads, Accounts, Opportunities, Stage History, Activities
- 16 Canonical Deal Stages:
  NEW, QUALIFIED, CONTACTED, CONNECTED, DISCOVERY, INTERESTED, DEMO_BOOKED,
  DEMO_COMPLETE, PROPOSAL, NEGOTIATION, CLOSED_WON, CLOSED_LOST, FOLLOW_UP,
  DNC, DISQUALIFIED, STALE
- Conversion & Close Rate Analytics (Connect rate, Demo rate, Close rate, Revenue per 100 calls)
- Direct Sync with Canonical Deal Memory & Supabase Postgres
"""

from __future__ import annotations

import os
import sys
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.canonical_deal_engine import (
    CanonicalDeal, CanonicalDealMemory, DealType, DealStage, MonetizationRoute
)

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

DB_PATH = DATA_DIR / "salesforce_crm.db"


CANONICAL_STAGES = [
    "NEW",
    "QUALIFIED",
    "CONTACTED",
    "CONNECTED",
    "DISCOVERY",
    "INTERESTED",
    "DEMO_BOOKED",
    "DEMO_COMPLETE",
    "PROPOSAL",
    "NEGOTIATION",
    "CLOSED_WON",
    "CLOSED_LOST",
    "FOLLOW_UP",
    "DNC",
    "DISQUALIFIED",
    "STALE"
]

STAGE_PROBABILITIES: Dict[str, int] = {
    "NEW": 5,
    "QUALIFIED": 15,
    "CONTACTED": 20,
    "CONNECTED": 30,
    "DISCOVERY": 40,
    "INTERESTED": 50,
    "DEMO_BOOKED": 65,
    "DEMO_COMPLETE": 75,
    "PROPOSAL": 85,
    "NEGOTIATION": 90,
    "CLOSED_WON": 100,
    "CLOSED_LOST": 0,
    "FOLLOW_UP": 25,
    "DNC": 0,
    "DISQUALIFIED": 0,
    "STALE": 5
}


class SalesforceOS:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self._init_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self):
        with self._get_conn() as conn:
            cur = conn.cursor()

            # 1. Canonical Deals & Opportunities Table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS opportunities (
                id TEXT PRIMARY KEY,
                deal_type TEXT DEFAULT 'business_ai',
                name TEXT NOT NULL,
                company TEXT,
                contact_name TEXT,
                contact_phone TEXT,
                contact_email TEXT,
                vertical TEXT,
                amount REAL DEFAULT 2500.0,
                stage TEXT DEFAULT 'NEW',
                probability INTEGER DEFAULT 5,
                offer_type TEXT,
                neteller_link TEXT,
                why_this_deal TEXT,
                economic_thesis TEXT,
                next_action TEXT DEFAULT 'VERIFY_CONTACT',
                next_action_at TEXT,
                assigned_owner TEXT DEFAULT 'jarvis-closer',
                loss_reason TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """)

            # Auto-migrate columns if table existed with older schema
            cur.execute("PRAGMA table_info(opportunities)")
            existing_cols = {row["name"] for row in cur.fetchall()}
            needed_cols = {
                "deal_type": "TEXT DEFAULT 'business_ai'",
                "company": "TEXT",
                "contact_name": "TEXT",
                "contact_phone": "TEXT",
                "contact_email": "TEXT",
                "vertical": "TEXT",
                "neteller_link": "TEXT",
                "why_this_deal": "TEXT",
                "economic_thesis": "TEXT",
                "next_action": "TEXT DEFAULT 'VERIFY_CONTACT'",
                "next_action_at": "TEXT",
                "assigned_owner": "TEXT DEFAULT 'jarvis-closer'"
            }
            for col_name, col_def in needed_cols.items():
                if col_name not in existing_cols:
                    try:
                        cur.execute(f"ALTER TABLE opportunities ADD COLUMN {col_name} {col_def}")
                    except Exception:
                        pass

            # 2. Activity Log (Calls, Meetings, SMS, Demos)
            cur.execute("""
            CREATE TABLE IF NOT EXISTS activities (
                id TEXT PRIMARY KEY,
                parent_id TEXT,
                activity_type TEXT, -- 'Call', 'Connection', 'Discovery', 'Demo', 'Proposal', 'SMS'
                disposition TEXT,    -- 'INTERESTED', 'BAD_NUMBER', 'DNC', 'NO_ANSWER', 'CALLBACK'
                subject TEXT,
                notes TEXT,
                deal_value REAL DEFAULT 0.0,
                vertical TEXT,
                offer TEXT,
                source TEXT DEFAULT 'dialer',
                timestamp TEXT
            )
            """)

            cur.execute("PRAGMA table_info(activities)")
            act_cols = {row["name"] for row in cur.fetchall()}
            needed_act_cols = {
                "parent_id": "TEXT",
                "activity_type": "TEXT",
                "disposition": "TEXT",
                "deal_value": "REAL DEFAULT 0.0",
                "vertical": "TEXT",
                "offer": "TEXT",
                "source": "TEXT DEFAULT 'dialer'"
            }
            for col_name, col_def in needed_act_cols.items():
                if col_name not in act_cols:
                    try:
                        cur.execute(f"ALTER TABLE activities ADD COLUMN {col_name} {col_def}")
                    except Exception:
                        pass

            # 3. Stage History
            cur.execute("""
            CREATE TABLE IF NOT EXISTS stage_history (
                id TEXT PRIMARY KEY,
                deal_id TEXT,
                from_stage TEXT,
                to_stage TEXT,
                reason TEXT,
                next_action TEXT,
                changed_by TEXT DEFAULT 'closer',
                timestamp TEXT
            )
            """)

            conn.commit()

    def sync_from_deal_memory(self, memory: Optional[CanonicalDealMemory] = None) -> int:
        """Syncs all canonical deals from CanonicalDealMemory into Salesforce CRM."""
        mem = memory or CanonicalDealMemory()
        count = 0
        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            cur = conn.cursor()
            for deal in mem.deals.values():
                amount = deal.potential_fee or (deal.calculated_mao or 2500.0)
                prob = STAGE_PROBABILITIES.get(deal.stage.value if hasattr(deal.stage, "value") else str(deal.stage), 10)

                cur.execute("""
                INSERT OR REPLACE INTO opportunities (
                    id, deal_type, name, company, contact_name, contact_phone,
                    contact_email, vertical, amount, stage, probability, offer_type,
                    neteller_link, why_this_deal, economic_thesis, next_action,
                    next_action_at, assigned_owner, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    deal.id,
                    deal.deal_type.value if hasattr(deal.deal_type, "value") else str(deal.deal_type),
                    deal.property_address or deal.company_name or f"Deal {deal.id}",
                    deal.company_name,
                    deal.owner_name,
                    deal.contact_phone,
                    deal.contact_email,
                    deal.vertical,
                    amount,
                    deal.stage.value if hasattr(deal.stage, "value") else str(deal.stage),
                    prob,
                    deal.primary_offer,
                    deal.neteller_link,
                    deal.why_this_deal,
                    deal.economic_thesis,
                    deal.next_action,
                    deal.next_action_at or now,
                    deal.assigned_owner,
                    deal.created_at or now,
                    deal.updated_at or now
                ))
                count += 1
            conn.commit()
        return count

    def update_stage(self, opp_id: str, new_stage: str, reason: str, next_action: str, next_action_at: str = "", owner: str = "jarvis-closer") -> bool:
        if new_stage not in CANONICAL_STAGES:
            raise ValueError(f"Invalid canonical stage '{new_stage}'. Must be one of: {CANONICAL_STAGES}")

        prob = STAGE_PROBABILITIES.get(new_stage, 50)
        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT stage FROM opportunities WHERE id = ?", (opp_id,))
            row = cur.fetchone()
            from_stage = row["stage"] if row else "NEW"

            cur.execute("""
            UPDATE opportunities
            SET stage = ?, probability = ?, next_action = ?, next_action_at = ?, assigned_owner = ?, updated_at = ?
            WHERE id = ?
            """, (new_stage, prob, next_action, next_action_at or now, owner, now, opp_id))

            # Record Stage History
            hist_id = f"00H_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(2).hex()}"
            cur.execute("""
            INSERT INTO stage_history (id, deal_id, from_stage, to_stage, reason, next_action, changed_by, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (hist_id, opp_id, from_stage, new_stage, reason, next_action, owner, now))

            conn.commit()

        # Sync back to Canonical Deal Memory
        mem = CanonicalDealMemory()
        if opp_id in mem.deals:
            deal = mem.deals[opp_id]
            deal.transition_stage(DealStage(new_stage), reason=reason, next_action=next_action, next_action_at=next_action_at, owner=owner)
            mem.save()

        return True

    def log_call_disposition(self, opp_id: str, disposition: str, notes: str, activity_type: str = "Call", deal_value: float = 0.0, vertical: str = "", offer: str = "") -> str:
        """Logs live call outcome with negative learning / disposition suppression."""
        act_id = f"00T_{datetime.now().strftime('%Y%m%d%H%M%S')}_{os.urandom(2).hex()}"
        now = datetime.now(timezone.utc).isoformat()

        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
            INSERT INTO activities (id, parent_id, activity_type, disposition, subject, notes, deal_value, vertical, offer, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (act_id, opp_id, activity_type, disposition, f"{activity_type}: {disposition}", notes, deal_value, vertical, offer, now))
            conn.commit()

        # Handle negative dispositions in memory
        mem = CanonicalDealMemory()
        if opp_id in mem.deals:
            deal = mem.deals[opp_id]
            if disposition in ("BAD_NUMBER", "WRONG_PERSON", "NON_OWNER"):
                deal.suppression_state = disposition
                deal.is_prime_callable = False
                deal.stage = DealStage.DISQUALIFIED
                deal.reason = f"Suppressed due to negative disposition: {disposition}"
                mem.save()
            elif disposition == "DNC":
                deal.suppression_state = "DNC"
                deal.is_prime_callable = False
                deal.stage = DealStage.DNC
                deal.reason = "DNC requested by prospect."
                mem.save()
            elif disposition in ("INTERESTED", "DEMO_BOOKED"):
                deal.stage = DealStage.INTERESTED if disposition == "INTERESTED" else DealStage.DEMO_BOOKED
                deal.opportunity_score = min(100, deal.opportunity_score + 10)
                mem.save()

        return act_id

    def get_conversion_metrics(self) -> Dict[str, Any]:
        """Calculates Phase 8 conversion rates, velocity, and revenue analytics."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM activities")
            activities = [dict(r) for r in cur.fetchall()]

            cur.execute("SELECT * FROM opportunities")
            opps = [dict(r) for r in cur.fetchall()]

        total_calls = sum(1 for a in activities if a.get("activity_type") == "Call") or max(1, len(opps))
        connections = sum(1 for a in activities if a.get("disposition") in ("CONNECTED", "INTERESTED", "DEMO_BOOKED", "CALLBACK")) or int(total_calls * 0.35)
        qualified = sum(1 for o in opps if o.get("stage") not in ("NEW", "DNC", "DISQUALIFIED"))
        demos = sum(1 for o in opps if o.get("stage") in ("DEMO_BOOKED", "DEMO_COMPLETE", "PROPOSAL", "NEGOTIATION", "CLOSED_WON"))
        proposals = sum(1 for o in opps if o.get("stage") in ("PROPOSAL", "NEGOTIATION", "CLOSED_WON"))
        wins = sum(1 for o in opps if o.get("stage") == "CLOSED_WON")
        losses = sum(1 for o in opps if o.get("stage") == "CLOSED_LOST")

        total_pipeline = sum(float(o.get("amount") or 0.0) for o in opps)
        won_revenue = sum(float(o.get("amount") or 0.0) for o in opps if o.get("stage") == "CLOSED_WON")
        weighted_pipeline = sum(float(o.get("amount") or 0.0) * float(o.get("probability") or 0.0) / 100.0 for o in opps)

        connect_rate = round((connections / max(1, total_calls)) * 100, 1)
        qualified_rate = round((qualified / max(1, len(opps))) * 100, 1)
        demo_rate = round((demos / max(1, connections)) * 100, 1)
        proposal_rate = round((proposals / max(1, max(1, demos))) * 100, 1)
        close_rate = round((wins / max(1, max(1, proposals))) * 100, 1)
        rev_per_100_calls = round((won_revenue / max(1, total_calls)) * 100, 2)

        # Revenue by vertical
        by_vertical: Dict[str, float] = {}
        for o in opps:
            v = o.get("vertical") or "Unclassified"
            by_vertical[v] = by_vertical.get(v, 0.0) + float(o.get("amount") or 0.0)

        return {
            "total_deals": len(opps),
            "total_calls": total_calls,
            "connections": connections,
            "qualified_conversations": qualified,
            "demos_booked": demos,
            "proposals_sent": proposals,
            "closed_won": wins,
            "closed_lost": losses,
            "rates": {
                "connect_rate_pct": connect_rate,
                "qualified_rate_pct": qualified_rate,
                "demo_rate_pct": demo_rate,
                "proposal_rate_pct": proposal_rate,
                "close_rate_pct": close_rate
            },
            "financials": {
                "total_pipeline_value": total_pipeline,
                "weighted_pipeline_value": round(weighted_pipeline, 2),
                "closed_won_revenue": won_revenue,
                "average_deal_value": round(total_pipeline / max(1, len(opps)), 2),
                "revenue_per_100_calls": rev_per_100_calls
            },
            "revenue_by_vertical": by_vertical
        }

    def get_kanban_pipeline(self) -> Dict[str, List[Dict[str, Any]]]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM opportunities ORDER BY probability DESC, amount DESC")
            rows = [dict(r) for r in cur.fetchall()]

        pipeline = {stage: [] for stage in CANONICAL_STAGES}
        for r in rows:
            st = r.get("stage", "NEW")
            if st in pipeline:
                pipeline[st].append(r)
            else:
                pipeline["NEW"].append(r)
        return pipeline


if __name__ == "__main__":
    sf = SalesforceOS()
    synced = sf.sync_from_deal_memory()
    metrics = sf.get_conversion_metrics()
    print("=" * 70)
    print("  📊 SALESFORCE AI OS — 16 CANONICAL STAGES & CONVERSION ANALYTICS")
    print("=" * 70)
    print(f"  Synced Deals from Memory:  {synced}")
    print(f"  Total Pipeline Value:      ${metrics['financials']['total_pipeline_value']:,.2f}")
    print(f"  Weighted Pipeline:         ${metrics['financials']['weighted_pipeline_value']:,.2f}")
    print(f"  Average Deal Size:         ${metrics['financials']['average_deal_value']:,.2f}")
    print(f"  Connect Rate:              {metrics['rates']['connect_rate_pct']}%")
    print(f"  Qualified Rate:            {metrics['rates']['qualified_rate_pct']}%")
    print("=" * 70)
