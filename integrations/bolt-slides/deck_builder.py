#!/usr/bin/env python3
"""Interactive pitch-deck builder (VibeFounder power #8).

"Generate interactive presentations with live apps inside"
([Bolt.new Slides reel](https://www.instagram.com/reel/Da3DxB8uKBk/)).

A stdlib-only generator that turns a JSON-able slide spec into ONE
self-contained HTML file: no build step, no npm, no CDN, no network at
view time. Slides support click-to-reveal builds, presenter notes, hash
deep-links, and — the actual power — *live widgets embedded in slides*:

  data_clean_demo  — "messy list -> clean list" live demo (DataClean AI pitch)
  roi_calculator   — prospect-tunable ROI slider math (their inputs, not our claims)

Usage:
    python3 deck_builder.py --sample      # write samples/dataclean-pitch.html
    python3 deck_builder.py --widgets      # list supported slide kinds/widgets

All user content is html-escaped on render; widget config that reaches JS
goes through json.dumps, never string interpolation.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
import uuid
from pathlib import Path

THEMES = ("midnight", "paper")
SLIDE_KINDS = ("cover", "bullets", "statement", "widget", "chart",
               "pricing", "cta")
WIDGETS = ("data_clean_demo", "roi_calculator")

VERSION = "1.0.0"


def _esc(text) -> str:
    return html.escape("" if text is None else str(text), quote=True)


def _js(value) -> str:
    # Safe bridge for config values into the generated <script>.
    return json.dumps(value)


# ---------------------------------------------------------------------------
# Deck model
# ---------------------------------------------------------------------------

class Deck:
    """An ordered list of slides; renders to a single self-contained HTML file."""

    def __init__(self, title: str, subtitle: str = "", theme: str = "midnight",
                 author: str = ""):
        if not (title or "").strip():
            raise ValueError("deck title is required")
        if theme not in THEMES:
            raise ValueError(f"theme must be one of {THEMES}")
        self.title = title
        self.subtitle = subtitle
        self.theme = theme
        self.author = author
        self.slides: list[dict] = []

    # -- slide builders ----------------------------------------------------
    def _add(self, kind: str, payload: dict, notes: str = "") -> int:
        if kind not in SLIDE_KINDS:
            raise ValueError(f"unknown slide kind: {kind!r} "
                             f"(expected one of {SLIDE_KINDS})")
        self.slides.append({"kind": kind, "payload": payload,
                            "notes": notes or ""})
        return len(self.slides) - 1

    def add_cover(self, kicker: str, title: str, subtitle: str = "",
                  cta: str = "", notes: str = "") -> int:
        return self._add("cover", {"kicker": kicker, "title": title,
                                   "subtitle": subtitle, "cta": cta},
                         notes)

    def add_bullets(self, title: str, items: list[str],
                    notes: str = "") -> int:
        if not items:
            raise ValueError("bullets slide needs at least one item")
        return self._add("bullets", {"title": title, "items": list(items)},
                         notes)

    def add_statement(self, text: str, sub: str = "", notes: str = "") -> int:
        return self._add("statement", {"text": text, "sub": sub}, notes)

    def add_widget(self, widget: str, title: str = "",
                   config: dict | None = None, notes: str = "") -> int:
        if widget not in WIDGETS:
            raise ValueError(f"unknown widget: {widget!r} "
                             f"(expected one of {WIDGETS})")
        return self._add("widget", {"widget": widget, "title": title,
                                    "config": dict(config or {})}, notes)

    def add_chart(self, title: str, series: list[tuple[str, float]],
                  notes: str = "") -> int:
        clean = []
        for label, value in series:
            if not isinstance(value, (int, float)) or value < 0:
                raise ValueError(f"chart values must be non-negative "
                                 f"numbers, got {value!r}")
            clean.append((str(label), float(value)))
        if not clean:
            raise ValueError("chart slide needs at least one data point")
        return self._add("chart", {"title": title, "series": clean}, notes)

    def add_pricing(self, title: str, tiers: list[dict],
                    notes: str = "") -> int:
        for tier in tiers:
            if "name" not in tier or "price" not in tier:
                raise ValueError("each pricing tier needs 'name' and 'price'")
        return self._add("pricing", {"title": title,
                                     "tiers": [dict(t) for t in tiers]},
                         notes)

    def add_cta(self, title: str, lines: list[str], button_text: str,
                button_url: str, notes: str = "") -> int:
        if not button_url.strip():
            raise ValueError("cta slide needs a button_url")
        return self._add("cta", {"title": title, "lines": list(lines),
                                 "button_text": button_text,
                                 "button_url": button_url}, notes)

    # -- serialisation ------------------------------------------------------
    def to_dict(self) -> dict:
        return {"title": self.title, "subtitle": self.subtitle,
                "theme": self.theme, "author": self.author,
                "slides": self.slides, "version": VERSION}

    def render_html(self) -> str:
        return _render(self)

    def save(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render_html(), encoding="utf-8")
        return path


# ---------------------------------------------------------------------------
# Renderer — one self-contained HTML file
# ---------------------------------------------------------------------------

_CSS = r"""
:root{
  --bg:#0b0f1a; --bg2:#111728; --ink:#f2f5fb; --mut:#9aa7c2;
  --acc:#7c6cf5; --acc2:#39d0d8; --card:#151d33; --line:#263049;
}
body.paper{ --bg:#faf8f2; --bg2:#ffffff; --ink:#141821; --mut:#5b6478;
  --acc:#5a3fd4; --acc2:#0e7f86; --card:#ffffff; --line:#e4e0d2; }
*{box-sizing:border-box}
html,body{height:100%}
body{margin:0;background:var(--bg);color:var(--ink);
  font-family:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  overflow:hidden}
#deck{position:fixed;inset:0}
.slide{position:absolute;inset:0;display:none;padding:6vh 8vw;
  background:radial-gradient(1200px 600px at 80% -10%,#1a2340 0%,var(--bg) 55%)}
body.paper .slide{background:radial-gradient(1200px 600px at 80% -10%,#efe9d8 0%,var(--bg) 60%)}
.slide.active{display:flex;flex-direction:column;justify-content:center}
.kicker{letter-spacing:.28em;text-transform:uppercase;font-size:13px;color:var(--acc2);margin:0 0 18px}
h1.title{font-size:clamp(38px,6vw,84px);line-height:1.04;margin:0 0 18px;font-weight:800}
h2.stitle{font-size:clamp(28px,3.6vw,52px);margin:0 0 26px;font-weight:750}
.subtitle{font-size:clamp(17px,2vw,26px);color:var(--mut);max-width:60ch;line-height:1.5}
.cta-line{margin-top:34px;font-size:18px;color:var(--ink)}
ul.points{list-style:none;margin:0;padding:0;display:grid;gap:18px;max-width:70ch}
ul.points li{font-size:clamp(18px,2.2vw,28px);line-height:1.45;padding-left:34px;position:relative}
ul.points li::before{content:"▸";position:absolute;left:0;color:var(--acc)}
.build{opacity:0;transform:translateY(14px);transition:opacity .45s,transform .45s}
.build.shown{opacity:1;transform:none}
.statement{font-size:clamp(34px,5vw,72px);font-weight:800;line-height:1.12;text-align:center}
.statement .sub{display:block;font-size:.42em;color:var(--mut);font-weight:500;margin-top:18px}
.accent{background:linear-gradient(92deg,var(--acc),var(--acc2));
  -webkit-background-clip:text;background-clip:text;color:transparent}
.widget{background:var(--card);border:1px solid var(--line);border-radius:18px;
  padding:26px;max-width:860px}
.widget h3{margin:0 0 14px;font-size:22px}
.widget textarea{width:100%;min-height:150px;background:var(--bg2);color:var(--ink);
  border:1px solid var(--line);border-radius:10px;padding:12px;font:13px/1.5 ui-monospace,monospace}
.widget button{background:linear-gradient(92deg,var(--acc),var(--acc2));border:0;color:#fff;
  font-weight:700;font-size:16px;padding:12px 26px;border-radius:999px;cursor:pointer;margin-top:12px}
.widget button:hover{filter:brightness(1.1)}
.dc-out{margin-top:14px;font-size:15px}
.dc-out table{border-collapse:collapse;width:100%;margin-top:8px}
.dc-out th,.dc-out td{border:1px solid var(--line);padding:6px 10px;text-align:left;font-size:13px}
.dc-out th{background:var(--bg2)}
.stat-row{display:flex;gap:26px;margin-top:10px;flex-wrap:wrap}
.stat b{font-size:30px;display:block}
.stat span{color:var(--mut);font-size:13px}
.roi-grid{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:6px}
.roi-grid label{font-size:14px;color:var(--mut);display:block;margin-bottom:6px}
.roi-grid input[type=range]{width:100%}
.roi-val{font-size:20px;font-weight:700}
.roi-result{background:var(--bg2);border:1px solid var(--line);border-radius:12px;padding:16px}
.roi-result .big{font-size:34px;font-weight:800;color:var(--acc2)}
.fine{font-size:12px;color:var(--mut);margin-top:10px}
.chart{display:flex;align-items:flex-end;gap:26px;height:300px;max-width:820px;
  border-left:2px solid var(--line);border-bottom:2px solid var(--line);padding:0 10px}
.bar{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%}
.bar i{display:block;width:64%;border-radius:8px 8px 0 0;
  background:linear-gradient(180deg,var(--acc),var(--acc2))}
.bar b{margin-top:10px;font-size:14px}
.bar span{font-size:12px;color:var(--mut)}
.tiers{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:18px;max-width:1000px}
.tier{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:24px}
.tier.hot{border:2px solid var(--acc);transform:scale(1.03)}
.tier h3{margin:0 0 6px;font-size:20px}
.tier .price{font-size:30px;font-weight:800;margin:6px 0 12px}
.tier ul{margin:0;padding-left:18px;color:var(--mut);font-size:14px;display:grid;gap:6px}
.cta{text-align:center}
.cta .btn{display:inline-block;margin-top:26px;background:linear-gradient(92deg,var(--acc),var(--acc2));
  color:#fff;font-weight:800;font-size:20px;padding:16px 44px;border-radius:999px;text-decoration:none}
#progress{position:fixed;top:0;left:0;height:4px;width:0;
  background:linear-gradient(90deg,var(--acc),var(--acc2));z-index:50;transition:width .3s}
#counter{position:fixed;right:26px;bottom:20px;color:var(--mut);font-size:14px;z-index:50}
#hint{position:fixed;left:26px;bottom:20px;color:var(--mut);font-size:13px;z-index:50}
#notes{position:fixed;left:0;right:0;bottom:0;background:#000c;color:var(--ink);
  padding:14px 26px;font-size:14px;display:none;z-index:60;border-top:1px solid var(--line)}
body.show-notes #notes{display:block}
"""

_JS_APP = r"""
(function(){
  var slides=Array.prototype.slice.call(document.querySelectorAll('.slide'));
  var idx=0;
  function parseHash(){var m=location.hash.match(/^#s(\d+)$/);
    return m?Math.min(slides.length-1,Math.max(0,parseInt(m[1],10)-1)):0;}
  function pendingBuilds(){
    return Array.prototype.slice.call(
      slides[idx].querySelectorAll('.build:not(.shown)'));}
  function show(i){
    slides[idx].classList.remove('active');
    idx=Math.min(slides.length-1,Math.max(0,i));
    slides.forEach(function(s){Array.prototype.forEach.call(
      s.querySelectorAll('.build'),function(b){b.classList.remove('shown');});});
    slides[idx].classList.add('active');
    document.getElementById('progress').style.width=((idx+1)/slides.length*100)+'%';
    document.getElementById('counter').textContent=(idx+1)+' / '+slides.length;
    try{history.replaceState(null,'','#s'+(idx+1));}catch(e){}
    document.getElementById('notes').textContent=
      slides[idx].getAttribute('data-notes')||'';
  }
  function next(){var p=pendingBuilds();
    if(p.length){p[0].classList.add('shown');}else{show(idx+1);}}
  function toggleFull(){
    if(!document.fullscreenElement){document.documentElement.requestFullscreen&&
      document.documentElement.requestFullscreen();}
    else{document.exitFullscreen&&document.exitFullscreen();}}
  document.addEventListener('keydown',function(e){
    var t=e.target&&e.target.tagName;
    if(t==='TEXTAREA'||t==='INPUT'){if(e.key==='Escape')e.target.blur();return;}
    if(e.key==='ArrowRight'||e.key===' '||e.key==='PageDown'){e.preventDefault();next();}
    else if(e.key==='ArrowLeft'||e.key==='PageUp'){e.preventDefault();show(idx-1);}
    else if(e.key==='Home'){e.preventDefault();show(0);}
    else if(e.key==='End'){e.preventDefault();show(slides.length-1);}
    else if(e.key==='n'||e.key==='N'){document.body.classList.toggle('show-notes');}
    else if(e.key==='f'||e.key==='F'){toggleFull();}
  });
  document.addEventListener('click',function(e){
    if(e.target.closest('button,textarea,input,a,.widget,.tier'))return;
    next();
  });
  show(parseHash());
})();
"""

_JS_DEMO = r"""
function dcClean(btn){
  var w=btn.closest('.widget');
  var ta=w.querySelector('textarea'), out=w.querySelector('.dc-out');
  var lines=ta.value.split('\n').map(function(l){return l.trim();}).filter(Boolean);
  var before=lines.length, seen={}, rows=[];
  lines.forEach(function(line){
    var parts=line.split(',').map(function(p){return p.trim();});
    var name=(parts[0]||'').toLowerCase().replace(/\b\w/g,function(c){return c.toUpperCase();});
    var email=(parts[1]||'').toLowerCase();
    var phone=(parts[2]||'').replace(/[^0-9+]/g,'');
    if(!email||seen[email])return;
    seen[email]=1; rows.push([name,email,phone]);
  });
  var dupes=before-rows.length;
  var h='<div class="stat-row">'
    +'<div class="stat"><b>'+before+'</b><span>rows in</span></div>'
    +'<div class="stat"><b>'+rows.length+'</b><span>clean rows out</span></div>'
    +'<div class="stat"><b>'+dupes+'</b><span>duplicates removed</span></div></div>';
  h+='<table><tr><th>Name</th><th>Email</th><th>Phone</th></tr>';
  rows.slice(0,12).forEach(function(r){
    h+='<tr><td>'+r[0].replace(/&/g,'&amp;').replace(/</g,'&lt;')
      +'</td><td>'+r[1].replace(/&/g,'&amp;').replace(/</g,'&lt;')
      +'</td><td>'+r[2].replace(/&/g,'&amp;').replace(/</g,'&lt;')+'</td></tr>';});
  h+='</table>';
  if(rows.length>12)h+='<div class="fine">showing first 12 of '+rows.length+' clean rows</div>';
  out.innerHTML=h;
}
"""

_JS_ROI = r"""
function roiUpdate(scope){
  var w=typeof scope==='string'?document.getElementById(scope):scope.closest('.widget');
  var g=function(id){return parseFloat(w.querySelector('[data-roi="'+id+'"]').value);};
  var hrs=g('hrs'), rate=g('rate'), team=g('team'), price=g('price');
  w.querySelector('[data-roi-val="hrs"]').textContent=hrs;
  w.querySelector('[data-roi-val="rate"]').textContent='$'+rate;
  w.querySelector('[data-roi-val="team"]').textContent=team;
  var monthly=hrs*4.33*rate*team, annual=monthly*12;
  var payback=price>0&&monthly>0?(price/monthly*30):0;
  w.querySelector('[data-roi-out="monthly"]').textContent=
    '$'+Math.round(monthly).toLocaleString('en-US');
  w.querySelector('[data-roi-out="annual"]').textContent=
    '$'+Math.round(annual).toLocaleString('en-US');
  w.querySelector('[data-roi-out="payback"]').textContent=
    payback>0?Math.max(1,Math.round(payback))+' days':'—';
}
document.addEventListener('input',function(e){
  if(e.target&&e.target.hasAttribute&&e.target.hasAttribute('data-roi'))
    roiUpdate(e.target);
});
"""


def _slide_open(notes: str) -> str:
    return (f'<section class="slide" data-notes="{_esc(notes)}">' if notes
            else '<section class="slide" data-notes="">')


def _render_cover(p: dict) -> str:
    out = _slide_open("") + f'<p class="kicker">{_esc(p.get("kicker"))}</p>'
    out += f'<h1 class="title">{_esc(p.get("title"))}</h1>'
    if p.get("subtitle"):
        out += f'<p class="subtitle">{_esc(p.get("subtitle"))}</p>'
    if p.get("cta"):
        out += f'<p class="cta-line">{_esc(p.get("cta"))}</p>'
    return out + "</section>"


def _render_bullets(p: dict) -> str:
    items = "".join(
        f'<li class="build">{_esc(it)}</li>' for it in p.get("items", []))
    return (_slide_open("") + f'<h2 class="stitle">{_esc(p.get("title"))}</h2>'
            f'<ul class="points">{items}</ul></section>')


def _render_statement(p: dict) -> str:
    sub = f'<span class="sub">{_esc(p.get("sub"))}</span>' if p.get("sub") else ""
    return (_slide_open("")
            + f'<div class="statement">{_esc(p.get("text"))}{sub}</div>'
            + "</section>")


_MESSY_SAMPLE = (
    "  john SMITH ,  John.Smith@Example.COM , (555) 123-4567\n"
    "Maria Garcia,maria.garcia@example.com,555-987-6543\n"
    "JOHN smith,john.smith@example.com,5551234567\n"
    "  alex kim  , ALEX.KIM@EXAMPLE.COM ,(555) 222-8899\n"
    "maria garcia , Maria.Garcia@example.com , 5559876543\n"
    "Priya Nair,priya.nair@example.com,555-444-1212"
)


def _render_widget(p: dict, uid: str) -> str:
    widget = p.get("widget")
    title = f'<h2 class="stitle">{_esc(p.get("title"))}</h2>' if p.get("title") else ""
    cfg = p.get("config") or {}
    if widget == "data_clean_demo":
        body = (
            f'<div class="widget"><h3>{_esc(cfg.get("heading", "Live demo — messy list in, clean list out"))}</h3>'
            f'<textarea>{_esc(cfg.get("sample", _MESSY_SAMPLE))}</textarea>'
            '<button onclick="dcClean(this)">Clean this list →</button>'
            '<div class="dc-out"><div class="fine">Hit the button — dedupe, '
            'normalise names, lowercase emails, strip phone junk. '
            'Runs 100% in this page.</div></div></div>'
        )
    elif widget == "roi_calculator":
        hrs = int(cfg.get("hours_per_week", 6))
        rate = int(cfg.get("hourly_value", 50))
        team = int(cfg.get("team_size", 2))
        price = int(cfg.get("pilot_price", 499))
        body = (
            f'<div class="widget" id="{uid}"><h3>{_esc(cfg.get("heading", "What is manual list-cleaning costing you?"))}</h3>'
            '<div class="roi-grid"><div>'
            f'<label>Hours/week on manual cleaning: <span class="roi-val" data-roi-val="hrs">{hrs}</span></label>'
            f'<input type="range" min="1" max="40" value="{hrs}" data-roi="hrs">'
            f'<label>Value of an hour: <span class="roi-val" data-roi-val="rate">${rate}</span></label>'
            f'<input type="range" min="10" max="200" step="5" value="{rate}" data-roi="rate">'
            f'<label>People doing it: <span class="roi-val" data-roi-val="team">{team}</span></label>'
            f'<input type="range" min="1" max="20" value="{team}" data-roi="team">'
            f'<input type="hidden" value="{price}" data-roi="price">'
            '</div><div class="roi-result">'
            '<div>Manual cost / month</div><div class="big" data-roi-out="monthly">–</div>'
            '<div style="margin-top:10px">Manual cost / year</div><div class="big" data-roi-out="annual">–</div>'
            f'<div style="margin-top:10px">A ${_esc(price)} pilot pays for itself in</div>'
            '<div class="big" data-roi-out="payback">–</div>'
            '</div></div>'
            '<div class="fine">Your inputs, your math — drag the sliders. '
            'We make no claim about your numbers; this is a calculator, not a promise.</div>'
            f'<script>roiUpdate("{uid}")</script></div>'
        )
    else:  # pragma: no cover — validated in add_widget
        raise ValueError(f"unknown widget: {widget!r}")
    return _slide_open("") + title + body + "</section>"


def _render_chart(p: dict) -> str:
    series = p.get("series", [])
    peak = max(v for _, v in series) or 1
    bars = "".join(
        f'<div class="bar"><i style="height:{round(v / peak * 100)}%"></i>'
        f'<b>{v:g}</b><span>{_esc(label)}</span></div>'
        for label, v in series)
    return (_slide_open("")
            + f'<h2 class="stitle">{_esc(p.get("title"))}</h2>'
            + f'<div class="chart">{bars}</div></section>')


def _render_pricing(p: dict) -> str:
    cards = []
    for tier in p.get("tiers", []):
        feats = "".join(f"<li>{_esc(f)}</li>" for f in tier.get("features", []))
        hot = " hot" if tier.get("highlight") else ""
        cards.append(
            f'<div class="tier{hot}"><h3>{_esc(tier.get("name"))}</h3>'
            f'<div class="price">{_esc(tier.get("price"))}</div>'
            f'<ul>{feats}</ul></div>')
    return (_slide_open("")
            + f'<h2 class="stitle">{_esc(p.get("title"))}</h2>'
            + f'<div class="tiers">{"".join(cards)}</div></section>')


def _render_cta(p: dict) -> str:
    lines = "".join(f'<p class="subtitle">{_esc(ln)}</p>'
                    for ln in p.get("lines", []))
    return (_slide_open("")
            + '<div class="cta">'
            f'<h2 class="stitle">{_esc(p.get("title"))}</h2>{lines}'
            f'<br><a class="btn" href="{_esc(p.get("button_url"))}">'
            f'{_esc(p.get("button_text"))}</a></div></section>')


def _render(deck: Deck) -> str:
    body_parts = []
    uid_counter = [0]

    def _uid() -> str:
        uid_counter[0] += 1
        return f"w{uid_counter[0]}"

    for slide in deck.slides:
        kind, payload = slide["kind"], slide["payload"]
        # stash notes on the section element
        if kind == "cover":
            part = _render_cover(payload)
        elif kind == "bullets":
            part = _render_bullets(payload)
        elif kind == "statement":
            part = _render_statement(payload)
        elif kind == "widget":
            part = _render_widget(payload, _uid())
        elif kind == "chart":
            part = _render_chart(payload)
        elif kind == "pricing":
            part = _render_pricing(payload)
        elif kind == "cta":
            part = _render_cta(payload)
        else:  # pragma: no cover — validated in _add
            raise ValueError(f"unknown slide kind: {kind!r}")
        notes = slide.get("notes", "")
        if notes:
            part = part.replace('data-notes=""',
                                f'data-notes="{_esc(notes)}"', 1)
        body_parts.append(part)

    needs_demo = any(s["kind"] == "widget" and s["payload"].get("widget")
                     == "data_clean_demo" for s in deck.slides)
    needs_roi = any(s["kind"] == "widget" and s["payload"].get("widget")
                    == "roi_calculator" for s in deck.slides)

    scripts = [_JS_APP]
    if needs_demo:
        scripts.append(_JS_DEMO)
    if needs_roi:
        scripts.append(_JS_ROI)
    script_tags = "".join(f"<script>{js}</script>" for js in scripts)

    return ("<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">\n"
            f"<title>{_esc(deck.title)}</title>\n"
            f"<style>{_CSS}</style>\n</head>\n"
            f"<body class=\"{deck.theme}\">\n"
            '<div id="progress"></div>\n<div id="deck">\n'
            + "\n".join(body_parts)
            + "\n</div>\n"
            '<div id="counter"></div>\n'
            '<div id="hint">← → navigate · click advances · N notes · F fullscreen</div>\n'
            '<div id="notes"></div>\n'
            + script_tags
            + "\n</body>\n</html>\n")


# ---------------------------------------------------------------------------
# Sample deck — the DataClean AI $499 pitch (honest, verified offer facts only)
# ---------------------------------------------------------------------------

def build_dataclean_sample() -> Deck:
    d = Deck(title="DataClean AI — $499 Pilot Pitch",
             subtitle="Interactive pitch deck",
             theme="midnight", author="MBM")
    d.add_cover(
        kicker="MBM · DataClean AI",
        title="Your list is costing you money.",
        subtitle="We turn messy prospect lists into clean, callable, "
                 "send-ready data — 10,000 records in 48 hours.",
        cta="↓ keep clicking — there's a live demo inside",
        notes="Open with the pain. Don't pitch yet; let the demo do it.")
    d.add_bullets(
        "Dirty data is a silent tax",
        ["Duplicate leads → your team calls the same person twice",
         "Dead emails → bounces hurt your sender reputation",
         "Messy names/phones → your CRM becomes unusable",
         "Nobody on your team wants to clean it by hand"],
        notes="One click per bullet — let each land before advancing.")
    d.add_widget(
        "data_clean_demo",
        title="Watch it work — live",
        config={"heading": "Paste a messy list. Hit the button."},
        notes="This runs entirely in the deck — no backend, no waiting. "
              "Offer to paste THEIR sample list here on the call.")
    d.add_statement(
        "10,000 records. 48 hours. $499.",
        sub="One flat pilot. You see the clean file before anything else happens.",
        notes="The offer, plain. Then the calculator lets them price their own pain.")
    d.add_widget(
        "roi_calculator",
        title="Price your own pain",
        config={"heading": "What does manual cleaning cost you?",
                "hours_per_week": 6, "hourly_value": 50,
                "team_size": 2, "pilot_price": 499},
        notes="Their sliders, their numbers — we claim nothing about their ROI.")
    d.add_chart(
        "What you get back",
        [("Duplicates removed", 18), ("Bad emails fixed", 24),
         ("Phones normalised", 31), ("Hours saved", 40)],
        notes="Illustrative shape of a typical clean — label it as such on the call.")
    d.add_pricing(
        "Start free. Scale when it works.",
        [{"name": "Free sample", "price": "$0",
          "features": ["500–1,000 records", "Same 48-hour process",
                       "No card, no commitment"]},
         {"name": "$499 Pilot", "price": "$499",
          "features": ["Up to 10,000 records", "48-hour turnaround",
                       "Dedupe + normalise + verify", "Clean CSV/Excel back"],
          "highlight": True},
         {"name": "Ongoing", "price": "Custom",
          "features": ["Monthly list hygiene", "CRM-ready exports",
                       "Priority turnaround"]}],
        notes="Free sample is the foot in the door — always offer it first.")
    d.add_cta(
        "Get your free 500-record sample",
        ["Send any messy list — CSV or Excel.",
         "Back in 48 hours, clean. Then decide."],
        button_text="Start my free sample →",
        button_url="https://clipform.io/7f9689f00",
        notes="Close: the only ask is the free sample. Email fallback: "
              "abdelshafyclapps@gmail.com")
    return d


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Interactive pitch-deck builder")
    ap.add_argument("--sample", action="store_true",
                    help="generate the DataClean AI sample pitch deck")
    ap.add_argument("--out", default="samples/dataclean-pitch.html",
                    help="output path for --sample")
    ap.add_argument("--widgets", action="store_true",
                    help="list slide kinds and widgets")
    args = ap.parse_args(argv)

    if args.widgets:
        print("slide kinds:", ", ".join(SLIDE_KINDS))
        print("widgets:    ", ", ".join(WIDGETS))
        print("themes:     ", ", ".join(THEMES))
        return 0
    if args.sample:
        deck = build_dataclean_sample()
        out = Path(args.out)
        if not out.is_absolute():
            out = Path(__file__).resolve().parent / out
        deck.save(out)
        print(f"wrote {out} ({len(deck.slides)} slides)")
        return 0
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
