"""Database access layer for the MBM Instagram Intelligence system.

Opens/creates the seven SQLite databases and provides insert/update helpers
used by the analysis and knowledge layers.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterable

import sqlite3

from .schema import DB_SCHEMA, MBM_SCORE_KEYS, Reel, _now


class DB:
    def __init__(self, db_dir: Path):
        self.db_dir = Path(db_dir)
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self._conns: dict[str, sqlite3.Connection] = {}
        for name in DB_SCHEMA:
            conn = sqlite3.connect(self.db_dir / f"{name}.db")
            conn.row_factory = sqlite3.Row
            conn.execute(DB_SCHEMA[name])
            conn.commit()
            self._conns[name] = conn

    def close(self):
        for c in self._conns.values():
            c.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # --- knowledge (reels) ---
    def upsert_reel(self, reel: Reel) -> bool:
        """Insert or update a reel. Returns True if changed (new or hash differs)."""
        conn = self._conns["knowledge"]
        cur = conn.execute("SELECT content_hash FROM reels WHERE reel_id=?", (reel.reel_id,))
        row = cur.fetchone()
        new_hash = reel.content_hash()
        if row and row["content_hash"] == new_hash:
            return False
        conn.execute(
            """
            INSERT INTO reels (
                reel_id, url, creator, title, date_saved, category, niche,
                business_model, hook_type, hook_score, mbm_relevance_score,
                potential_revenue, content_hash, created_at, updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(reel_id) DO UPDATE SET
                url=excluded.url, creator=excluded.creator, title=excluded.title,
                date_saved=excluded.date_saved, category=excluded.category,
                niche=excluded.niche, business_model=excluded.business_model,
                hook_type=excluded.hook_type, hook_score=excluded.hook_score,
                mbm_relevance_score=excluded.mbm_relevance_score,
                potential_revenue=excluded.potential_revenue,
                content_hash=excluded.content_hash, updated_at=excluded.updated_at
            """,
            (
                reel.reel_id, reel.url, reel.creator, reel.title, reel.date_saved,
                reel.category, reel.niche, reel.business_model, reel.hook_type,
                reel.hook_score, reel.mbm_relevance_score, reel.potential_revenue,
                new_hash, reel.created_at, _now(),
            ),
        )
        conn.commit()
        return True

    def store_details(self, reel: "Reel"):
        """Populate the detail tables (hooks/offers/psychology/editing/business_models)."""
        # hooks
        if reel.hook_type:
            self.insert_rows(
                "hooks", "hooks",
                ("reel_id", "hook_type", "hook_text", "hook_score", "niche"),
                [(reel.reel_id, reel.hook_type, reel.primary_hook, reel.hook_score, reel.niche)],
            )
        # offers
        self.insert_rows(
            "offers", "offers",
            ("reel_id", "creator", "lead_magnet", "tripwire", "core_offer",
             "upsell", "monetization_method", "price_anchoring"),
            [(reel.reel_id, reel.creator, getattr(reel, "lead_magnet", ""),
              getattr(reel, "tripwire", ""), reel.offer, getattr(reel, "upsell", ""),
              reel.monetization_method, getattr(reel, "price_anchoring", ""))],
        )
        # psychology (one row per trigger)
        triggers = [t.strip() for t in (reel.psychology_used or "").split(",") if t.strip()]
        if triggers:
            self.insert_rows(
                "psychology", "psychology", ("reel_id", "trigger", "note"),
                [(reel.reel_id, t, "") for t in triggers],
            )
        # editing
        self.insert_rows(
            "editing", "editing",
            ("reel_id", "editing_style", "subtitle_style", "color_palette",
             "hook_timing", "cta_timing"),
            [(reel.reel_id, reel.editing_style, getattr(reel, "subtitle_style", ""),
              getattr(reel, "color_palette", ""), getattr(reel, "hook_timing", ""),
              getattr(reel, "cta_timing", ""))],
        )
        # business models
        if reel.business_model:
            self.insert_rows(
                "business_models", "business_models",
                ("reel_id", "business_model", "niche", "revenue_potential"),
                [(reel.reel_id, reel.business_model, reel.niche, reel.mbm_relevance_score)],
            )

    def get_reel(self, reel_id: str) -> dict | None:
        row = self._conns["knowledge"].execute(
            "SELECT * FROM reels WHERE reel_id=?", (reel_id,)
        ).fetchone()
        return dict(row) if row else None

    def all_reel_ids(self) -> list[str]:
        rows = self._conns["knowledge"].execute("SELECT reel_id FROM reels").fetchall()
        return [r["reel_id"] for r in rows]

    # --- creators ---
    def upsert_creator(self, handle: str, **fields):
        conn = self._conns["creators"]
        conn.execute(
            """
            INSERT INTO creators (handle, updated_at, reel_count) VALUES (?,?,1)
            ON CONFLICT(handle) DO UPDATE SET updated_at=?, reel_count=reel_count+1
            """,
            (handle, _now(), _now()),
        )
        if fields:
            sets = ", ".join(f"{k}=?" for k in fields)
            conn.execute(f"UPDATE creators SET {sets} WHERE handle=?", (*fields.values(), handle))
        conn.commit()

    # --- simple append tables ---
    def insert_rows(self, db_name: str, table: str, columns: Iterable[str], rows: Iterable[tuple]):
        conn = self._conns[db_name]
        placeholders = ",".join("?" for _ in columns)
        col_sql = ",".join(columns)
        conn.executemany(
            f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})", list(rows)
        )
        conn.commit()

    # --- queries for reports ---
    def top_hooks(self, limit: int = 20):
        return self._conns["hooks"].execute(
            "SELECT hook_type, COUNT(*) c FROM hooks GROUP BY hook_type ORDER BY c DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def top_niches(self, limit: int = 20):
        return self._conns["knowledge"].execute(
            "SELECT niche, COUNT(*) c FROM reels WHERE niche<>'' GROUP BY niche ORDER BY c DESC LIMIT ?",
            (limit,),
        ).fetchall()

    def top_reels_by_mbm(self, limit: int = 20):
        return self._conns["knowledge"].execute(
            "SELECT reel_id, title, creator, mbm_relevance_score FROM reels ORDER BY mbm_relevance_score DESC LIMIT ?",
            (limit,),
        ).fetchall()
