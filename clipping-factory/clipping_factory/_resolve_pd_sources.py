"""One-off resolver: find real public-domain film files on archive.org."""
import json
import sys

import requests

UA = {"User-Agent": "MBM-ClippingFactory/1.0 (source acquisition)"}


def search_items(title: str):
    q = f'title:"{title}" AND mediatype:movies'
    r = requests.get(
        "https://archive.org/advancedsearch.php",
        params={"q": q, "fl[]": "identifier", "rows": "6", "output": "json"},
        headers=UA, timeout=(10, 30),
    )
    r.raise_for_status()
    docs = r.json().get("response", {}).get("docs", [])
    return [d["identifier"] for d in docs]


def best_video(identifier: str):
    try:
        d = requests.get(f"https://archive.org/metadata/{identifier}",
                         headers=UA, timeout=(10, 30)).json()
    except Exception as exc:
        return None
    server = d.get("server") or ""
    cands = []
    for f in d.get("files", []):
        name = f.get("name", "")
        fmt = (f.get("format") or "").lower()
        size = int(f.get("size") or 0)
        if not name.lower().endswith((".mp4", ".avi", ".mkv", ".ogv")):
            continue
        if size < 100 * 1024 * 1024:
            continue
        score = (0 if "512kb" in name else 1, size)
        cands.append((score, name))
    if not cands:
        return None
    cands.sort()
    name = cands[0][1]
    return {
        "url": f"https://archive.org/download/{identifier}/{name}",
        "file": name,
        "size_mb": cands[0][0][1] // (1024 * 1024),
    }


if __name__ == "__main__":
    titles = sys.argv[1:] or [
        "Carnival of Souls",
        "Night of the Living Dead 1968",
        "Dementia 13",
        "House on Haunted Hill",
        "The Cabinet of Dr. Caligari",
        "Nosferatu 1922",
    ]
    out = {}
    for t in titles:
        print(f"=== {t}")
        found = False
        try:
            for ident in search_items(t):
                v = best_video(ident)
                if v:
                    print(f"  {ident}: {v['file']} ({v['size_mb']} MB)")
                    out[t] = {"identifier": ident, **v}
                    found = True
                    break
                print(f"  {ident}: no suitable video file")
        except Exception as exc:
            print(f"  search error: {exc}")
        if not found:
            print("  NO SOURCE FOUND")
    with open("artifacts/clipping_factory/pd_source_urls.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print("\nwrote artifacts/clipping_factory/pd_source_urls.json")
