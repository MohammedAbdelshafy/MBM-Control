"""CLI for turning a factory quota JSON file into buyer-search briefs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .search_spec import build_search_spec


def main() -> int:
    parser = argparse.ArgumentParser(description="Build evidence-first buyer search specs.")
    parser.add_argument("quota_json", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = json.loads(args.quota_json.read_text(encoding="utf-8"))
    specs = [build_search_spec(item) for item in payload]
    rendered = json.dumps(specs, ensure_ascii=False, indent=2)

    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
