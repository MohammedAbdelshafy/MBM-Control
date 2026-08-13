"""
verify_all_channels.py -- capture REAL channel identity per brand from the persisted
YouTube profiles. Lean + headless=new; reads ytcfg identity, not the banner.
Usage: python verify_all_channels.py               # all brands
       python verify_all_channels.py cutedosage    # one brand
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent
BRANDS = ["clippingfactorymbm", "cutedosage", "dontwatchthis", "goalmachinez", "twistsrevealed"]
RESULTS_PATH = ROOT / "channel_verify_results.json"
HEADLESS_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"


SCRIPT = """
(() => {
  const g = (k) => { try { return (window.ytcfg && ytcfg.get) ? ytcfg.get(k) : null } catch(e){ return null } };
  const ch = g('CHANNEL_ID') || g('CHANNEL_ID_DELEGATED');
  let ch2 = null;
  const a = document.querySelector('a[href*="/channel/"]');
  if (a) { const m = a.getAttribute('href').match(/channel\\/(UC[\\w-]+)/); if (m) ch2 = m[1]; }
  const ts = document.querySelector('title');
  let nameEl = document.querySelector('#account-name, ytcp-text#account-name, a[href*="/@"] > yt-formatted-string');
  const h = document.querySelector('a[href*="/@"]');
  let handle = null;
  if (h) { const m = h.getAttribute('href').match(/@([^/?]+)/); if (m) handle='@'+m[1]; }
  return JSON.stringify({
    channel: ch || ch2,
    name: nameEl ? nameEl.textContent.trim().slice(0,60) : null,
    handle: handle,
    url: location.href,
    title: document.title ? document.title.slice(0,60) : null
  });
})()
"""


def verify_brand(brand: str) -> dict:
    profile_dir = ROOT / f"youtube_profile_{brand}"
    rec = {"brand": brand, "profile": str(profile_dir), "exists": profile_dir.exists(), "ok": False}
    if not profile_dir.exists():
        rec["detail"] = "profile dir not found"
        return rec
    t0 = time.time()
    try:
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=False,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--window-size=1280,900"],
            )
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            try:
                page.goto("https://studio.youtube.com/", timeout=30000, wait_until="domcontentloaded")
            except Exception:
                pass
            time.sleep(8)
            data = page.evaluate(SCRIPT)
            page.close()
        if isinstance(data, str):
            data = json.loads(data)
        rec.update(data or {})
        rec["ok"] = bool(rec.get("channel") and str(rec.get("channel", "")).startswith("UC"))
        rec["state"] = "ready" if rec["ok"] else ("loaded" if rec.get("url") else "no_page")
    except Exception as e:
        rec["detail"] = f"{type(e).__name__}: {str(e)[:160]}"
    rec["secs"] = round(time.time() - t0, 1)
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("brand", nargs="?", default=None)
    args, _ = ap.parse_known_args()
    brands = [args.brand] if args.brand else BRANDS
    results = {}
    if Path(RESULTS_PATH).exists():
        try:
            results = json.loads(Path(RESULTS_PATH).read_text(encoding="utf-8"))
        except Exception:
            results = {}
    for b in brands:
        print(f"=== {b} ===", flush=True)
        r = verify_brand(b)
        results[b] = r
        print(json.dumps({k: r.get(k) for k in ("channel", "handle", "name", "state", "ok", "detail", "secs", "url")}, ensure_ascii=False), flush=True)
    Path(RESULTS_PATH).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()