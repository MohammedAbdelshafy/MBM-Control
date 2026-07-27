"""Local dashboard generator for the MBM Instagram Intelligence system.

Reads the SQLite knowledge databases and emits a self-contained dashboard.html
(search, filters, top hooks/niches/creators, weekly reports) plus serves it via
Python's stdlib http.server (no external deps).

Usage:
  python -m ig_intel dashboard --config config.example.yaml
"""

from __future__ import annotations

import argparse
import http.server
import json
import sqlite3
from pathlib import Path
from typing import Callable

from .config import Config


def build_data(cfg: Config) -> dict:
    db_dir = Path(cfg.db_dir)
    conns = {}
    for name in ("knowledge", "creators", "hooks", "offers",
                 "psychology", "editing", "business_models"):
        p = db_dir / f"{name}.db"
        if p.exists():
            conns[name] = sqlite3.connect(p)

    def q(name, sql, args=()):
        c = conns.get(name)
        if not c:
            return []
        return [dict(r) for r in c.execute(sql, args).fetchall()]

    reels = q("knowledge", "SELECT * FROM reels ORDER BY mbm_relevance_score DESC")
    creators = q("creators", "SELECT * FROM creators ORDER BY reel_count DESC")
    hook_rows = q("knowledge", "SELECT hook_type, COUNT(*) c FROM hooks GROUP BY hook_type ORDER BY c DESC")
    niche_rows = q("knowledge", "SELECT niche, COUNT(*) c FROM reels WHERE niche<>'' GROUP BY niche ORDER BY c DESC")

    data = {
        "reels": reels,
        "creators": creators,
        "top_hooks": hook_rows,
        "top_niches": niche_rows,
        "counts": {
            "reels": len(reels),
            "creators": len(creators),
            "hooks": sum(r["c"] for r in hook_rows),
        },
    }
    for c in conns.values():
        c.close()
    return data


def render_html(data: dict) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MBM Instagram Intelligence</title>
<style>
  :root{--bg:#0b0e14;--card:#151a23;--fg:#e6e6e6;--accent:#5b8cff;--mut:#8b94a3}
  *{box-sizing:border-box}
  body{margin:0;font-family:system-ui,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg)}
  header{padding:16px 20px;background:var(--card);display:flex;gap:16px;align-items:center;flex-wrap:wrap}
  h1{font-size:18px;margin:0}
  .stat{background:#1d2430;padding:8px 14px;border-radius:10px;font-size:13px}
  .stat b{color:var(--accent)}
  main{padding:20px;display:grid;grid-template-columns:320px 1fr;gap:20px}
  .side{display:flex;flex-direction:column;gap:16px}
  .panel{background:var(--card);border-radius:12px;padding:14px}
  .panel h2{font-size:14px;margin:0 0 10px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em}
  input,select{width:100%;padding:8px 10px;border-radius:8px;border:1px solid #2a3340;background:#0f141c;color:var(--fg)}
  .reel{padding:12px;border-bottom:1px solid #1d2430}
  .reel h3{margin:0 0 4px;font-size:15px}
  .tag{display:inline-block;background:#1d2430;border-radius:6px;padding:2px 8px;font-size:11px;margin:2px 4px 2px 0;color:var(--mut)}
  .score{color:var(--accent);font-weight:700}
  ul{margin:6px 0;padding-left:18px;font-size:13px}
  .list .row{display:flex;justify-content:space-between;font-size:13px;padding:3px 0;border-bottom:1px solid #1d2430}
</style></head>
<body>
<header>
  <h1>MBM Instagram Intelligence</h1>
  <div class="stat">Reels <b id="c-reels"></b></div>
  <div class="stat">Creators <b id="c-creators"></b></div>
  <div class="stat">Hooks <b id="c-hooks"></b></div>
</header>
<main>
  <div class="side">
    <div class="panel">
      <h2>Search & Filter</h2>
      <input id="q" placeholder="search caption, creator, niche..." oninput="apply()">
      <select id="f-niche" onchange="apply()" style="margin-top:8px"></select>
      <select id="f-model" onchange="apply()" style="margin-top:8px"></select>
    </div>
    <div class="panel list"><h2>Top Hooks</h2><div id="hooks"></div></div>
    <div class="panel list"><h2>Top Niches</h2><div id="niches"></div></div>
  </div>
  <div>
    <div class="panel"><h2>Reels</h2><div id="reels"></div></div>
  </div>
</main>
<script>
const DATA = __PAYLOAD__;
function uniq(arr,key){return [...new Set(arr.map(x=>x[key]).filter(Boolean))];}
function init(){
  document.getElementById('c-reels').textContent=DATA.counts.reels;
  document.getElementById('c-creators').textContent=DATA.counts.creators;
  document.getElementById('c-hooks').textContent=DATA.counts.hooks;
  const niches=uniq(DATA.reels,'niche'); const models=uniq(DATA.reels,'business_model');
  const nsel=document.getElementById('f-niche'); nsel.innerHTML='<option value="">All niches</option>'+niches.map(n=>`<option>${n}</option>`).join('');
  const msel=document.getElementById('f-model'); msel.innerHTML='<option value="">All business models</option>'+models.map(m=>`<option>${m}</option>`).join('');
  document.getElementById('hooks').innerHTML=DATA.top_hooks.map(h=>`<div class="row"><span>${h.hook_type}</span><b>${h.c}</b></div>`).join('')||'<div class="row">none</div>';
  document.getElementById('niches').innerHTML=DATA.top_niches.map(n=>`<div class="row"><span>${n.niche}</span><b>${n.c}</b></div>`).join('')||'<div class="row">none</div>';
  apply();
}
function apply(){
  const q=document.getElementById('q').value.toLowerCase();
  const niche=document.getElementById('f-niche').value;
  const model=document.getElementById('f-model').value;
  const rows=DATA.reels.filter(r=>
    (!q || (r.title+r.caption+r.creator+r.niche).toLowerCase().includes(q)) &&
    (!niche || r.niche===niche) && (!model || r.business_model===model)
  );
  document.getElementById('reels').innerHTML=rows.map(r=>`
    <div class="reel">
      <h3>${esc(r.title||'(untitled)')}</h3>
      <div><span class="tag">${esc(r.creator)}</span><span class="tag">${esc(r.niche)}</span>
      <span class="tag">${esc(r.business_model)}</span><span class="tag">${esc(r.hook_type)}</span>
      <span class="score">MBM ${r.mbm_relevance_score||0}</span></div>
      <div style="font-size:13px;color:var(--mut)">${esc((r.caption||'').slice(0,160))}</div>
      <div><a class="tag" href="${esc(r.url)}" target="_blank">open</a></div>
    </div>`).join('')||'<div class="reel">No reels match.</div>';
}
function esc(s){return (s||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
init();
</script></body></html>""".replace("__PAYLOAD__", payload)


def serve(cfg: Config, log: Callable[[str], None] = print, port: int = 8787):
    data = build_data(cfg)
    out = Path(cfg.knowledge_dir).resolve() / "dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(data), encoding="utf-8")
    log(f"[dashboard] wrote {out}")

    handler = http.server.SimpleHTTPRequestHandler
    # serve from the knowledge dir so dashboard.html is at root
    class _H(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **k):
            super().__init__(*a, directory=str(out.parent), **k)

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), _H)
    log(f"[dashboard] serving at http://127.0.0.1:{port}/  (Ctrl+C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        log("[dashboard] stopped")


def main(argv=None):
    p = argparse.ArgumentParser(prog="ig_intel dashboard")
    p.add_argument("--config", default="config.example.yaml")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--no-serve", action="store_true", help="only write dashboard.html")
    args = p.parse_args(argv)
    cfg = Config.load(args.config).resolve()
    data = build_data(cfg)
    out = Path(cfg.knowledge_dir).resolve() / "dashboard.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_html(data), encoding="utf-8")
    print(f"[dashboard] wrote {out}")
    if not args.no_serve:
        serve(cfg, port=args.port)
