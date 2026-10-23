#!/usr/bin/env python3
"""test_activation.py — activation checks for the nvidia-free-models live lane.

Part 1 (hermetic, no network): probe() logic against a fake helper script —
  correct sentinel parse, wrong-reply skip, error skip, all-fail raise.
Part 2 (live, needs the vault-registered NVIDIA credential):
  /v1/models count, every pick_model() id present in the live catalog,
  end-to-end chat returning the exact sentinel.

Run: python3 test_activation.py
Exit 0 = all pass. Part 2 skips cleanly (exit 0, "SKIP") only if the helper
is absent; a live failure FAILS — absence of evidence is not success.
"""
import json
import os
import stat
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "bin"))

import nvidia_router  # noqa: E402
import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "nvidia_live", os.path.join(HERE, "bin", "nvidia_live.py"))
nvidia_live = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nvidia_live)

PASS, FAIL, SKIP = [], [], []


def check(name, fn):
    try:
        fn()
    except AssertionError as e:
        FAIL.append(f"{name}: {e}")
        print(f"FAIL {name}: {e}")
    except Exception as e:  # noqa: BLE001
        FAIL.append(f"{name}: {type(e).__name__}: {e}")
        print(f"FAIL {name}: {type(e).__name__}: {e}")
    else:
        PASS.append(name)
        print(f"PASS {name}")


def write_fake_helper(script_body):
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w") as f:
        f.write(script_body)
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)
    return path


# ---------- Part 1: hermetic probe logic ----------

def t_probe_picks_healthy_first():
    fake = write_fake_helper(
        "#!/usr/bin/env python3\nimport sys, json\n"
        "print(json.dumps({'model': sys.argv[3] if len(sys.argv)>3 else 'm',"
        " 'reply': 'lane live'}))\n")
    real_helper = nvidia_live.HELPER
    try:
        nvidia_live.HELPER = fake
        model, reply, tried = nvidia_live.probe(["a", "b"])
        assert model == "a" and reply == "lane live", (model, reply)
        assert tried == [], tried
    finally:
        nvidia_live.HELPER = real_helper


def t_probe_skips_wrong_reply_and_errors():
    # model 'bad' answers wrong, 'err' exits nonzero, 'good' is healthy
    fake = write_fake_helper(
        "#!/usr/bin/env python3\nimport sys, json\n"
        "m = sys.argv[3] if len(sys.argv) > 3 else ''\n"
        "sys.exit(1) if m == 'err' else print(json.dumps("
        "{'model': m, 'reply': 'nope' if m == 'bad' else 'lane live'}))\n")
    real_helper = nvidia_live.HELPER
    try:
        nvidia_live.HELPER = fake
        model, reply, tried = nvidia_live.probe(["bad", "err", "good"])
        assert model == "good", model
        assert len(tried) == 2, tried
        assert tried[0][0] == "bad" and "wrong reply" in tried[0][1]
        assert tried[1][0] == "err" and "error" in tried[1][1]
    finally:
        nvidia_live.HELPER = real_helper


def t_probe_raises_when_all_fail():
    fake = write_fake_helper(
        "#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n")
    real_helper = nvidia_live.HELPER
    try:
        nvidia_live.HELPER = fake
        try:
            nvidia_live.probe(["x", "y"])
        except nvidia_live.LiveLaneError as e:
            assert "x" in str(e) and "y" in str(e), str(e)
        else:
            raise AssertionError("expected LiveLaneError")
    finally:
        nvidia_live.HELPER = real_helper


def t_probe_nonjson_helper_raises():
    fake = write_fake_helper("#!/usr/bin/env python3\nprint('not json')\n")
    real_helper = nvidia_live.HELPER
    try:
        nvidia_live.HELPER = fake
        try:
            nvidia_live.live_chat("m", "hi")
        except nvidia_live.LiveLaneError as e:
            assert "non-JSON" in str(e), str(e)
        else:
            raise AssertionError("expected LiveLaneError")
    finally:
        nvidia_live.HELPER = real_helper


# ---------- Part 2: live checks ----------

_HELPER_MISSING = not os.path.exists(
    os.path.expanduser(
        "~/workspace/custom-connectors/custom.nvidia-nim/bin/nvidia_chat.py"))


def t_live_models_count():
    if _HELPER_MISSING:
        raise AssertionError("SKIP: connector helper absent")
    res = nvidia_live.live_models()
    assert res["count"] >= 80, f"count={res['count']}"
    assert len(res["models"]) > 0


def t_live_pick_ids_in_catalog():
    live_ids = {m["id"] for m in nvidia_router.list_models()}
    for task in ("coding", "chat", "vision", "reasoning"):
        pick = nvidia_router.pick_model(task)
        assert pick in live_ids, f"{task} pick {pick} not in live catalog"


def t_live_curated_ids_in_catalog():
    live_ids = {m["id"] for m in nvidia_router.list_models()}
    curated = json.load(open(os.path.join(HERE, "models.json")))
    missing = [m["id"] for m in curated if m["id"] not in live_ids]
    assert not missing, f"curated ids missing from live catalog: {missing}"


def t_live_chat_sentinel():
    if _HELPER_MISSING:
        raise AssertionError("SKIP: connector helper absent")
    # Free-tier inference is flaky (empty replies, timeouts) — retry a few
    # times against the proven candidate before calling it a failure.
    last = None
    for _ in range(3):
        try:
            model, reply, _tried = nvidia_live.probe(["z-ai/glm-5.3-flash"])
        except nvidia_live.LiveLaneError as e:
            last = e
            continue
        assert reply.strip() == nvidia_live.SENTINEL, (model, reply)
        return
    raise AssertionError(f"3 probe attempts failed; last: {last}")


def main():
    print("== Part 1: hermetic probe logic ==")
    for name, fn in [
        ("probe picks healthy first", t_probe_picks_healthy_first),
        ("probe skips wrong-reply + error models", t_probe_skips_wrong_reply_and_errors),
        ("probe raises when all fail", t_probe_raises_when_all_fail),
        ("non-JSON helper raises LiveLaneError", t_probe_nonjson_helper_raises),
    ]:
        check(name, fn)
    print("== Part 2: live lane ==")
    for name, fn in [
        ("live /v1/models count >= 80", t_live_models_count),
        ("every pick_model() id in live catalog", t_live_pick_ids_in_catalog),
        ("every curated models.json id in live catalog", t_live_curated_ids_in_catalog),
        ("live chat returns exact sentinel", t_live_chat_sentinel),
    ]:
        check(name, fn)
    print(f"\nRESULT: {len(PASS)} passed, {len(FAIL)} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
