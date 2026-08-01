import json, time
from ig_intel.collector import _DevToolsMCP

m = _DevToolsMCP("http://127.0.0.1:9222", print)
tabs = [t for t in m._tabs() if "instagram" in t.get("url", "")]
ws = tabs[0]["webSocketDebuggerUrl"]
urls = m._cdp_extract(ws, "saved", scrolls=6)
print("REEL URLS FOUND:", len(urls))
for u in urls[:12]:
    print("  ", u.get("url"))
