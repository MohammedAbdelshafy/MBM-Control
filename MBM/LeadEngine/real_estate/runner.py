from __future__ import annotations

import json
import sys
from pathlib import Path

from .contracts import BuyerEvidence, PropertyEvidence
from .deal_bridge import to_canonical_deal
from .offer_builder import build_offer_packet
from .underwriting import underwrite


def run_file(path: str) -> dict[str, object]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    prop = PropertyEvidence(**raw["property"])
    buyer = BuyerEvidence(**raw["buyer"]) if raw.get("buyer") else None
    uw = underwrite(
        raw["underwriting"]["arv"],
        raw["underwriting"]["repairs"],
        raw["underwriting"]["purchase_price"],
    )
    packet = build_offer_packet(prop, raw["seller"], buyer, uw, raw["offer_price"])
    deal = to_canonical_deal(packet)
    return {
        "send_state": packet.send_state,
        "email_copy": packet.email_copy,
        "whatsapp_copy": packet.whatsapp_copy,
        "manual_call_payload": packet.manual_call_payload,
        "source_provenance": packet.source_provenance,
        "underwriting": uw,
        "canonical_deal": deal.to_dict(),
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python -m MBM.LeadEngine.real_estate.runner <json-file>", file=sys.stderr)
        return 2
    print(json.dumps(run_file(sys.argv[1]), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
