"""Deterministic, side-effect-free MBM digital-product pack builder.

The factory reads an offer directory and produces a customer-safe package.
Private payment manifests and internal outreach assets never enter the pack.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

PRIVATE_MANIFESTS = {"neteller_manifest.json"}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _public_payment(whop: dict[str, Any]) -> dict[str, Any]:
    items = whop.get("items", {})
    public_items: dict[str, Any] = {}
    if isinstance(items, dict):
        for item_id, item in items.items():
            if not isinstance(item, dict):
                continue
            public_items[item_id] = {
                key: item[key]
                for key in ("amount", "billing_type", "label", "checkout_url")
                if key in item
            }
    return {"currency": whop.get("currency"), "items": public_items}


def load_offer(offer_dir: Path) -> dict[str, Any]:
    offer_dir = Path(offer_dir)
    if not offer_dir.is_dir():
        raise FileNotFoundError(f"Offer directory not found: {offer_dir}")

    landing = offer_dir / "landing.html"
    whop = offer_dir / "whop_manifest.json"
    delivery = offer_dir / "delivery"
    whop_data: dict[str, Any] = _load_json(whop) if whop.exists() else {}
    items = whop_data.get("items", {})
    payment_ready = isinstance(items, dict) and any(
        isinstance(item, dict) and bool(item.get("checkout_url"))
        for item in items.values()
    )
    delivery_files = sorted(
        path.relative_to(offer_dir).as_posix()
        for path in delivery.rglob("*")
        if path.is_file() and path.stat().st_size > 0
    ) if delivery.is_dir() else []

    return {
        "offer": whop_data.get("offer", offer_dir.name),
        "engineering_ready": landing.is_file() and whop.is_file(),
        "delivery_ready": bool(delivery_files),
        "payment_ready": payment_ready,
        "customer_ready": landing.is_file() and whop.is_file() and bool(delivery_files) and payment_ready,
        "commercially_validated": False,
        "public_payment": _public_payment(whop_data),
        "delivery_files": delivery_files,
    }


def build_customer_pack(offer_dir: Path, output_dir: Path) -> dict[str, Any]:
    offer_dir = Path(offer_dir)
    output_dir = Path(output_dir)
    state = load_offer(offer_dir)
    if not state["delivery_ready"]:
        raise ValueError("Offer has no non-empty delivery assets")

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

    files: list[str] = []
    for rel in state["delivery_files"]:
        source = offer_dir / rel
        destination = output_dir / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        files.append(rel)

    catalog = {
        "schema_version": "1.0",
        "offer": state["offer"],
        "factory": "MBM Digital Product Factory",
        "delivery": {"files": files},
        "payment": state["public_payment"],
        "commercially_validated": False,
        "external_side_effects": "blocked",
        "private_payment_manifests_excluded": sorted(PRIVATE_MANIFESTS),
    }
    (output_dir / "catalog.json").write_text(
        json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    files.append("catalog.json")
    return {"offer": state["offer"], "files": files, "customer_ready": state["customer_ready"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a customer-safe MBM digital-product pack")
    parser.add_argument("offer_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    result = build_customer_pack(args.offer_dir, args.output_dir)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
