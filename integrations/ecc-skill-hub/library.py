#!/usr/bin/env python3
"""library.py — the curated ECC cherry-pick catalog.

Nine skills from affaan-m/ECC (pinned commit PROVENANCE.txt) were reviewed
and vendored under ./picks/. This module is the machine-readable catalog:
what each pick is, which founder product it serves, what it needs, and the
reviewer's safety verdict.

"vetted" verdicts (from the 2026-10-10 audit):
  SAFE        — single prompt SKILL.md, no scripts, no remote-code patterns
  SAFE-DOCS   — prompt SKILL.md whose text *warns against* pipe-to-shell
                (the warning text matched the scanner: false positive, good sign)
  CONFIG-SLOT — safe prompt, but real activation needs a credential/config
                listed in `needs`; nothing in the vendored copy works without it
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
PICKS_DIR = HERE / "picks"

SOURCE_REPO = "https://github.com/affaan-m/ECC"
PINNED_COMMIT = "5cc14d7c3155c7dcd4059c94b89df4b6303b7cd6"


@dataclass
class Pick:
    slug: str
    product: str               # founder product this serves
    role: str                  # one-line "rebrand" role
    why: str                   # why it was cherry-picked
    needs: list[str] = field(default_factory=list)   # config slots, else []
    verdict: str = "SAFE"
    note: str = ""

    @property
    def path(self) -> Path:
        return PICKS_DIR / self.slug

    def read_skill(self) -> str:
        return (self.path / "SKILL.md").read_text(encoding="utf-8")

    def has_skill(self) -> bool:
        return (self.path / "SKILL.md").is_file()


PICKS: list[Pick] = [
    Pick("lead-intelligence",
         product="Wholesaler Lead Engine / outreach pipe",
         role="Agent-powered lead intel (Apollo/Clay replacement)",
         why="Signal scoring, mutual ranking, warm-path discovery and "
             "channel-specific outreach drafts map directly onto the "
             "wholesaler lead engine's seller-finding work.",
         needs=["WebSearch/WebFetch-capable agent runtime"],
         verdict="SAFE",
         note="Bundled sub-agents: enrichment-agent, mutual-mapper, "
              "outreach-drafter, signal-scorer."),
    Pick("cost-aware-llm-pipeline",
         product="MBM-Control (GLM workforce)",
         role="LLM spend router — margin guard",
         why="Model routing by task complexity, budget tracking, retry "
             "logic, prompt caching: the exact patterns the GLM swarm "
             "needs to stop burning paid credits on draft work.",
         needs=[],
         verdict="SAFE"),
    Pick("agent-eval",
         product="MBM-Control (GLM workforce)",
         role="Head-to-head agent shootouts",
         why="Pass rate / cost / time / consistency comparisons for "
             "choosing between coding agents — extends the bench-verdict "
             "work already done (2026-10-07) with a reusable harness.",
         needs=[],
         verdict="SAFE"),
    Pick("benchmark-optimization-loop",
         product="MBM-Control (GLM workforce)",
         role="Measured 'make it faster' loop",
         why="Baseline → one-hypothesis variants → correctness gate → "
             "promote fastest: disciplined optimization for swarm runners "
             "instead of vibes.",
         needs=[],
         verdict="SAFE"),
    Pick("eval-harness",
         product="MBM-Control (GLM workforce)",
         role="Eval-driven agent development",
         why="Define capability/regression evals before coding, grade with "
             "code/model/rule/human graders — the missing reliability layer "
             "for overnight swarm builds.",
         needs=[],
         verdict="SAFE"),
    Pick("agent-architecture-audit",
         product="MBM-Control (GLM workforce)",
         role="12-layer agent-stack diagnostic",
         why="Severity-ranked findings with code-first fixes for wrapper "
             "regression, memory pollution, tool-discipline failures and "
             "hidden repair loops. Diagnostic skill for every agent app.",
         needs=[],
         verdict="SAFE"),
    Pick("marketing-campaign",
         product="DataClean AI / AI Consultancy Sprint",
         role="Launch-campaign orchestration",
         why="Audience research, positioning, landing copy, email "
             "sequences, social posts, ad copy, short-form video scripts, "
             "content calendars — the execution layer behind the $499 "
             "DataClean and $297 AI Sprint pitches.",
         needs=[],
         verdict="SAFE"),
    Pick("social-publisher",
         product="outreach pipe",
         role="Agent-driven multi-platform publishing",
         why="Scheduling/publishing across 13 platforms through one "
             "workspace API — the automation half of the warm-outreach "
             "pipeline (publishing is automated; outreach itself stays "
             "manual per the founder's social guardrails).",
         needs=["SC_API_KEY (SocialClaw workspace API key, getsocialclaw.com)"],
         verdict="CONFIG-SLOT",
         note="Requires third-party SocialClaw account; the optional "
              "xquik/tweetclaw npm package is pinned (@1.6.31) but was "
              "NOT vendored — install it yourself only if your dependency "
              "policy allows it."),
    Pick("data-scraper-agent",
         product="Wholesaler Lead Engine",
         role="Scheduled public-data collector",
         why="Build a fully automated collector for any public source "
             "(job boards, prices, news, GitHub), AI-enriched, stored to "
             "Notion/Sheets/Supabase — seller-intel feed for the lead "
             "engine.",
         needs=["GEMINI_API_KEY (Gemini Flash free tier — founder has the "
                "gemini connector live)",
                "storage sink: Notion API or Google Sheets or Supabase"],
         verdict="CONFIG-SLOT"),
]


def get(slug: str) -> Pick:
    for p in PICKS:
        if p.slug == slug:
            return p
    raise KeyError(f"unknown pick: {slug}")


def slugs() -> list[str]:
    return [p.slug for p in PICKS]


def search(query: str) -> list[Pick]:
    q = query.lower()
    return [p for p in PICKS
            if q in p.slug or q in p.role.lower() or q in p.why.lower()
            or q in p.product.lower()]
