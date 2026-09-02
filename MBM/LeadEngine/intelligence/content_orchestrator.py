"""
ContentOrchestrator — wires INTELLIGENCE -> OPPORTUNITY -> PRODUCTION (§13).

                    World Monitor (MCP/REST)
                           |
                    IntelligenceEngine
                           |
                   +-------+--------+
                   |                |
              ContentOpp      MonetizationOpp
                   |                |
                   +-------+--------+
                           |
                  ContentOrchestrator
                           |
                   +-------+--------+
                   |                |
                Topview         SkySnail
                   |                |
                   +-------+--------+
                           |
                        QA Gate
                           |
                    Human Approval
                           |
                 Publishing (existing stack)

The orchestrator never auto-publishes; Topview/SkySnail outputs are jobs/
variants that require human approval. New opportunities enter the existing
system only via the canonical queue -> SingleWriter path (§14).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from .types import IntelligenceEvent, Opportunity, OpportunityStatus
from .intelligence_engine import IntelligenceEngine
from .opportunity_engine import OpportunityEngine, ScoringConfig
from .opportunity_queue import write_opportunities
from .anderro_adapter import AnderroAdapter
from .topview_adapter import TopviewAdapter
from .skysnail_adapter import SkySnailAdapter
from .observability import AuditLog

@dataclass
class OrchestratorResult:
    opportunities: List[Dict[str, Any]]
    generation_jobs: List[Dict[str, Any]]
    thumbnail_variants: List[Dict[str, Any]]
    awaiting_approval: List[Dict[str, Any]]

class ContentOrchestrator:
    def __init__(
        self,
        intel: Optional[IntelligenceEngine] = None,
        opp_engine: Optional[OpportunityEngine] = None,
        anderro: Optional[AnderroAdapter] = None,
        topview: Optional[TopviewAdapter] = None,
        skysnail: Optional[SkySnailAdapter] = None,
        audit: Optional[AuditLog] = None,
    ):
        self.intel = intel
        self.opp_engine = opp_engine or OpportunityEngine()
        self.anderro = anderro
        self.topview = topview
        self.skysnail = skysnail
        self.audit = audit or AuditLog()

    def run(
        self,
        *,
        query: str = "",
        category: str = "",
        limit: int = 12,
        create_drafts: bool = False,
        create_thumbnails: bool = False,
        top_n: int = 10,
    ) -> Dict[str, Any]:
        """
        End-to-end: ingest intelligence -> score opportunities -> push to Review Queue.
        When create_drafts is False, no external generation calls are made (safe dry-run).
        """
        started = datetime.now(timezone.utc).isoformat()

        # 1. intelligence
        if self.intel is None:
            return {"ok": False, "code": "NOT_CONFIGURED", "error": "IntelligenceEngine not wired (check WORLDMONITOR_API_KEY + INTELLIGENCE_ENABLED)"}

        ingest = self.intel.ingest(query=query, category=category, limit=limit, persist=True)
        if not ingest.get("ok"):
            return {"ok": False, "stage": "intelligence", **ingest}

        # ingest events may already be IntelligenceEvent dicts with Provenance objects or dicts
        from .types import Provenance as _Prov
        events: list[IntelligenceEvent] = []
        for e in ingest.get("events") or []:
            prov = e.get("provenance")
            if isinstance(prov, _Prov):
                prov_obj = prov
            elif isinstance(prov, dict):
                prov_obj = _Prov(**{k: v for k, v in prov.items() if k in _Prov.__dataclass_fields__})
            else:
                prov_obj = _Prov(provider="worldmonitor")
            events.append(IntelligenceEvent(
                id=e["id"], source=e["source"], sourceUrl=e.get("sourceUrl"),
                observedAt=e["observedAt"], publishedAt=e.get("publishedAt"),
                category=e["category"], title=e["title"], summary=e.get("summary"),
                entities=e.get("entities") or [], locations=e.get("locations") or [],
                topics=e.get("topics") or [], confidence=e.get("confidence"),
                freshnessSeconds=e.get("freshnessSeconds"), rawReference=e.get("rawReference"),
                provenance=prov_obj,
            ))

        # 2. monetization offers (live, never hardcoded)
        offers = []
        if self.anderro:
            try:
                offers = self.anderro.list_offers(limit=30)
            except Exception as e:
                self.audit.append("orchestrator.anderro", "anderro", status="failed", detail={"error": str(e)[:400]})
                offers = []

        # 3. opportunity ranking
        ranked = self.opp_engine.rank(events, offers, top_n=top_n)
        
        # Hydrate Opportunity dataclasses from dicts
        opp_objects = []
        for r in ranked:
            opp_dict = r["opportunity"]
            # Convert dict back to Opportunity instance to write to queue safely
            opp = Opportunity(**opp_dict)
            opp_objects.append(opp)
            
        # Write to human-review queue (Side-car storage)
        queued_count = write_opportunities(opp_objects)

        gen_jobs: List[Dict[str, Any]] = []
        variants: List[Dict[str, Any]] = []

        # 4. production (only when explicitly requested; gated behind flags)
        if create_drafts:
            for entry in ranked[:3]:  # cap drafts per run
                opp_dict = entry["opportunity"]
                hook = str(opp_dict.get("title") or "")
                script = str(opp_dict.get("summary") or hook)
                if self.topview:
                    job = self.topview.create_generation_job(hook=hook, script=script, opportunity_id=str(opp_dict.get("opportunity_id") or ""), title=hook)
                    gen_jobs.append(job.to_dict())
                if self.skysnail and create_thumbnails:
                    vs = self.skysnail.generate_variants(source_asset_id=str(opp_dict.get("opportunity_id") or "unknown"), topic=hook, transcript=script, count=3)
                    variants.extend([v.__dict__ for v in vs])

        awaiting = [{"opportunity_id": r["opportunity"]["opportunity_id"], "title": r["opportunity"]["title"], "score": r["score"], "status": r["opportunity"]["status"]} for r in ranked]

        self.audit.append("orchestrator.run", "orchestrator", status="ok", detail={"ingested": len(events), "ranked": len(ranked), "queued": queued_count, "jobs": len(gen_jobs), "variants": len(variants)})

        return {
            "ok": True,
            "started_at": started,
            "ingest": {"fetched": ingest.get("fetched"), "deduped": ingest.get("deduped"), "store": ingest.get("store")},
            "opportunities": ranked,
            "generation_jobs": gen_jobs,
            "thumbnail_variants": variants,
            "awaiting_approval": awaiting,
            "queued": queued_count,
            "note": "All Topview/SkySnail outputs require human approval before publishing (QA gate not bypassed).",
        }

