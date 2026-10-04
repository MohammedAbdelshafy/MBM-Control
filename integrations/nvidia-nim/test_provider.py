#!/usr/bin/env python3
"""test_provider.py — verify the NVIDIA NIM provider wiring WITHOUT an API key.

Checks:
  1. Base URL is reachable: live GET /v1/models -> HTTP 200, models listed.
  2. The model catalog loads and is non-empty.
  3. swarm.models.yaml parses (minimal stdlib parser — no pyyaml needed).
  4. Config schema valid: provider base_url / api_key_env / protocol present.
  5. Every routed model id exists in the live catalog.

Run:  python3 mbm-control/nvidia-nim/test_provider.py
Exit 0 = all checks pass. Any failure prints FAIL and exits 1.
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
EXPECTED_BASE_URL = "https://integrate.api.nvidia.com/v1"
EXPECTED_KEY_ENV = "NVIDIA_API_KEY"

failures = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        failures.append(name)


def live_models():
    req = urllib.request.Request(
        EXPECTED_BASE_URL + "/models",
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        code = resp.status
        data = json.loads(resp.read().decode("utf-8"))
    return code, [m["id"] for m in data.get("data", []) if m.get("id")]


def load_catalog():
    """Prefer the real saved catalog; fall back to the curated models.json."""
    candidates = [
        os.path.expanduser("~/workspace/night-shift/nvidia_models_2026-10-04.json"),
        os.path.join(HERE, "..", "..", "models.json"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "data" in data:
                return [m["id"] for m in data["data"] if m.get("id")], path
            if isinstance(data, list):
                ids = [m["id"] if isinstance(m, dict) else m for m in data]
                return ids, path
    return None, None


def parse_simple_yaml(path):
    """Minimal parser for the flat provider/routing/defaults mapping format."""
    cfg = {}
    section = None
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.rstrip("\n")
            if not line.strip() or line.strip().startswith("#"):
                continue
            if not line.startswith((" ", "\t")) and line.rstrip().endswith(":"):
                section = line.strip()[:-1]
                cfg[section] = {}
                continue
            if ":" in line and section is not None:
                k, v = line.strip().split(":", 1)
                cfg[section][k.strip()] = v.strip()
    return cfg


def main():
    print("== NVIDIA NIM provider wiring test (no API key required) ==\n")

    # 1. base URL reachable, public model list
    try:
        code, ids = live_models()
    except Exception as e:  # noqa: BLE001 — report, don't crash
        check("live GET /v1/models reachable", False, str(e))
        ids, code = [], None
    else:
        check("live GET /v1/models returns HTTP 200", code == 200, f"HTTP {code}")
        check("live catalog non-empty", len(ids) > 0, f"{len(ids)} models")
        print(f"       sample ids: {', '.join(ids[:3])}")

    # 2. catalog loads
    cat_ids, cat_path = load_catalog()
    check("model catalog loads", bool(cat_ids),
          f"{len(cat_ids)} ids from {cat_path}" if cat_ids else "no catalog found")

    # 3+4. routing table parses, schema valid
    yaml_path = os.path.join(HERE, "swarm.models.yaml")
    try:
        cfg = parse_simple_yaml(yaml_path)
        parsed = True
    except Exception as e:  # noqa: BLE001
        parsed = False
        cfg = {}
        print(f"[FAIL] swarm.models.yaml parses — {e}")
        failures.append("swarm.models.yaml parses")
    if parsed:
        check("swarm.models.yaml parses", True, yaml_path)
        prov = cfg.get("provider", {})
        check("provider.base_url correct",
              prov.get("base_url") == EXPECTED_BASE_URL, prov.get("base_url", ""))
        check("provider.api_key_env correct",
              prov.get("api_key_env") == EXPECTED_KEY_ENV, prov.get("api_key_env", ""))
        check("provider.protocol openai-compatible",
              prov.get("protocol") == "openai-compatible", prov.get("protocol", ""))

        # 5. every routed id exists in the catalog
        routing = cfg.get("routing", {})
        check("routing table non-empty", len(routing) > 0,
              f"tasks: {', '.join(sorted(routing))}")
        catalog_set = set(cat_ids or [])
        live_set = set(ids)
        for task, mid in sorted(routing.items()):
            in_either = mid in catalog_set or mid in live_set
            check(f"routing[{task}] id in catalog", in_either, mid)

    print()
    if failures:
        print(f"RESULT: {len(failures)} check(s) FAILED: {failures}")
        return 1
    print("RESULT: all provider wiring checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
