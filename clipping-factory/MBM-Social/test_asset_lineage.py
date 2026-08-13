"""
test_asset_lineage -- standalone tests (python test_asset_lineage.py).
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from mbm_social import asset_lineage as al

PASS = 0
FAILURES: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAILURES
    if cond:
        PASS += 1
        print(f"  ok   {name}")
    else:
        FAILURES.append(name)
        print(f"  FAIL {name} {detail}")


TRANSCRIPT = "the lighthouse keeper heard it first, a low hum under the fog"


def test_simhash() -> None:
    print("simhash")
    a = al.simhash(TRANSCRIPT)
    b = al.simhash(TRANSCRIPT)
    check("identical text same hash", a == b)
    c = al.simhash("completely unrelated topic about fishing")
    check("different text differs", a != c)
    check("identical is near-dup", al.is_near_duplicate(a, b))
    check("different not near-dup", not al.is_near_duplicate(a, c, threshold=8))
    near = al.simhash(TRANSCRIPT.replace("fog", "fog and mist"))
    check("minor edit near-dup", al.is_near_duplicate(a, near, threshold=8))


def test_family() -> None:
    print("asset family (one source -> many assets)")
    with tempfile.TemporaryDirectory() as tmp:
        ledger = al.LineageLedger(path=Path(tmp) / "lineage.jsonl")
        src = al.record_source(ledger, "https://example.com/source-1", TRANSCRIPT, filepath="raw.mp4")
        clip = al.derive_asset(ledger, src, "clip", "clip_01.mp4", TRANSCRIPT[:120])
        reframe = al.derive_asset(ledger, clip, "vertical_reframe", "reframe_01.mp4", TRANSCRIPT[:120])
        caption = al.derive_asset(ledger, clip, "caption", "clip_01.srt", "timing file")
        check("source parent none", src.parent_asset_id is None)
        check("clip parent source", clip.parent_asset_id == src.asset_id)
        check("reframe parent clip", reframe.parent_asset_id == clip.asset_id)
        check("source_id inherited", reframe.source_id == src.source_id)
        check("kind source", src.kind == "source")

        fam = ledger.family(src.source_id)
        check("family size", len(fam) == 4)
        report = al.family_report(ledger, src.source_id)
        check("report assets", report["assets"] == 4)
        check("report kinds", report["kinds"] == ["caption", "clip", "source", "vertical_reframe"])

        try:
            al.derive_asset(ledger, src, "source", "x.mp4")
            check("cannot derive source kind", False)
        except al.LineageError:
            check("cannot derive source kind", True)

        dups = al.find_near_duplicates(ledger, TRANSCRIPT[:120])
        check("near-dup detection finds family", len(dups) >= 2)


def test_render_queue_retries() -> None:
    print("render queue + retries")
    with tempfile.TemporaryDirectory() as tmp:
        ledger = al.LineageLedger(path=Path(tmp) / "lineage.jsonl")
        src = al.record_source(ledger, "https://example.com/source-2", TRANSCRIPT)
        clip = al.derive_asset(ledger, src, "clip", "c2.mp4", TRANSCRIPT)
        job = al.enqueue_render(clip, max_retries=2, backoff_s=10.0)
        check("job queued", job.status == "queued")
        check("attempts 0", job.attempts == 0)
        al.mark_rendering(job)
        check("attempts 1", job.attempts == 1)
        al.retry_backoff(job, "render timeout")
        check("retry back to queued", job.status == "queued")
        check("backoff doubled", job.backoff_s == 20.0)
        al.mark_rendering(job)
        al.retry_backoff(job, "render timeout again")
        check("retry 2 still queued", job.status == "queued")
        al.mark_rendering(job)
        al.retry_backoff(job, "final failure")
        check("exhausted retries -> failed", job.status == "failed")
        check("error preserved", job.last_error == "final failure")

        job2 = al.enqueue_render(clip)
        al.mark_rendering(job2)
        al.complete_render(job2)
        check("complete -> done", job2.status == "done")


def test_qa_and_publication() -> None:
    print("qa + publication evidence")
    with tempfile.TemporaryDirectory() as tmp:
        ledger = al.LineageLedger(path=Path(tmp) / "lineage.jsonl")
        src = al.record_source(ledger, "https://example.com/source-3", TRANSCRIPT)
        clip = al.derive_asset(ledger, src, "clip", "c3.mp4", TRANSCRIPT)
        al.set_qa(ledger, clip.asset_id, True)
        check("qa set", ledger.get(clip.asset_id)["qa_passed"] is True)

        try:
            al.record_publication(ledger, clip.asset_id, "", "youtube", "https://youtu.be/x")
            check("publication rejects empty upload_id", False)
        except al.LineageError:
            check("publication rejects empty upload_id", True)

        al.record_publication(ledger, clip.asset_id, "VID123", "youtube", "https://youtu.be/VID123")
        row = ledger.get(clip.asset_id)
        check("evidence stored", row["publication_evidence"]["upload_id"] == "VID123")
        check("evidence verified timestamp", bool(row["publication_evidence"]["verified_iso"]))

        report = al.family_report(ledger, src.source_id)
        check("report counts published", report["published"] == 1)


def main() -> int:
    print("asset_lineage tests")
    for t in (test_simhash, test_family, test_render_queue_retries, test_qa_and_publication):
        try:
            t()
        except Exception as e:  # noqa: BLE001
            FAILURES.append(f"{t.__name__}: {e!r}")
            print(f"  FAIL {t.__name__} raised {e!r}")
    print(f"\nPASS: {PASS}  FAIL: {len(FAILURES)}")
    if FAILURES:
        for f in FAILURES:
            print("  -", f)
        return 1
    print("ALL TESTS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())