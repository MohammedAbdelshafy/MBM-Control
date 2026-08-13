"""Harvest REAL channel identity from live native Chrome via CDP for every brand.

Usage:
  python harvest_channels.py [cdp_url]
Writes MBM_Social/harvested_channels.json (brand -> {channel_id, name, handle, url}).
This is the fix for the fabricated UC_DONTWATCHTHIS1 channel ids in the registry.
"""
import json, sys, time
from pathlib import Path
import importlib.util

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

spec = importlib.util.spec_from_file_location("ytcdp", HERE / "mbm_social" / "youtube_cdp_publisher.py")
yt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(yt)

BRANDS = ["dontwatchthis", "goalmachinez", "cutedosage", "clippingfactorymbm", "twistsrevealed"]
CDP = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:9222"

out = {}
for brand in BRANDS:
    print(f"\n=== {brand} ===")
    info = yt.get_current_channel(CDP)
    if info is None:
        print("  CDP unavailable -- is Chrome running with --remote-debugging-port=9222?")
        continue
    print("  ", info)
    out[brand] = info

dest = HERE / "harvested_channels.json"
dest.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"\nSaved: {dest}")