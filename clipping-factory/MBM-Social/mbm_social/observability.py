"""
observability -- Production metrics surface (Phase 11).

Aggregates the operational signals the brief requires so they can be exposed via
existing dashboards / the event bus. Pure in-memory counters (no external deps);
snapshot() returns a flat dict ready to emit.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Metrics:
    started_at: float = field(default_factory=time.time)
    clips_generated: int = 0
    minutes_processed: float = 0.0
    generations: int = 0
    generation_latency_sum_s: float = 0.0
    publishes_attempted: int = 0
    publishes_succeeded: int = 0
    failures: int = 0
    retries: int = 0
    cost_usd: float = 0.0
    views: float = 0.0
    revenue_usd: float = 0.0
    queue_depth: int = 0

    # ---- recorders ----
    def record_clip(self, minutes: float = 0.0) -> None:
        self.clips_generated += 1
        self.minutes_processed += minutes

    def record_generation(self, latency_s: float) -> None:
        self.generations += 1
        self.generation_latency_sum_s += latency_s

    def record_publish_attempt(self, success: bool, retries: int = 0) -> None:
        self.publishes_attempted += 1
        if success:
            self.publishes_succeeded += 1
        else:
            self.failures += 1
        self.retries += retries

    def record_cost(self, usd: float) -> None:
        self.cost_usd += usd

    def record_views(self, views: float) -> None:
        self.views += views

    def record_revenue(self, usd: float) -> None:
        self.revenue_usd += usd

    def set_queue_depth(self, depth: int) -> None:
        self.queue_depth = depth

    # ---- derived ----
    def snapshot(self) -> dict:
        elapsed_h = max(1e-9, (time.time() - self.started_at) / 3600.0)
        gen_latency = (self.generation_latency_sum_s / self.generations) if self.generations else 0.0
        attempt = self.publishes_attempted or 1
        return {
            "clips_hour": round(self.clips_generated / elapsed_h, 2),
            "minutes_processed_hour": round(self.minutes_processed / elapsed_h, 2),
            "generation_latency_s": round(gen_latency, 3),
            "publish_throughput_hour": round(self.publishes_succeeded / elapsed_h, 2),
            "queue_depth": self.queue_depth,
            "failure_rate": round(self.failures / attempt, 3),
            "retry_rate": round(self.retries / attempt, 3),
            "cost_per_clip_usd": round(self.cost_usd / self.clips_generated, 4) if self.clips_generated else 0.0,
            "views_per_clip": round(self.views / self.clips_generated, 2) if self.clips_generated else 0.0,
            "revenue_per_clip_usd": round(self.revenue_usd / self.clips_generated, 4) if self.clips_generated else 0.0,
            "roi": round((self.revenue_usd - self.cost_usd) / self.cost_usd, 4) if self.cost_usd else 0.0,
        }
