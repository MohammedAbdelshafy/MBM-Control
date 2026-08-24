"""
crayo_engine -- Canonical Crayo-class production loop (orchestrator).

Wires the full pipeline through EXISTING and new modules:

    ingest (caller-supplied segments)
      -> candidate_pool (Phase 1: large pool + 8-axis scoring + selection)
      -> routing_decision (Phase 4: WHERE/WHEN/SHOULD/variant)
      -> content_intelligence (Phase 3: hook/title/desc/caption/hashtags/CTA)
      -> video_editing (Phase 2: reframe/caption command builders)
      -> publishing (Phase 6: resilient publish, idempotent, dead-letter)
      -> revenue_attribution (Phase 7: estimated/actual economics)
      -> learning_feedback (Phase 8: Enterprise Memory update)
      -> observability (Phase 11: metrics)

External steps (real transcription, real FFmpeg render, real publisher, real
analytics) are INJECTED so the loop is testable end-to-end without media or
network. The loop never claims a publish it did not receive a real result for.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from . import candidate_pool as cp
from . import distribution_optimizer as dist
from . import routing_decision as rd
from . import content_intelligence as ci
from . import video_editing as ve
from . import publishing as pub
from . import revenue_attribution as ra
from . import learning_feedback as lf
from . import observability as ob
from . import circuit_breaker as cb


@dataclass
class CrayoConfig:
    brand: str
    profile: str
    source_id: str
    pool: cp.PoolConfig
    policy: dist.DistributionPolicy
    niche: str = ""


def run_crayo_loop(
    cfg: CrayoConfig,
    *,
    segments: Optional[list[dict]] = None,
    publisher_fn: Callable[[dict], dict],
    dlq_dir: Path,
    analytics_fn: Optional[Callable[[str], dict]] = None,
    idempotency_store: Optional[pub.IdempotencyStore] = None,
    registry: Optional[ra.RewardRateRegistry] = None,
    metrics: Optional[ob.Metrics] = None,
    enable_learning: bool = True,
) -> dict:
    metrics = metrics or ob.Metrics()
    store = idempotency_store or pub.IdempotencyStore()
    registry = registry or ra.RewardRateRegistry()

    # PHASE 1 — candidate pool + scoring + selection
    candidates = cp.generate_candidates(
        cfg.source_id, cfg=cfg.pool, segments=segments, caption_quality=0.7)
    metrics.record_clip(len(candidates))
    selected = cp.select_publishable(candidates, cfg.pool)

    # PHASE 5 — distribution decision (no history yet -> flat/hold)
    perf = dist.PerformanceSignal()
    decision = dist.recommend(cfg.policy, perf, queue_depth=0)

    used_p: dict[str, int] = {}
    used_c: dict[str, int] = {}
    results: list[dict] = []
    econ_rows: list[ra.ClipEconomics] = []

    for cand in selected:
        if not decision["should_publish"]:
            break
        dec = rd.decide(cand, cfg.brand, cfg.policy, used_p, used_c)
        if dec.manual or not dec.should_publish:
            results.append({"clip_id": cand.clip_id, "status": "manual",
                            "reasons": dec.reasons})
            continue

        # PHASE 3 — metadata generation (uses learning memory if enabled)
        history = lf.get_winning_patterns(cfg.brand) if enable_learning else None
        meta = ci.generate_metadata(
            {"transcript_window": ""}, cfg.brand, dec.platform,
            topic=cfg.niche, history=history)

        # PHASE 2 — editing command (constructed, not executed here)
        edit_cmd = ve.build_platform_render(
            "source.mp4", f"out_{cand.clip_id}.mp4", dec.platform,
            start_ts=cand.start_ts, end_ts=cand.end_ts)

        package = {
            "asset_id": cand.clip_id,
            "brand": cfg.brand,
            "target_platform": dec.platform,
            "channel": dec.channel,
            "title": meta["title"],
            "description": meta["description"],
            "hashtags": meta["hashtags"],
            "hook": meta["hook"],
            "edit_command": edit_cmd,
            "publish_at": dec.publish_at,
        }

        # PHASE 6 — resilient publish
        pres = pub.publish_with_resilience(
            package, publisher_fn, store=store, dlq_dir=dlq_dir,
            breaker=cb.CircuitBreaker())
        metrics.record_publish_attempt(pres.status == "published", retries=0)

        # PHASE 7 — economics (estimated unless analytics supplied)
        if analytics_fn is not None:
            a = analytics_fn(cand.clip_id)
            econ = ra.actual_clip(cand.clip_id, dec.platform,
                                  views=float(a.get("views", 0)),
                                  cost_usd=0.10,
                                  revenue_usd=float(a.get("revenue_usd", 0.0)))
            if enable_learning:
                lf.record_analytics(cand.clip_id, int(a.get("views", 0)),
                                    float(a.get("ctr", 0.0)),
                                    float(a.get("watch_time", 0.0)),
                                    int(a.get("subs", 0)),
                                    float(a.get("revenue_usd", 0.0)))
        else:
            econ = ra.estimate_clip(cand.clip_id, dec.platform, views=0,
                                   cost_usd=0.10, registry=registry)
        econ_rows.append(econ)

        # PHASE 8 — learning memory
        if enable_learning:
            lf.record_clip(cand.clip_id, cfg.brand, cfg.profile,
                           hook=meta["hook"], title=meta["title"],
                           caption=meta["description"],
                           posting_time=dec.publish_at, platform=dec.platform)

        results.append({
            "clip_id": cand.clip_id, "platform": dec.platform,
            "status": pres.status, "scores": cand.scores,
            "edit_command": edit_cmd,
        })
        used_p[dec.platform] = used_p.get(dec.platform, 0) + 1
        used_c[dec.channel] = used_c.get(dec.channel, 0) + 1

    profit = ra.campaign_profit(econ_rows)
    return {
        "generated": len(candidates),
        "selected": len(selected),
        "published": sum(1 for r in results if r.get("status") == "published"),
        "results": results,
        "profit": profit.__dict__,
        "metrics": metrics.snapshot(),
        "distribution": decision,
    }
