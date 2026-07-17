"""Load MBM-Social brand configs + registries (single source of truth)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
BRANDS_DIR = ROOT / "Brands"


def _read_json(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def load_brand(slug: str) -> dict:
    """Return merged brand config from brand.yaml + its markdown rule files."""
    d = BRANDS_DIR / slug
    if not d.exists():
        raise FileNotFoundError(f"No brand folder for '{slug}' at {d}")
    import yaml

    cfg: dict[str, Any] = yaml.safe_load((d / "brand.yaml").read_text(encoding="utf-8"))
    cfg["sources"] = yaml.safe_load((d / "sources.yaml").read_text(encoding="utf-8"))
    cfg["posting"] = yaml.safe_load((d / "posting_schedule.yaml").read_text(encoding="utf-8"))
    cfg["kpis"] = yaml.safe_load((d / "kpis.yaml").read_text(encoding="utf-8"))
    cfg["style_guide"] = (d / "style_guide.md").read_text(encoding="utf-8")
    cfg["thumbnail_rules"] = (d / "thumbnail_rules.md").read_text(encoding="utf-8")
    cfg["title_rules"] = (d / "title_rules.md").read_text(encoding="utf-8")
    cfg["caption_rules"] = (d / "caption_rules.md").read_text(encoding="utf-8")
    return cfg


def load_all_brands() -> list[dict]:
    return [load_brand(p.name) for p in sorted(BRANDS_DIR.iterdir()) if p.is_dir()]


def load_registry(name: str) -> dict:
    return _read_json(name)


def load_campaign_router() -> dict:
    return _read_json("CampaignRouter.json")


def load_channel_registry() -> dict:
    return _read_json("ChannelRegistry.json")


def channel_for_brand(slug: str) -> Optional[dict]:
    reg = load_channel_registry()
    for ch in reg.get("channels", []):
        if ch["brand"] == slug:
            return ch
    return None


def active_brands() -> list[dict]:
    reg = load_registry("BrandRegistry.json")
    return [b for b in reg["brands"].values() if b.get("active")]
