"""
content_rewards -- MBM-Social Content Rewards vertical slice (issue #17).

A real, honest implementation of the content-rewards economics pipeline:

    campaign discovery
    -> campaign normalization
    -> eligibility
    -> economic scoring   (ESTIMATED net revenue / production minute)
    -> content selection
    -> clip candidate scoring
    -> render (job descriptor)
    -> QA (fails closed)
    -> account routing    (reuses routing.assert_routing_ok)
    -> submission
    -> verification       (platform-reported views / revenue)
    -> revenue ledger     (estimated | verified | actual kept SEPARATE)
    -> learning           (EWMA priors updated from verified actuals)

PRIMARY RANKING SIGNAL:  expected_net_revenue / production_minute.

HONESTY RULES (never confused):
  estimated_views  - model projection, always labelled with `basis` + confidence.
  verified_views   - platform-reported (analytics), only set by record_verification().
  actual_revenue   - settled money, only set by record_verification().

A ledger row only acquires verified/actual values after a source-supplied
verification call; nothing is invented. No network calls: pure config + math,
fully testable offline.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
REWARDS_DIR = ROOT / "ContentRewards"
LEDGER_PATH = REWARDS_DIR / "ledger.jsonl"
SUBMISSIONS_DIR = REWARDS_DIR / "submissions"
PRIORS_PATH = REWARDS_DIR / "priors.json"
DEFAULT_COST_PER_MINUTE_USD = 0.10  # editorial + render amortized per production minute
DEFAULT_PLATFORM_FEE_RATE = 0.30  # YouTube partner payout share after fee bucket
EWMA_ALPHA = 0.25  # learning rate for RPM priors

from . import routing  # noqa: E402  (reuses fail-closed destination resolution)


class ContentRewardsError(Exception):
    """Raised when a content-rewards invariant is violated (fails closed)."""


# --------------------------------------------------------------------------
# Domain models
# --------------------------------------------------------------------------


@dataclass
class Campaign:
    """A normalized campaign: one candidate clip concept for one brand."""

    id: str
    brand: str
    topic: str
    title: str
    hook: str
    source_url: str
    transcript_snippet: str
    timestamp_accuracy: float  # 0..1 evidence that the hook timestamp is real
    hook_score: float  # 0..1 editorial hook strength
    estimated_duration_s: int
    target_platform: str
    production_minutes: float
    asset_id: str = ""
    renderer: str = "clipping-factory"


@dataclass
class EconomicForecast:
    """Honest economics. estimated != verified != actual."""

    campaign_id: str
    brand: str
    estimated_views: float
    confidence: float  # 0..1
    basis: str  # e.g. "channel_rpm_prior", "n_analytics_none"
    rpm_estimate_usd: float
    expected_gross_revenue_usd: float
    platform_fee_rate: float
    expected_net_revenue_usd: float
    production_minutes: float
    cost_per_minute_usd: float
    production_cost_usd: float
    net_revenue_per_production_minute_usd: float

    def to_ledger_fields(self) -> dict:
        return {
            "estimated_views": round(self.estimated_views, 2),
            "confidence": round(self.confidence, 3),
            "basis": self.basis,
            "rpm_estimate_usd": round(self.rpm_estimate_usd, 4),
            "expected_gross_revenue_usd": round(self.expected_gross_revenue_usd, 2),
            "expected_net_revenue_usd": round(self.expected_net_revenue_usd, 2),
            "production_minutes": round(self.production_minutes, 2),
            "net_revenue_per_production_minute_usd": round(
                self.net_revenue_per_production_minute_usd, 4
            ),
        }


@dataclass
class ClipScore:
    """Quality score of a clip candidate. 0..1 total, weighted components."""

    hook_score: float
    duration_score: float
    captions_score: float
    transcript_evidence_score: float
    aspect_ratio_score: float
    total: float = 0.0

    def __post_init__(self) -> None:
        weights = {
            "hook_score": 0.35,
            "duration_score": 0.20,
            "captions_score": 0.15,
            "transcript_evidence_score": 0.20,
            "aspect_ratio_score": 0.10,
        }
        self.total = round(
            sum(getattr(self, k) * w for k, w in weights.items()), 4
        )


@dataclass
class QaResult:
    passed: bool
    issues: list[str] = field(default_factory=list)


@dataclass
class SubmissionOrder:
    submission_id: str
    campaign_id: str
    asset_id: str
    brand: str
    account_id: str
    platform: str
    channel: str
    status: str  # queued | submitted | verified
    created_iso: str
    verification: dict = field(default_factory=dict)


@dataclass
class LedgerRow:
    row_id: str
    timestamp_iso: str
    submission_id: str
    campaign_id: str
    asset_id: str
    brand: str
    platform: str
    stage: str  # planned | submitted | verified
    estimated_views: float
    confidence: float
    basis: str
    expected_net_revenue_usd: float
    production_minutes: float
    net_revenue_per_production_minute_usd: float
    verified_views: Optional[float] = None
    actual_revenue_usd: Optional[float] = None
    verification_source: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------
# Normalization + discovery
# --------------------------------------------------------------------------


def _norm_topic(value: str) -> str:
    return str(value).strip().lower().replace("_", " ")


def normalize_campaign(raw: dict) -> Campaign:
    """Normalize a raw campaign record. Fails closed on missing identity."""
    brand = str(raw.get("brand") or raw.get("brand_id") or "").strip().lower()
    if not brand:
        raise ContentRewardsError("Campaign missing 'brand'; cannot normalize.")
    topic = _norm_topic(raw.get("topic", ""))
    cid = str(
        raw.get("id")
        or raw.get("campaign_id")
        or uuid.uuid5(uuid.NAMESPACE_DNS, f"{brand}:{topic}")
    )
    return Campaign(
        id=cid,
        brand=brand,
        topic=topic or "general",
        title=str(raw.get("title", "")).strip(),
        hook=str(raw.get("hook", "")).strip(),
        source_url=str(raw.get("source_url", "")).strip(),
        transcript_snippet=str(raw.get("transcript_snippet", "")).strip(),
        timestamp_accuracy=float(raw.get("timestamp_accuracy", 0.0)),
        hook_score=float(raw.get("hook_score", 0.0)),
        estimated_duration_s=int(raw.get("estimated_duration_s", 55)),
        target_platform=str(raw.get("target_platform", "youtube")).lower(),
        production_minutes=float(raw.get("production_minutes", 20.0)),
        asset_id=str(raw.get("asset_id", "")),
        renderer=str(raw.get("renderer", "clipping-factory")),
    )


def _campaign_rules(router: Optional[dict] = None) -> dict[str, dict]:
    """Load per-brand eligibility rules from CampaignRouter.json."""
    if router is None:
        try:
            from .brand_config import load_campaign_router

            router = load_campaign_router()
        except Exception:
            router = {}
    rules = {}
    for rule in router.get("rules", []) or []:
        brand = str(rule.get("brand", "")).strip().lower()
        if brand:
            rules[brand] = rule
    return rules


def discover_campaigns(raw_campaigns: Optional[list[dict]] = None) -> list[Campaign]:
    """
    Discover + normalize campaigns.
    - If raw_campaigns is given, normalize them (explicit discovery).
    - Else derive candidate skeletons from CampaignRouter.json brand rules
      (eligible_topics become one campaign skeleton per topic).
    Never requires a network call.
    """
    if raw_campaigns is not None:
        return [normalize_campaign(c) for c in raw_campaigns]

    campaigns: list[Campaign] = []
    for brand, rule in _campaign_rules().items():
        for topic in rule.get("eligible_topics", []) or []:
            campaigns.append(
                normalize_campaign(
                    {
                        "brand": brand,
                        "topic": topic,
                        "title": f"{topic.title()} short — {brand}",
                        "hook": "",
                        "timestamp_accuracy": 0.0,
                        "hook_score": 0.0,
                        "estimated_duration_s": 55,
                        "target_platform": "youtube",
                        "production_minutes": 20.0,
                    }
                )
            )
    return campaigns


# --------------------------------------------------------------------------
# Eligibility
# --------------------------------------------------------------------------


def campaign_eligible(
    campaign: Campaign,
    channel: Optional[dict] = None,
    rule: Optional[dict] = None,
    brand_active: Optional[bool] = None,
) -> tuple[bool, list[str]]:
    """
    Eligibility gate. Fails closed: any missing/ambiguous condition blocks.
      - brand must be active (if provided)
      - channel must exist and have publish_enabled=true (if provided)
      - topic must be inside the brand's eligible_topics (if rule provided)
      - topic must NOT be in exclude_topics (if rule provided)
      - hook_score >= min_hook_score (if rule provided)
    """
    reasons: list[str] = []

    if brand_active is not None and not brand_active:
        reasons.append(f"brand '{campaign.brand}' not active")

    if channel is not None:
        if not channel.get("publish_enabled", False):
            reasons.append(
                f"channel '{channel.get('account_id', '?')}' publish_enabled=false"
            )
        acct_brand = str(channel.get("brand_id", "")).strip().lower()
        if acct_brand and acct_brand != campaign.brand:
            reasons.append(
                f"channel belongs to '{acct_brand}', not '{campaign.brand}'"
            )

    if rule is not None:
        eligible = [str(t).strip().lower() for t in rule.get("eligible_topics", [])]
        excluded = [str(t).strip().lower() for t in rule.get("exclude_topics", [])]
        if eligible and campaign.topic not in eligible:
            reasons.append(
                f"topic '{campaign.topic}' not in eligible_topics for '{campaign.brand}'"
            )
        if campaign.topic in excluded:
            reasons.append(f"topic '{campaign.topic}' excluded for '{campaign.brand}'")
        min_hook = float(rule.get("min_hook_score", 0.0))
        if campaign.hook_score < min_hook:
            reasons.append(
                f"hook_score {campaign.hook_score:.2f} < min_hook_score {min_hook:.2f}"
            )

    return (not reasons), reasons


# --------------------------------------------------------------------------
# Economic scoring
# --------------------------------------------------------------------------


def _rpm_prior(priors: dict[str, float], brand: str) -> tuple[float, float, str]:
    """Return (rpm, confidence, basis) for a brand, or a neutral default."""
    rpm = priors.get(brand)
    if rpm is not None:
        return float(rpm), 0.8, "channel_rpm_prior"
    return 1.50, 0.20, "rpm_default_low_confidence"


def estimate_forecast(
    campaign: Campaign,
    priors: Optional[dict[str, float]] = None,
    views_provider: Optional[callable] = None,
    cost_per_minute_usd: float = DEFAULT_COST_PER_MINUTE_USD,
    platform_fee_rate: float = DEFAULT_PLATFORM_FEE_RATE,
) -> EconomicForecast:
    """
    Estimate honest economics for a campaign.
    views_provider(campaign) -> (views, confidence, basis) OR None.
    Without a provider, estimated_views defaults to 0 with basis
    'no_views_model' — no invented numbers, so net/min is 0 until a
    real projection exists.
    """
    if views_provider is not None:
        views, conf, basis = views_provider(campaign)
    else:
        views, conf, basis = 0.0, 0.0, "no_views_model"

    rpm, rpm_conf, rpm_basis = _rpm_prior(priors or {}, campaign.brand)
    gross = (float(views) / 1000.0) * rpm
    net = gross * (1.0 - platform_fee_rate)
    minutes = max(campaign.production_minutes, 0.5)
    cost = minutes * cost_per_minute_usd
    per_minute = max(net - cost, 0.0) / minutes

    return EconomicForecast(
        campaign_id=campaign.id,
        brand=campaign.brand,
        estimated_views=float(views),
        confidence=float(conf),
        basis=basis,
        rpm_estimate_usd=rpm,
        expected_gross_revenue_usd=gross,
        platform_fee_rate=platform_fee_rate,
        expected_net_revenue_usd=max(net - cost, 0.0),
        production_minutes=minutes,
        cost_per_minute_usd=cost_per_minute_usd,
        production_cost_usd=cost,
        net_revenue_per_production_minute_usd=per_minute,
    )


# --------------------------------------------------------------------------
# Clip candidate scoring
# --------------------------------------------------------------------------


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def score_clip_candidate(
    campaign: Campaign,
    candidate: Optional[dict] = None,
    *,
    hook_score: Optional[float] = None,
    has_captions: Optional[bool] = None,
    transcript_evidence: Optional[float] = None,
    aspect_ratio: str = "9:16",
) -> ClipScore:
    """Score one clip candidate. Fails safe to 0 components when missing."""
    c = candidate or {}
    hook = hook_score if hook_score is not None else float(c.get("hook_score", campaign.hook_score))
    duration = campaign.estimated_duration_s
    duration_score = 1.0 if 15 <= duration <= 90 else (0.4 if duration <= 180 else 0.1)
    captions = 1.0 if (has_captions if has_captions is not None else bool(c.get("has_captions", False))) else 0.0
    evidence = transcript_evidence if transcript_evidence is not None else float(c.get("transcript_evidence", campaign.timestamp_accuracy))
    aspect = 1.0 if aspect_ratio in ("9:16", "1:1") else 0.3
    return ClipScore(
        hook_score=_clip(hook),
        duration_score=_clip(duration_score),
        captions_score=_clip(captions),
        transcript_evidence_score=_clip(evidence),
        aspect_ratio_score=_clip(aspect),
    )


def qa_candidate(campaign: Campaign, clip: ClipScore) -> QaResult:
    """QA gate. Fails closed when required evidence is missing."""
    issues: list[str] = []
    if clip.total < 0.5:
        issues.append(f"clip score {clip.total:.2f} < 0.50 gate")
    if not campaign.hook:
        issues.append("campaign has no hook text")
    if not campaign.transcript_snippet:
        issues.append("campaign has no transcript evidence")
    if campaign.timestamp_accuracy <= 0.0:
        issues.append("timestamp_accuracy is 0 — cannot prove the hook moment")
    if not (15 <= campaign.estimated_duration_s <= 90):
        issues.append(f"duration {campaign.estimated_duration_s}s outside short-form bounds")
    return QaResult(passed=not issues, issues=issues)


# --------------------------------------------------------------------------
# Routing + submission
# --------------------------------------------------------------------------


def route_campaign(campaign: Campaign) -> routing.RoutingDestination:
    """Resolve the canonical destination. Reuses routing (fails closed)."""
    package = {
        "brand": campaign.brand,
        "target_platform": campaign.target_platform,
        "asset_id": campaign.asset_id or campaign.id,
    }
    return routing.assert_routing_ok(package)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RevenueLedger:
    """Append-only JSON-lines ledger. Estimated/verified/actual never mixed."""

    def __init__(self, path: Path = LEDGER_PATH) -> None:
        self.path = path

    def _load(self) -> list[dict]:
        if not self.path.exists():
            return []
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows

    def append(self, row: LedgerRow) -> None:
        rows = self._load()
        rows.append(row.as_dict())
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8",
        )

    def find(self, submission_id: str) -> Optional[dict]:
        for r in self._load():
            if r["submission_id"] == submission_id:
                return r
        return None

    def update(self, row: dict) -> None:
        rows = self._load()
        for i, r in enumerate(rows):
            if r["row_id"] == row["row_id"]:
                rows[i] = row
                break
        else:
            raise ContentRewardsError(f"row {row['row_id']} not in ledger")
        self.path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8",
        )

    def summary(self) -> dict:
        rows = self._load()
        planned = [r for r in rows if r["stage"] == "planned"]
        submitted = [r for r in rows if r["stage"] == "submitted"]
        verified = [r for r in rows if r["stage"] == "verified"]
        return {
            "rows": len(rows),
            "planned": len(planned),
            "submitted": len(submitted),
            "verified": len(verified),
            "sum_estimated_views": round(sum(r["estimated_views"] for r in rows), 2),
            "sum_expected_net_revenue_usd": round(
                sum(r["expected_net_revenue_usd"] for r in rows), 2
            ),
            "sum_verified_views": round(
                sum((r["verified_views"] or 0.0) for r in verified), 2
            ),
            "sum_actual_revenue_usd": round(
                sum((r["actual_revenue_usd"] or 0.0) for r in verified), 2
            ),
        }

    def to_csv(self, path: Path) -> None:
        rows = self._load()
        if not rows:
            path.write_text("", encoding="utf-8")
            return
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)


def _ledger_row(
    campaign: Campaign,
    forecast: EconomicForecast,
    submission_id: str,
    stage: str,
) -> LedgerRow:
    return LedgerRow(
        row_id=str(uuid.uuid4()),
        timestamp_iso=_iso_now(),
        submission_id=submission_id,
        campaign_id=campaign.id,
        asset_id=campaign.asset_id or campaign.id,
        brand=campaign.brand,
        platform=campaign.target_platform,
        stage=stage,
        estimated_views=forecast.estimated_views,
        confidence=forecast.confidence,
        basis=forecast.basis,
        expected_net_revenue_usd=forecast.expected_net_revenue_usd,
        production_minutes=forecast.production_minutes,
        net_revenue_per_production_minute_usd=forecast.net_revenue_per_production_minute_usd,
    )


def submit(
    campaign: Campaign,
    forecast: EconomicForecast,
    ledger: Optional[RevenueLedger] = None,
    submissions_dir: Path = SUBMISSIONS_DIR,
) -> SubmissionOrder:
    """
    Route, write a submission order, and append a 'planned' ledger row.
    Fails closed: routing must resolve BEFORE anything is recorded.
    """
    dest = route_campaign(campaign)
    order = SubmissionOrder(
        submission_id=f"CR-{uuid.uuid4().hex[:12]}",
        campaign_id=campaign.id,
        asset_id=campaign.asset_id or campaign.id,
        brand=campaign.brand,
        account_id=dest.account_id,
        platform=dest.platform,
        channel=dest.channel,
        status="queued",
        created_iso=_iso_now(),
    )
    ledger = ledger or RevenueLedger()
    submissions_dir.mkdir(parents=True, exist_ok=True)
    (submissions_dir / f"{order.submission_id}.json").write_text(
        json.dumps(asdict(order), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    ledger.append(_ledger_row(campaign, forecast, order.submission_id, "planned"))
    return order


def record_verification(
    ledger: RevenueLedger,
    submission_id: str,
    verified_views: float,
    actual_revenue_usd: float,
    source: str,
) -> LedgerRow:
    """
    Mark a submission verified with PLATFORM-REPORTED numbers only.
    Raises if the source is empty (prevents fabricated verification).
    """
    if not source or not source.strip():
        raise ContentRewardsError("verification requires a non-empty source")
    row = ledger.find(submission_id)
    if row is None:
        raise ContentRewardsError(f"no ledger row for submission '{submission_id}'")
    row["stage"] = "verified"
    row["verified_views"] = float(verified_views)
    row["actual_revenue_usd"] = float(actual_revenue_usd)
    row["verification_source"] = source.strip()
    row["timestamp_iso"] = _iso_now()
    ledger.update(row)
    return LedgerRow(**row)


# --------------------------------------------------------------------------
# Learning (EWMA priors from verified actuals)
# --------------------------------------------------------------------------


def update_rpm_priors(
    priors: dict[str, float],
    ledger: RevenueLedger,
    alpha: float = EWMA_ALPHA,
) -> dict[str, float]:
    """Update brand RPM priors from verified rows (actual revenue / 1000 views)."""
    out = dict(priors)
    for r in ledger._load():
        if r["stage"] != "verified" or not r["verified_views"]:
            continue
        views = float(r["verified_views"])
        if views <= 0:
            continue
        rpm = (float(r["actual_revenue_usd"] or 0.0) / views) * 1000.0
        brand = r["brand"]
        out[brand] = round(alpha * rpm + (1 - alpha) * out.get(brand, rpm), 4)
    return out


def save_priors(priors: dict[str, float], path: Path = PRIORS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"updated_iso": _iso_now(), "rpm_usd_per_1000_views": priors},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_priors(path: Path = PRIORS_PATH) -> dict[str, float]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: float(v) for k, v in data.get("rpm_usd_per_1000_views", {}).items()}


# --------------------------------------------------------------------------
# Planning (primary ranking signal)
# --------------------------------------------------------------------------


def plan_campaigns(
    campaigns: list[Campaign],
    priors: Optional[dict[str, float]] = None,
    views_provider: Optional[callable] = None,
) -> list[tuple[Campaign, EconomicForecast]]:
    """Score every campaign and sort by net_revenue_per_production_minute desc."""
    scored = [
        (c, estimate_forecast(c, priors=priors or {}, views_provider=views_provider))
        for c in campaigns
    ]
    scored.sort(key=lambda t: t[1].net_revenue_per_production_minute_usd, reverse=True)
    return scored


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="MBM-Social Content Rewards")
    sub = parser.add_subparsers(dest="command", required=True)

    p_discover = sub.add_parser("discover", help="discover + normalize campaigns")
    p_discover.add_argument("--rules", action="store_true", help="derive from CampaignRouter.json")

    sub.add_parser("plan", help="rank campaigns by net revenue / production minute")
    sub.add_parser("ledger", help="print ledger summary")
    sub.add_parser("export-csv", help="write ContentRewards/ledger.csv")

    p_score = sub.add_parser("score", help="score + QA one candidate (JSON on stdin)")
    p_verify = sub.add_parser("verify", help="verify a submission (JSON on stdin)")

    args = parser.parse_args(argv)

    if args.command == "discover":
        campaigns = discover_campaigns([] if not args.rules else None)
        for c in campaigns:
            print(json.dumps(asdict(c), ensure_ascii=False, sort_keys=True))
        return 0

    if args.command == "plan":
        priors = load_priors()
        campaigns = discover_campaigns()
        if not campaigns:
            print("No campaigns discovered (CampaignRouter.json rules missing or empty).")
            return 1
        ranked = plan_campaigns(campaigns, priors=priors)
        print(f"{'BRAND':20s} {'TOPIC':22s} {'EXP_VIEWS':>10s} {'NET$/MIN':>10s} {'CONF':>6s} {'BASIS':26s}")
        for c, f in ranked:
            print(f"{c.brand:20s} {c.topic:22s} {f.estimated_views:>10.0f} {f.net_revenue_per_production_minute_usd:>10.4f} {f.confidence:>6.2f} {f.basis:26s}")
        return 0

    if args.command == "ledger":
        s = RevenueLedger().summary()
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0

    if args.command == "export-csv":
        out = REWARDS_DIR / "ledger.csv"
        RevenueLedger().to_csv(out)
        print(f"wrote {out}")
        return 0

    if args.command == "score":
        raw = json.loads(sys.stdin.read())
        campaign = normalize_campaign(raw.get("campaign", raw))
        clip = score_clip_candidate(campaign, raw.get("candidate", {}))
        qa = qa_candidate(campaign, clip)
        print(json.dumps(
            {"clip_score": asdict(clip), "qa": asdict(qa)},
            ensure_ascii=False, indent=2,
        ))
        return 0 if qa.passed else 1

    if args.command == "verify":
        raw = json.loads(sys.stdin.read())
        ledger = RevenueLedger()
        row = record_verification(
            ledger,
            raw["submission_id"],
            float(raw["verified_views"]),
            float(raw.get("actual_revenue_usd", 0.0)),
            source=str(raw.get("source", "")),
        )
        print(json.dumps(row.as_dict(), ensure_ascii=False, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())