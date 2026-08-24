import json
import subprocess
from pathlib import Path

CACHE = Path("artifacts/clipping_factory/pd_source_cache.json")
c = json.loads(CACHE.read_text(encoding="utf-8"))

print(f"{'MOVIE':42} {'exists':6} {'MB':>5} {'min':>6} uri  local")
all_ok = True
for key, e in sorted(c.items()):
    lp = e.get("local_path", "")
    p = Path(lp) if lp else None
    exists = bool(p and p.exists())
    mb = round(p.stat().st_size / 1048576) if exists else 0
    d = 0.0
    if exists:
        r = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration",
                            "-of","default=noprint_wrappers=1:nokey=1", str(p)],
                           capture_output=True, text=True)
        try: d = float(r.stdout.strip()) / 60
        except Exception: d = 0.0
    ok = exists and 60 <= mb <= 4000 and 70 <= d <= 160 and bool(e.get("url")) and e.get("verified")
    all_ok &= ok
    print(f"{key:42} {str(exists):6} {mb:>5} {d:>6.1f} {str(bool(e.get('url'))):5} {ok}")

print("ALL_VALID" if all_ok else "INVALID_ENTRIES_PRESENT")

# Discovery handoff proof
from clipping_factory.movie_discovery import discover_movies, SourceClass
pool = discover_movies(genres=None, count=24)
pd = [m for m in pool if m.source_class == SourceClass.PUBLIC_DOMAIN.value]
print(f"\ndiscovery pool={len(pool)} pd_candidates={len(pd)}")
for m in pd:
    ok = m.source_uri != "" and m.source_class == "public_domain"
    print(f"  {m.title} ({m.year}) [{m.campaign_id}] uri={'YES' if m.source_uri else 'EMPTY'} -> {'OK' if ok else 'BLOCKED'}")
