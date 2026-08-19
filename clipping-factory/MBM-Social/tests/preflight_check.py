"""Pre-flight gate check for first real YouTube publication."""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

source = Path("viral_pool/viral_voice_agency_01.mp4")

from mbm_social.video_gate import validate_video_file
from mbm_social.audio_gate import validate_audio
from mbm_social.creative_gate import score_creative, CREATIVE_TIERS
from mbm_social.platform_gate import validate_platform

print("=== PRE-FLIGHT GATES ===")
print()

vg = validate_video_file(source)
print(f"VIDEO_GATE: {vg.status}")
print(f"  checks: {sum(1 for v in vg.checks.values() if v)}/{len(vg.checks)} passed")
print()

ag = validate_audio(source)
print(f"AUDIO_GATE: {ag.status}")
print(f"  checks: {sum(1 for v in ag.checks.values() if v)}/{len(ag.checks)} passed")
print()

cg = score_creative(source)
print(f"CREATIVE_GATE: {cg.status}")
print(f"  creative_score: {cg.creative_score}")
print(f"  threshold: {cg.threshold}")
print(f"  tier: {cg.tier}")
print(f"  decision: {cg.decision}")
print()

for platform in ["youtube_shorts", "instagram_reels", "tiktok"]:
    pg = validate_platform(source, platform)
    print(f"PLATFORM({platform}): {pg.status}")
print()

all_pass = vg.status == "PASS" and ag.status == "PASS" and cg.status == "PASS"
creative_ok = cg.tier in ("PUBLISH", "PREMIUM")
overall = "PASS" if all_pass and creative_ok else "FAIL"
print(f"OVERALL: {overall}")
print(f"  video={vg.status}, audio={ag.status}, creative={cg.status}")
print(f"  tier={cg.tier} (need PUBLISH or PREMIUM)")
