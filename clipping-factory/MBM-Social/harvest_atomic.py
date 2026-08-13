"""Launch real Chrome with CDP port, wait for it, then harvest channels - atomically."""
import json, subprocess, sys, time, urllib.request
from pathlib import Path

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = r"C:\Users\omare\AppData\Local\Google\Chrome\User Data"
CDP = "http://127.0.0.1:9222"

def port_up(timeout=45):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(CDP + "/json/version", timeout=2) as r:
                return json.loads(r.read())
        except Exception:
            time.sleep(2)
    return None

def main():
    subprocess.Popen([
        CHROME,
        "--remote-debugging-port=9222",
        f"--user-data-dir={PROFILE}",
        "--profile-directory=Default",
        "--no-first-run",
        "https://studio.youtube.com/",
    ])
    ver = port_up()
    if not ver:
        print("PORT NEVER CAME UP")
        sys.exit(2)
    print("CDP UP:", ver.get("Browser"))

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "ytcdp", Path(__file__).resolve().parent / "mbm_social" / "youtube_cdp_publisher.py")
    yt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(yt)

    out = {}
    for brand in ["dontwatchthis", "goalmachinez", "cutedosage", "clippingfactorymbm", "twistsrevealed"]:
        print(f"\n=== {brand} ===")
        try:
            info = yt.get_current_channel(CDP)
        except Exception as e:
            print("  err:", e)
            info = None
        if info is None:
            print("  no channel data")
            continue
        print("  ", info)
        out[brand] = info

    dest = Path(__file__).resolve().parent / "harvested_channels.json"
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\nSaved:", dest)

if __name__ == "__main__":
    main()