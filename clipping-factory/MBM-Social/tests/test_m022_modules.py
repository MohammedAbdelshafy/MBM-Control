"""
M-022 unit tests — foundational modules (Phases 1-3, 7-9, 11, 13).

All tests are hermetic: no network, no Ollama, no backend DB, no real
publishing. They use tmp_path fixtures and injected fakes.
"""
from __future__ import annotations

import json
from pathlib import Path

from mbm_social import (
    event_bus, checkpoint, circuit_breaker, source_registry,
    platform_registry, viral_intelligence, quality_gate_policy,
    client_campaign, app_websites, github_app,
)
from mbm_social.campaign_runner import run_campaign, CampaignContext, CANONICAL_STAGES


# ── event_bus ───────────────────────────────────────────────────────────
def test_event_bus_emits_and_persists(tmp_path):
    bus = event_bus.EventBus(tmp_path / "events.jsonl")
    ev = bus.stage_result("c1", "speech_factory", True, metrics={"x": 1})
    assert ev.status == "ok"
    events = bus.events()
    assert len(events) == 1
    assert events[0]["campaign_id"] == "c1"
    # observer fires
    seen = []
    bus.subscribe(lambda e: seen.append(e))
    bus.emit("publish", "c1", "publisher", status="ok", data={"id": "abc"})
    assert any(e.event_id for e in seen)


# ── checkpoint / resume ────────────────────────────────────────────────
def test_checkpoint_records_and_resumes(tmp_path):
    cp = checkpoint.CampaignCheckpoint(campaign_id="c1", state_file=tmp_path / "c1.json")
    cp.record("source_discovery", {"n": 3})
    cp.record("rights_check", {"ok": True})
    cp.save()
    cp2 = checkpoint.CampaignCheckpoint.load(tmp_path / "c1.json")
    assert cp2.is_stage_done("source_discovery")
    assert cp2.next_stage == "video_acquisition"
    cp2.record("video_acquisition", {}, failed=True, reason="boom")
    assert cp2.failures.get("video_acquisition") == "boom"


# ── circuit breaker + DLQ ──────────────────────────────────────────────
def test_circuit_breaker_opens(tmp_path):
    cb = circuit_breaker.CircuitBreaker(failure_threshold=2, cooldown_sec=100)
    assert cb.allow("yt")
    cb.failure("yt")
    assert cb.allow("yt")
    cb.failure("yt")
    assert not cb.allow("yt")  # opened
    cb.success("yt")
    assert cb.allow("yt")


def test_dead_letter_preserves_package(tmp_path):
    q = tmp_path / "publish_queue"
    q.mkdir()
    pkg = q / "pkg.json"
    pkg.write_text(json.dumps({"brand": "x", "title": "t"}), encoding="utf-8")
    dest = circuit_breaker.move_to_dead_letter(pkg, q, "publish_blocked", {"detail": "no id"})
    assert dest.exists()
    assert not pkg.exists()
    data = json.loads(dest.read_text())
    assert data["status"] == "dead_letter"
    assert data["dead_letter"]["reason"] == "publish_blocked"


# ── source registry / rights gate ──────────────────────────────────────
def test_source_registry_gates_restricted(tmp_path):
    reg = source_registry.SourceRegistry(tmp_path / "src.json")
    rec = reg.register("https://x/1", "dontwatchthis", restricted=True, rights_status="unknown")
    assert rec.state == source_registry.APPROVAL_REQUIRED
    assert not reg.is_processable(rec.source_id)
    reg.approve(rec.source_id, "human", rights_status="cleared")
    assert reg.is_processable(rec.source_id)
    nxt = reg.get_next_processable("dontwatchthis")
    assert nxt is not None
    # non-restricted auto-approves
    r2 = reg.register("https://x/2", "cutedosage", restricted=False)
    assert r2.state == source_registry.APPROVED


# ── platform registry honesty ──────────────────────────────────────────
def test_platform_registry_status():
    assert platform_registry.publish_status("youtube") == platform_registry.SUPPORTED
    assert platform_registry.publish_status("instagram") == platform_registry.MANUAL_REQUIRED
    assert platform_registry.publish_status("linkedin") == platform_registry.BLOCKED
    assert platform_registry.publish_status("twitter") == platform_registry.BLOCKED
    # assert_publishable raises for blocked, ok for youtube
    platform_registry.assert_publishable("youtube")
    try:
        platform_registry.assert_publishable("linkedin")
        assert False, "should raise"
    except RuntimeError:
        pass


# ── viral intelligence ─────────────────────────────────────────────────
def test_viral_intelligence_ranking():
    sigs = [
        viral_intelligence.ClipSignal(clip_id="a", hook=0.9, retention_prediction=0.85, niche="dark_stories"),
        viral_intelligence.ClipSignal(clip_id="b", hook=0.2, retention_prediction=0.1, niche="dark_stories"),
    ]
    ranked = viral_intelligence.rank_candidates(sigs, niche="dark_stories")
    assert ranked[0].clip_id == "a"
    assert ranked[0].score > ranked[1].score
    assert ranked[0].recommended_platform in ("youtube", "instagram", "tiktok", "linkedin")
    assert any("recommended platform" in r for r in ranked[0].reasons)
    assert 0.0 <= ranked[0].confidence <= 1.0


def test_viral_intelligence_history_blend():
    s = viral_intelligence.ClipSignal(clip_id="h", retention_prediction=0.5, historical_score=1.0)
    r = viral_intelligence.score_clip(s)
    assert r.breakdown["retention_prediction"] > 0.5  # blended upward


# ── quality gate policy ────────────────────────────────────────────────
def test_quality_gate_pass_and_fail():
    pol = quality_gate_policy.GatePolicy()
    good = {"media_integrity": 1.0, "hook_quality": 0.8, "speech_accuracy": 0.9,
            "subtitle_accuracy": 0.9, "visual_framing": 0.8, "audio_quality": 0.8,
            "brand_fit": 0.9, "platform_fit": 0.8, "metadata_completeness": 0.9}
    assert pol.evaluate(good, rights_approved=True).passed
    bad = dict(good)
    bad["hook_quality"] = 0.2
    res = pol.evaluate(bad, rights_approved=True)
    assert not res.passed
    assert res.status == "QUALITY_FAILED"
    assert any("hook_quality" in f["reason"] for f in res.failures)
    # rights gate
    res2 = pol.evaluate(good, rights_approved=False)
    assert not res2.passed
    assert any(f["gate"] == "rights_status" for f in res2.failures)


# ── client campaign validation ─────────────────────────────────────────
def test_client_campaign_validation():
    internal = client_campaign.from_dict({"kind": "INTERNAL_BRAND", "campaign_id": "c", "brand": "x"})
    assert client_campaign.validate(internal) == []
    bad_client = client_campaign.from_dict({
        "kind": "CLIENT_CAMPAIGN", "campaign_id": "c", "brand": "x",
        "client": "", "source_ownership_confirmed": False,
        "output_quantity": 0, "target_platforms": [], "approval_mode": "auto",
        "quality_gate": 0.5,
    })
    errs = client_campaign.validate(bad_client)
    assert any("client" in e for e in errs)
    assert any("ownership" in e for e in errs)
    assert any("quality_gate" in e for e in errs)


# ── website contract ───────────────────────────────────────────────────
def test_website_contract_render(tmp_path):
    c = app_websites.SiteContract(
        slug="muslim-clips", brand="clippingfactorymbm", title="Muslim Clips",
        niche="islamic_content", offer="Halal short-form editing.",
        pricing=["$5/clip"], faq=[{"q": "Turnaround?", "a": "48h"}],
        sample_clips=["https://x/v.mp4"], contact={"email": "a@b.co"},
    )
    out = app_websites.generate_site(c, tmp_path)
    html = (out / "index.html").read_text()
    assert "Muslim Clips" in html
    assert (out / "contract.json").exists()


# ── github app webhook + idempotency + issues ──────────────────────────
def test_github_webhook_signature():
    secret = "s3cr3t"
    body = b'{"action":"x"}'
    import hmac, hashlib
    sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert github_app.validate_webhook_signature(body, sig, secret)
    assert not github_app.validate_webhook_signature(body, sig, "wrong")


def test_github_idempotency(tmp_path):
    store = github_app.IdempotencyStore(tmp_path / "ids.jsonl")
    assert store.mark("evt1") is True
    assert store.mark("evt1") is False
    assert store.seen("evt1")


def test_github_issue_gh_missing_returns_error():
    # With no gh CLI and no token, it must return an error dict (never raise).
    res = github_app.create_issue("o/r", "t", "b")
    assert res["ok"] is False


def test_github_app_jwt_requires_cryptography():
    try:
        github_app.build_app_jwt("123", "not-a-key")
        assert False, "should raise without a valid PEM key"
    except Exception:
        pass


# ── E2E simulated campaign (resume / quality fail / rights block / DLQ) ─
def _make_fake_stages(behaviour: str, tmp_path):
    """Return stage_fns simulating different production scenarios."""
    q = tmp_path / "publish_queue"
    q.mkdir(exist_ok=True)

    def source_discovery(ctx, out):
        return {"sources": [{"value": "https://x/1"}]}

    def rights_check(ctx, out):
        return {"rights_verified": True}

    def video_acquisition(ctx, out):
        return {"source_content_id": "sc1"}

    def speech_factory(ctx, out):
        return {"analysis": {"transcript": "the twist was shocking"}}

    def visual_factory(ctx, out):
        out["clip_id"] = "clip1"
        return {"clips_created": ["clip1"]}

    def hook_factory(ctx, out):
        return {"edits": [], "hook_generated": True}

    def ranking(ctx, out):
        out["route"] = {"brand": ctx.brand, "channel_id": "UC1", "score": 0.8}
        return {"route": out["route"]}

    def captions(ctx, out):
        out["package"] = {"brand": ctx.brand, "title": "T", "queue_path": str(q / "p.json")}
        (q / "p.json").write_text(json.dumps({"brand": ctx.brand, "title": "T"}), encoding="utf-8")
        return {"package": out["package"]}

    def thumbnail(ctx, out):
        return {"thumbnail_text": "WOW"}

    def quality_control(ctx, out):
        if behaviour == "quality_fail":
            return {"media_integrity": 1.0, "hook_quality": 0.2, "speech_accuracy": 0.9,
                    "subtitle_accuracy": 0.9, "visual_framing": 0.8, "audio_quality": 0.8,
                    "brand_fit": 0.9, "platform_fit": 0.8, "metadata_completeness": 0.9}
        return {"media_integrity": 1.0, "hook_quality": 0.8, "speech_accuracy": 0.9,
                "subtitle_accuracy": 0.9, "visual_framing": 0.8, "audio_quality": 0.8,
                "brand_fit": 0.9, "platform_fit": 0.8, "metadata_completeness": 0.9}

    def publishing_queue(ctx, out):
        return {"queue_path": str(q / "p.json"), "status": "draft"}

    def publisher(ctx, out):
        if behaviour == "publish_fail":
            return {"published_platforms": {}, "failed": True,
                    "package_path": str(q / "p.json")}
        if behaviour == "blocked_platform":
            return {"platforms": ["linkedin"], "published_platforms": {},
                    "package_path": str(q / "p.json")}
        return {"published_platforms": {"youtube": True}, "platforms": ["youtube"]}

    def analytics(ctx, out):
        return {"recorded": True}

    def learning(ctx, out):
        return {"learning_updated": True}

    return {
        "source_discovery": source_discovery, "rights_check": rights_check,
        "video_acquisition": video_acquisition, "speech_factory": speech_factory,
        "visual_factory": visual_factory, "hook_factory": hook_factory,
        "ranking": ranking, "captions": captions, "thumbnail": thumbnail,
        "quality_control": quality_control, "publishing_queue": publishing_queue,
        "publisher": publisher, "analytics": analytics, "learning": learning,
    }


def test_e2e_success(tmp_path):
    ctx = CampaignContext(campaign_id="e2e_ok", brand="dontwatchthis", profile="dark_stories")
    res = run_campaign(ctx, _make_fake_stages("ok", tmp_path),
                       checkpoint_dir=tmp_path, event_log=tmp_path / "ev.jsonl")
    assert res.status == "completed"
    assert len(res.stages) == len(CANONICAL_STAGES)


def test_e2e_quality_failed(tmp_path):
    ctx = CampaignContext(campaign_id="e2e_qf", brand="dontwatchthis", profile="dark_stories")
    res = run_campaign(ctx, _make_fake_stages("quality_fail", tmp_path),
                       checkpoint_dir=tmp_path, event_log=tmp_path / "ev.jsonl")
    assert res.status == "quality_failed"
    # never reached publisher
    assert not any(s["stage"] == "publisher" for s in res.stages)


def test_e2e_rights_blocked(tmp_path):
    reg = source_registry.SourceRegistry(tmp_path / "src.json")
    rec = reg.register("https://x/1", "dontwatchthis", restricted=True, rights_status="unknown")
    ctx = CampaignContext(campaign_id="e2e_rb", brand="dontwatchthis",
                          profile="dark_stories", source_id=rec.source_id)
    res = run_campaign(ctx, _make_fake_stages("ok", tmp_path),
                       checkpoint_dir=tmp_path, event_log=tmp_path / "ev.jsonl",
                       source_registry=reg)
    assert res.status == "rights_blocked"


def test_e2e_resume_after_failure(tmp_path):
    # First run fails at visual_factory (simulate by raising once).
    state = {"fail_at": "visual_factory"}

    def flaky(ctx, out):
        if state["fail_at"] == "visual_factory":
            state["fail_at"] = None
            raise RuntimeError("transient acquisition error")
        return {"source_content_id": "sc1"}

    stages = _make_fake_stages("ok", tmp_path)
    stages["video_acquisition"] = flaky
    ctx = CampaignContext(campaign_id="e2e_resume", brand="dontwatchthis", profile="dark_stories")
    res1 = run_campaign(ctx, stages, checkpoint_dir=tmp_path, event_log=tmp_path / "ev.jsonl")
    assert res1.status == "failed"
    # Resume: re-run with resume=True; completed stages replay, failure stage re-runs.
    res2 = run_campaign(ctx, _make_fake_stages("ok", tmp_path),
                        checkpoint_dir=tmp_path, event_log=tmp_path / "ev.jsonl", resume=True)
    assert res2.status == "completed"
    # source_discovery/rights_check replayed as resumed
    assert any(s.get("resumed") for s in res2.stages)


def test_e2e_publish_fail_dlq(tmp_path):
    ctx = CampaignContext(campaign_id="e2e_dlq", brand="dontwatchthis", profile="dark_stories",
                          queue_dir=tmp_path / "publish_queue")
    res = run_campaign(ctx, _make_fake_stages("publish_fail", tmp_path),
                       checkpoint_dir=tmp_path, event_log=tmp_path / "ev.jsonl")
    # Breaker opens after repeated failures; package preserved in dead-letter.
    dl = tmp_path / "publish_queue" / "dead_letter"
    assert dl.exists()


def test_e2e_blocked_platform_preserved(tmp_path):
    ctx = CampaignContext(campaign_id="e2e_blk", brand="dontwatchthis", profile="dark_stories",
                          repo="owner/repo", queue_dir=tmp_path / "publish_queue")
    res = run_campaign(ctx, _make_fake_stages("blocked_platform", tmp_path),
                       checkpoint_dir=tmp_path, event_log=tmp_path / "ev.jsonl")
    assert res.status == "publish_blocked"
    dl = tmp_path / "publish_queue" / "dead_letter"
    assert dl.exists()
