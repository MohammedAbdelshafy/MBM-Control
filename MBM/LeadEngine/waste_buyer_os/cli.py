"""CLI for turning a factory quota JSON file into buyer-search briefs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import FactoryWasteQuota
from .search_spec import build_search_spec


def _load_quotas(path: Path) -> list[FactoryWasteQuota]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("quota JSON must contain a list of waste-stream objects")

    quotas: list[FactoryWasteQuota] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"quota entry {index} must be an object")
        evidence = item.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValueError(f"quota entry {index} evidence must be a list")
        item = dict(item)
        item["evidence"] = tuple(str(value) for value in evidence)
        quota = FactoryWasteQuota(**item)
        errors = quota.validate()
        if errors:
            raise ValueError(f"quota entry {index}: {'; '.join(errors)}")
        quotas.append(quota)
    return quotas


def main() -> int:
    parser = argparse.ArgumentParser(description="Build evidence-first buyer search specs.")
    parser.add_argument("quota_json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    specs = [build_search_spec(quota) for quota in _load_quotas(args.quota_json)]
    rendered = json.dumps(specs, ensure_ascii=False, indent=2)

    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
