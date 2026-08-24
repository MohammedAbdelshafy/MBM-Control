"""
Campaign websites — Phase 10 shared frontend contract (config-driven).

Each clipping website is a campaign/brand frontend over the SAME backend. A new
site requires configuration + theme + assets — never a new backend system.

SiteContract carries: landing page fields, offer, brand, niche, sample clips,
turnaround, pricing, FAQ, contact/intake, and optional campaign status. The
generator renders a single static index.html (and assets manifest) per site.
Multiple brands/sites are supported by instantiating with different contracts.
"""
from __future__ import annotations

import html
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class SiteContract:
    slug: str
    brand: str                     # maps to a brand in BrandRegistry
    title: str = ""
    tagline: str = ""
    niche: str = ""
    theme: str = "default"
    offer: str = ""
    turnaround: str = ""
    pricing: list[str] = field(default_factory=list)
    faq: list[dict] = field(default_factory=list)        # [{"q":..., "a":...}]
    sample_clips: list[str] = field(default_factory=list)  # video urls / ids
    contact: dict = field(default_factory=dict)            # {email, form, socials:{}}
    campaign_status: str = ""                              # optional live status
    accent_color: str = "#E11D48"

    def to_dict(self) -> dict:
        return {
            "slug": self.slug, "brand": self.brand, "title": self.title,
            "tagline": self.tagline, "niche": self.niche, "theme": self.theme,
            "offer": self.offer, "turnaround": self.turnaround, "pricing": self.pricing,
            "faq": self.faq, "sample_clips": self.sample_clips, "contact": self.contact,
            "campaign_status": self.campaign_status, "accent_color": self.accent_color,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SiteContract":
        return cls(
            slug=d["slug"], brand=d.get("brand", d["slug"]), title=d.get("title", ""),
            tagline=d.get("tagline", ""), niche=d.get("niche", ""), theme=d.get("theme", "default"),
            offer=d.get("offer", ""), turnaround=d.get("turnaround", ""),
            pricing=d.get("pricing", []), faq=d.get("faq", []), sample_clips=d.get("sample_clips", []),
            contact=d.get("contact", {}), campaign_status=d.get("campaign_status", ""),
            accent_color=d.get("accent_color", "#E11D48"),
        )


def _esc(s: Any) -> str:
    return html.escape(str(s))


def render_html(contract: SiteContract) -> str:
    faq_items = "\n".join(
        f'      <details class="faq"><summary>{_esc(f.get("q",""))}</summary>'
        f'<p>{_esc(f.get("a",""))}</p></details>' for f in contract.faq
    )
    pricing_items = "\n".join(f"      <li>{_esc(p)}</li>" for p in contract.pricing) or "      <li>Contact for pricing</li>"
    clips = "\n".join(
        f'      <div class="clip"><iframe loading="lazy" src="{_esc(c)}" allowfullscreen></iframe></div>'
        if str(c).startswith("http") else f'      <div class="clip"><video src="{_esc(c)}" controls></video></div>'
        for c in contract.sample_clips
    )
    contact = contract.contact or {}
    socials = contact.get("socials", {})
    social_html = " ".join(f'<a href="{_esc(u)}">{_esc(n)}</a>' for n, u in socials.items())
    status_html = (f'<p class="status">Status: {_esc(contract.campaign_status)}</p>'
                   if contract.campaign_status else "")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{_esc(contract.title or contract.brand)}</title>
  <style>
    :root {{ --accent: {_esc(contract.accent_color)}; }}
    body {{ font-family: system-ui, sans-serif; margin:0; color:#111; }}
    header {{ background:var(--accent); color:#fff; padding:3rem 1rem; text-align:center; }}
    main {{ max-width:880px; margin:0 auto; padding:2rem 1rem; }}
    .clip {{ margin:1rem 0; aspect-ratio:9/16; max-width:320px; }}
    .clip iframe, .clip video {{ width:100%; height:100%; border-radius:12px; }}
    .pricing, .faq {{ margin:2rem 0; }}
    .faq summary {{ cursor:pointer; font-weight:600; }}
    .cta {{ background:#111; color:#fff; padding:1rem 1.5rem; border-radius:10px; display:inline-block; text-decoration:none; }}
  </style>
</head>
<body>
  <header>
    <h1>{_esc(contract.title or contract.brand)}</h1>
    <p>{_esc(contract.tagline)}</p>
  </header>
  <main>
    <section><h2>What we do</h2><p>{_esc(contract.offer)}</p>{status_html}</section>
    <section class="clips"><h2>Sample clips</h2>{clips}</section>
    <section><h2>Turnaround</h2><p>{_esc(contract.turnaround)}</p></section>
    <section class="pricing"><h2>Pricing</h2><ul>{pricing_items}</ul></section>
    <section class="faq"><h2>FAQ</h2>{faq_items}</section>
    <section><h2>Get in touch</h2>
      <p>{_esc(contact.get("email",""))}</p>
      <p>{social_html}</p>
      <a class="cta" href="{_esc(contact.get("form", "#"))}">Start a project</a>
    </section>
  </main>
</body>
</html>
"""


def generate_site(contract: SiteContract, out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    site_dir = out_dir / contract.slug
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(render_html(contract), encoding="utf-8")
    (site_dir / "contract.json").write_text(
        json.dumps(contract.to_dict(), indent=2), encoding="utf-8"
    )
    return site_dir


def generate_sites(contracts: list[SiteContract], out_dir: Path) -> list[Path]:
    return [generate_site(c, out_dir) for c in contracts]
