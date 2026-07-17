"""Knowledge layer: duplicate detection, trend detection, creator profiles,
weekly reports. Operates on the SQLite databases populated by the analysis stage.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from .db import DB
from .schema import Reel


class KnowledgeLayer:
    def __init__(self, db: DB, log: Callable[[str], None] = print):
        self.db = db
        self.log = log

    # --- duplicate detection ------------------------------------------
    def detect_duplicates(self, reels: list[Reel]) -> list[tuple[str, str]]:
        """Find reels teaching the same point (by normalized hook/offer text)."""
        buckets: dict[str, list[str]] = {}
        pairs: list[tuple[str, str]] = []
        for r in reels:
            key = self._teach_key(r)
            if not key:
                continue
            for other in buckets.get(key, []):
                pairs.append((other, r.reel_id))
            buckets.setdefault(key, []).append(r.reel_id)
        if pairs:
            self.log(f"[knowledge] {len(pairs)} duplicate/related pairs found")
        return pairs

    @staticmethod
    def _teach_key(r: Reel) -> str:
        base = (r.primary_hook or r.offer or "").lower()
        # collapse to first 6 significant words
        words = [w for w in base.split() if len(w) > 3][:6]
        return " ".join(words)

    # --- trend detection ----------------------------------------------
    def trends(self) -> dict:
        hooks = self.db.top_hooks(20)
        niches = self.db.top_niches(20)
        return {
            "top_hook_types": [dict(h) for h in hooks],
            "top_niches": [dict(n) for n in niches],
        }

    # --- creator profiles ---------------------------------------------
    def build_creator_profiles(self, reels: list[Reel]):
        by_creator: dict[str, list[Reel]] = {}
        for r in reels:
            by_creator.setdefault(r.creator or "unknown", []).append(r)
        for handle, rs in by_creator.items():
            avg_hook = sum(r.hook_score for r in rs if r.hook_score) / max(len(rs), 1)
            self.db.upsert_creator(
                handle,
                avg_hook=round(avg_hook, 1),
                business_model=Counter(r.business_model for r in rs).most_common(1)[0][0]
                if rs else "",
                top_topics="; ".join(sorted({r.niche for r in rs if r.niche})[:5]),
            )

    # --- weekly report ------------------------------------------------
    def weekly_report(self, out_dir: Path) -> Path:
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        hooks = self.db.top_hooks(20)
        niches = self.db.top_niches(20)
        top = self.db.top_reels_by_mbm(20)
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lines = [f"# MBM Instagram Intelligence — Weekly Report ({date})", ""]
        lines.append("## Top 20 Hooks")
        for h in hooks:
            lines.append(f"- {h['hook_type']}: {h['c']}")
        lines.append("\n## Top 20 Niches")
        for n in niches:
            lines.append(f"- {n['niche']}: {n['c']}")
        lines.append("\n## Top 20 by MBM Relevance")
        for r in top:
            lines.append(f"- [{r['mbm_relevance_score']}] {r['title']} — {r['creator']}")
        report = out_dir / f"weekly_{date}.md"
        report.write_text("\n".join(lines), encoding="utf-8")
        self.log(f"[knowledge] weekly report -> {report}")
        return report
