"""
Hermetic tests for the M-023 Crayo-class engine.

No network, no media, no real publisher. External steps are injected/faked.
"""
from __future__ import annotations

import json
import types
from pathlib import Path

import pytest

from mbm_social import (
    candidate_pool as cp,
    video_editing as ve,
    content_intelligence as ci,
    distribution_optimizer as dist,
    publishing as pub,
    revenue_attribution as ra,
    observability as ob,
    routing_decision as rd,
    learning_feedback as lf,
    crayo_engine as ce,
)


# ───────────────────────── Phase 1: candidate pool ──────────────────────────

def test_pool_sizes_clamped():
    assert cp.POOL_SIZES == (10, 25, 50, 100, 250)
    c = cp.PoolConfig(size=17)
    assert c.size in cp.POOL_SIZES


def test_pool_generates_eight_scores():
    cfg = cp.PoolConfig(size=25, min_overall_score=0.0, min_hook_score=0.0,
                         min_predicted_retention=0.0, publishable_target=25)
    cands = cp.generate_candidates("src1", cfg=cfg)
    assert len(cands) == 25
    for c in cands:
        for k in ("hook_score", "speech_score", "visual_score",
                  "retention_prediction", "platform_fit", "brand_fit",
                  "caption_quality", "overall_score"):
            assert k in c.scores
            assert 0.0 <= c.scores[k] <= 1.0


def test_select_publishable_caps_and_gates():
    cfg = cp.PoolConfig(size=50, min_overall_score=0.9, min_hook_score=0.9,
                         min_predicted_retention=0.9, publishable_target=3)
    cands = cp.generate_candidates("src1", cfg=cfg)
    sel = cp.select_publishable(cands, cfg)
    assert len(sel) <= 3
    for c in sel:
        assert c.scores["overall_score"] >= 0.9


# ───────────────────────── Phase 2: video editing ───────────────────────────

def test_reframe_command_contains_filters():
    cmd = ve.build_reframe_command("in.mp4", "out.mp4", aspect="9:16",
                                   start_ts=1.0, end_ts=9.0)
    assert cmd[0] == "ffmpeg"
    vf = cmd[cmd.index("-vf") + 1]
    assert "crop" in vf and "scale" in vf and "pad" in vf
    assert "-ss" in cmd and "-to" in cmd


def test_reframe_invalid_aspect_raises():
    with pytest.raises(ValueError):
        ve.build_reframe_command("in.mp4", "out.mp4", aspect="3:2")


def test_reframe_region_invalid_falls_back():
    f = ve.choose_reframe_filter(None, "9:16")
    assert "crop" in f
    f2 = ve.choose_reframe_filter(ve.ReframeRegion(2.0, 2.0, 0.5, 0.5), "9:16")
    # invalid region -> still returns a crop (safe fallback)
    assert "crop" in f2


def test_caption_command_has_drawtext():
    cmd = ve.build_caption_command("in.mp4", "out.mp4", "Hello world", platform="tiktok")
    vf = cmd[cmd.index("-vf") + 1]
    assert "drawtext" in vf


def test_platform_render_default_aspect():
    cmd = ve.build_platform_render("in.mp4", "out.mp4", "linkedin")
    vf = cmd[cmd.index("-vf") + 1]
    assert "scale=1920:1080" in vf  # linkedin default 16:9


# ──────────────────── Phase 3: content intelligence ─────────────────────────

def test_content_intelligence_template_fallback(monkeypatch):
    monkeypatch.setattr(ci.mr, "generate", lambda *a, **k: None)
    monkeypatch.setattr(ci.mr, "resolve", lambda *a, **k: None)
    meta = ci.generate_metadata({"transcript_window": "x"}, "dontwatchthis",
                                 "youtube", topic="mystery")
    assert meta["title"] and meta["hook"] and meta["hashtags"]
    assert meta["hook_model"] == "template-fallback"


# ──────────────────── Phase 5: distribution optimizer ───────────────────────

def test_distribution_scales_up_on_good_perf():
    pol = dist.DistributionPolicy()
    rec = dist.recommend(pol, dist.PerformanceSignal(trend="up", avg_quality=0.8))
    assert rec["scale"] > 1.0
    assert rec["target_candidates_per_source"] > pol.target_candidates_per_source


def test_distribution_scales_down_on_bad_perf():
    pol = dist.DistributionPolicy()
    rec = dist.recommend(pol, dist.PerformanceSignal(trend="down", avg_quality=0.3))
    assert rec["scale"] < 1.0


def test_within_daily_caps():
    pol = dist.DistributionPolicy(max_daily_publishes_per_channel=2)
    assert dist.within_daily_caps({}, {"chan": 1}, "youtube", "chan", pol)
    assert not dist.within_daily_caps({}, {"chan": 2}, "youtube", "chan", pol)


# ────────────────────── Phase 6: publishing resilience ──────────────────────

def test_publish_retry_then_success(tmp_path):
    state = {"n": 0}
    def flaky(pkg):
        state["n"] += 1
        if state["n"] < 2:
            raise RuntimeError("boom")
        return {"status": "published", "publish_id": "v1"}
    dlq = tmp_path / "dlq"
    store = pub.IdempotencyStore()
    res = pub.publish_with_resilience({"asset_id": "a1", "target_platform": "youtube", "title": "t"},
                                      flaky, store=store, dlq_dir=dlq, max_retries=3, backoff_base=0.0)
    assert res.status == "published"
    assert state["n"] == 2


def test_publish_idempotent_skip(tmp_path):
    def ok(pkg):
        return {"status": "published", "publish_id": "v1"}
    dlq = tmp_path / "dlq"
    store = pub.IdempotencyStore()
    r1 = pub.publish_with_resilience({"asset_id": "a1", "target_platform": "youtube", "title": "t"},
                                     ok, store=store, dlq_dir=dlq)
    r2 = pub.publish_with_resilience({"asset_id": "a1", "target_platform": "youtube", "title": "t"},
                                     ok, store=store, dlq_dir=dlq)
    assert r1.status == "published" and r2.status == "skipped_idempotent"


def test_publish_duplicate_detected(tmp_path):
    def ok(pkg):
        return {"status": "published", "publish_id": "v1"}
    dlq = tmp_path / "dlq"
    store = pub.IdempotencyStore()
    pkg_a = {"asset_id": "a1", "target_platform": "youtube", "title": "same"}
    pkg_b = {"asset_id": "a2", "target_platform": "youtube", "title": "same"}
    store.record_hash(pkg_a)
    r = pub.publish_with_resilience(pkg_b, ok, store=store, dlq_dir=dlq)
    assert r.status == "skipped_duplicate"


def test_publish_blocked_platform_to_dlq(tmp_path, monkeypatch):
    def ok(pkg):
        return {"status": "published"}
    dlq = tmp_path / "dlq"
    monkeypatch.setattr(pub.pr, "assert_publishable",
                        lambda p: (_ for _ in ()).throw(KeyError(p)))
    store = pub.IdempotencyStore()
    r = pub.publish_with_resilience({"asset_id": "a1", "target_platform": "linkedin", "title": "t"},
                                    ok, store=store, dlq_dir=dlq)
    assert r.status == "blocked"
    assert (dlq).exists() and any(dlq.iterdir())


def test_publish_final_failure_to_dlq(tmp_path):
    def always_fail(pkg):
        raise RuntimeError("dead")
    dlq = tmp_path / "dlq"
    store = pub.IdempotencyStore()
    r = pub.publish_with_resilience({"asset_id": "a1", "target_platform": "youtube", "title": "t"},
                                    always_fail, store=store, dlq_dir=dlq, max_retries=1, backoff_base=0.0)
    assert r.status == "failed"
    assert dlq.exists() and any(dlq.iterdir())


# ────────────────────── Phase 7: revenue attribution ────────────────────────

def test_reward_rate_registry_unverified_default():
    reg = ra.RewardRateRegistry()
    assert reg.rate("youtube").verified is False


def test_estimate_vs_actual_separated():
    reg = ra.RewardRateRegistry()
    reg.set("youtube", 4.0, verified=True, source="YouTube PPP")
    est = ra.estimate_clip("c1", "youtube", views=10000, cost_usd=1.0, registry=reg)
    assert est.is_actual is False
    act = ra.actual_clip("c1", "youtube", views=10000, cost_usd=1.0, revenue_usd=40.0)
    assert act.is_actual is True
    assert act.revenue_per_1k == 4.0
    assert act.profit_usd == 39.0


def test_campaign_profit_estimated_vs_actual():
    reg = ra.RewardRateRegistry()
    reg.set("youtube", 3.0, verified=True)
    rows = [ra.estimate_clip(f"c{i}", "youtube", views=1000, cost_usd=0.1, registry=reg)
            for i in range(3)]
    p = ra.campaign_profit(rows)
    assert p.has_actual is False
    assert p.revenue_per_1k == 3.0
    act_rows = [ra.actual_clip(f"c{i}", "youtube", views=1000, cost_usd=0.1, revenue_usd=5.0)
                for i in range(3)]
    p2 = ra.campaign_profit(act_rows)
    assert p2.has_actual is True
    assert p2.profit_usd == 14.7


# ────────────────────── Phase 11: observability ─────────────────────────────

def test_observability_snapshot():
    m = ob.Metrics()
    m.record_clip(minutes=5)
    m.record_publish_attempt(True, retries=1)
    m.record_cost(0.5)
    m.record_views(1000)
    m.record_revenue(2.0)
    snap = m.snapshot()
    assert snap["cost_per_clip_usd"] == 0.5
    assert snap["views_per_clip"] == 1000.0
    assert snap["retry_rate"] == 1.0


# ────────────────────── Phase 4: routing decision ──────────────────────────

def test_routing_decision_publishes(monkeypatch):
    fake_dest = types.SimpleNamespace(channel="chan1", account_id="acct1")
    monkeypatch.setattr(rd.routing, "resolve_destination", lambda *a, **k: fake_dest)
    cand = cp.Candidate("c1", "src", 0.0, 5.0,
                        {"hook_score": 0.9, "speech_score": 0.8, "visual_score": 0.8,
                         "retention_prediction": 0.9, "platform_fit": 0.8,
                         "brand_fit": 0.8, "caption_quality": 0.8, "overall_score": 0.9},
                        "youtube")
    pol = dist.DistributionPolicy(min_quality_score=0.0, min_hook_score=0.0,
                                  min_predicted_retention=0.0)
    d = rd.decide(cand, "dontwatchthis", pol)
    assert d.should_publish is True
    assert d.channel == "chan1"


def test_routing_decision_blocked_manual(monkeypatch):
    monkeypatch.setattr(rd.pr, "assert_publishable",
                        lambda p: (_ for _ in ()).throw(KeyError(p)))
    cand = cp.Candidate("c1", "src", 0.0, 5.0,
                        {"hook_score": 0.9, "speech_score": 0.8, "visual_score": 0.8,
                         "retention_prediction": 0.9, "platform_fit": 0.8,
                         "brand_fit": 0.8, "caption_quality": 0.8, "overall_score": 0.9},
                        "linkedin")
    pol = dist.DistributionPolicy()
    d = rd.decide(cand, "dontwatchthis", pol)
    assert d.manual is True


# ────────────────────── Phase 8 + E2E: full loop ────────────────────────────

def test_crayo_e2e_publishes_and_learns(tmp_path, monkeypatch):
    monkeypatch.setattr(ci.mr, "generate", lambda *a, **k: None)
    monkeypatch.setattr(ci.mr, "resolve", lambda *a, **k: None)
    # prevent the learning loop from writing to the real LearningMemory.json
    monkeypatch.setattr(lf.le, "record_campaign_result", lambda *a, **k: None)
    monkeypatch.setattr(lf.le, "update_performance_from_analytics", lambda *a, **k: None)
    fake_dest = types.SimpleNamespace(channel="chan1", account_id="acct1")
    monkeypatch.setattr(rd.routing, "resolve_destination", lambda *a, **k: fake_dest)

    def pub_ok(pkg):
        return {"status": "published", "publish_id": "vid_" + pkg["asset_id"]}

    def analytics(clip_id):
        return {"views": 5000, "ctr": 0.05, "watch_time": 800, "subs": 3, "revenue_usd": 15.0}

    cfg = ce.CrayoConfig(
        brand="dontwatchthis", profile="dark_stories", source_id="src_e2e",
        pool=cp.PoolConfig(size=25, min_overall_score=0.0, min_hook_score=0.0,
                           min_predicted_retention=0.0, publishable_target=10),
        policy=dist.DistributionPolicy(min_quality_score=0.0, min_hook_score=0.0,
                                       min_predicted_retention=0.0),
        niche="dark_stories",
    )
    out = ce.run_crayo_loop(cfg, publisher_fn=pub_ok, dlq_dir=tmp_path / "dlq",
                            analytics_fn=analytics)
    assert out["generated"] == 25
    assert out["selected"] > 0
    assert out["published"] > 0
    assert out["profit"]["has_actual"] is True
    assert out["profit"]["actual_revenue_usd"] > 0
    assert out["metrics"]["publish_throughput_hour"] > 0
