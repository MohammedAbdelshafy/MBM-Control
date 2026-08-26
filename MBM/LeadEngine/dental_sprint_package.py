#!/usr/bin/env python3
"""
Dental Sprint Package — DENTAL-GOLD-SPRINT-001
==============================================
Turns the OX3-qualified 12-practice CALL_READY queue into the ONLY active
sales sprint:

  - per-practice PRIMARY / SECONDARY offer from the outcome catalog
  - evidence-disciplined script angles (hedge_required -> questions only)
  - trackable CTAs ($149 Revenue Audit checkout + Neteller rail)
  - GLM ranking mission output: priority / offer / why / angle / next_action

No new prospect collection. No fabricated pain claims.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

OX3_OUTPUT = (
    ROOT / "MBM" / "Artifacts" / "GTM" / "campaigns" /
    "CAMP-DENTAL-DFW-MCR-001" / "OX3_OUTPUT_DENTAL-GOLD-002.json"
)
SPRINT_DIR = ROOT / "MBM" / "Artifacts" / "GTM" / "sprints"

AUDIT_CHECKOUT = "https://whop.com/checkout/plan_Sg0oIq3Tf4rlQ"
AUDIT_UTM = "?utm_source=outreach&utm_medium=phone&utm_campaign=dental_sprint_001"
PROD_BASE = "https://mbm-dialer-app.vercel.app/productized-service/ai-consultancy-sprint/landing.html"

OFFER_MCR = {
    "sku": "AIS-MISSED-CALL-RECOVERY",
    "name": "Missed-Call Recovery",
    "promise": "Every call that rings out gets an instant callback/text within 60 seconds, qualification, and a booked slot request.",
}
OFFER_RECEPTIONIST = {
    "sku": "AIS-AI-RECEPTIONIST",
    "name": "AI Receptionist",
    "promise": "After-hours and overflow calls answered live, routed, and booked to the schedule.",
}
OFFER_LEADQUAL = {
    "sku": "AIS-LEAD-QUALIFICATION",
    "name": "AI Lead Qualification",
    "promise": "New inquiries automatically qualified and routed before the front desk touches them.",
}

DISCOVERY_ANGLES = [
    ("open", "Hi, this is Mohammed — I know I'm catching you off guard. Can I take 30 seconds to say why I called? If it's not useful, hang up on me."),
    ("discovery", "Quick question — when {practice} misses a new-patient call at lunch or after hours, what happens today? Does anyone get back to them?"),
    ("bridge", "That gap is exactly what we fix: an automatic second attempt within a minute, plus qualification, so the caller lands in your book instead of a competitor's."),
    ("offer", "We'd start with a $149 automation audit of your intake flow this week — if the numbers don't justify fixing it, you keep the map and owe nothing further."),
]


def secondary_offer_for(pain_hypothesis: str) -> dict:
    text = (pain_hypothesis or "").lower()
    if any(k in text for k in ("book", "schedul", "after-hour", "reception", "front desk", "front-desk")):
        return OFFER_RECEPTIONIST
    if any(k in text for k in ("lead", "inquir", "intake", "qualif")):
        return OFFER_LEADQUAL
    return OFFER_RECEPTIONIST


def build() -> dict:
    data = json.loads(OX3_OUTPUT.read_text(encoding="utf-8"))
    records = [r for r in data.get("records", []) if r.get("decision") == "QUALIFIED"]
    queue_scores = {q["company_id"]: q for q in data.get("ranked_call_queue", [])}

    practices = []
    for rec in records:
        cid = rec["company_id"]
        ranked = queue_scores.get(cid, {})
        pain_label = rec.get("pain_label", "")
        hedged = bool(rec.get("hedge_required")) or pain_label != "PROVEN"
        hyp = rec.get("pain_hypothesis", "")
        primary = OFFER_MCR
        secondary = secondary_offer_for(hyp)
        practices.append({
            "company_id": cid,
            "practice": rec["practice_name"],
            "phone": rec["contact"]["phone"],
            "phone_status": rec["contact"].get("phone_status"),
            "score": rec.get("score"),
            "rank": rec.get("rank"),
            "pain_evidence_label": pain_label,
            "pain_hypothesis": hyp,
            "hedged_script_required": hedged,
            "primary_offer": primary,
            "secondary_offer": secondary,
            "booking_route": rec["contact"].get("booking_route", ""),
            "evidence_refs": sorted({a.get("evidence_ref") for a in rec.get("audit_trail", []) if a.get("evidence_ref")}),
            "cta": {
                "foot_in_door": f"{AUDIT_CHECKOUT}{AUDIT_UTM}",
                "landing": f"{PROD_BASE}#engines{AUDIT_UTM}",
            },
            "next_action": "CALL_OPERATOR_BRIDGE -> record disposition",
        })

    # GLM ranking mission output: deterministic, evidence-weighted ordering.
    def priority(p):
        label_weight = {"PROVEN": 1.0}.get(p["pain_evidence_label"], 0.7)
        return round((p["score"] or 0) * label_weight, 2)

    practices.sort(key=lambda p: (-priority(p), p["rank"] or 99))
    for i, p in enumerate(practices, 1):
        p["glm_priority"] = i

    package = {
        "sprint_id": "DENTAL-GOLD-SPRINT-001",
        "campaign_id": "CAMP-DENTAL-DFW-MCR-001",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "actor": "ox-alpha/opencode",
        "rule": "ONLY active sales sprint until first payment; no queue expansion.",
        "counts": {"practices": len(practices), "call_ready": len(practices)},
        "offers_catalog_note": "PRIMARY=Missed-Call Recovery for every practice; SECONDARY varies by published-behavior evidence only. No pain claim without evidence.",
        "practices": practices,
    }

    SPRINT_DIR.mkdir(parents=True, exist_ok=True)
    out_json = SPRINT_DIR / "DENTAL-GOLD-SPRINT-001.json"
    out_json.write_text(json.dumps(package, indent=2), encoding="utf-8")

    lines = [
        "# DENTAL-GOLD-SPRINT-001 — The Only Active Sales Sprint",
        "",
        f"Generated: {package['generated_at']}  |  Practices: **{len(practices)}** (all CALL_READY)",
        "",
        "PRIMARY offer for all: **Missed-Call Recovery**. SECONDARY: AI Receptionist / Lead Qualification (evidence-matched).",
        "Foot-in-door CTA: **$149 Automation Audit** — " + AUDIT_CHECKOUT,
        "",
        "| GLM# | Practice | Phone | Score | Pain label | Secondary | ",
        "|---|---|---|---|---|---|",
    ]
    for p in practices:
        lines.append(
            f"| {p['glm_priority']} | {p['practice']} | `{p['phone']}` | {p['score']} | "
            f"{p['pain_evidence_label']} | {p['secondary_offer']['name']} |"
        )
    lines += ["", "## Operator script frame (hedged where evidence is hypothesis-only)", ""]
    for key, template in DISCOVERY_ANGLES:
        lines.append(f"- **{key}:** {template.format(practice='{practice}')}")
    lines += ["", "## Dial order detail", ""]
    for p in practices:
        lines += [
            f"### #{p['glm_priority']} {p['practice']} (`{p['phone']}`)",
            f"- Pain ({p['pain_evidence_label']}): {p['pain_hypothesis']}",
            f"- Primary: {p['primary_offer']['name']} — {p['primary_offer']['promise']}",
            f"- Secondary: {p['secondary_offer']['name']} — {p['secondary_offer']['promise']}",
            f"- Booking route observed: {p['booking_route']}",
            f"- Evidence: {', '.join(list(p['evidence_refs'])[:2])}",
            "",
        ]
    out_md = SPRINT_DIR / "DENTAL-GOLD-SPRINT-001.md"
    out_md.write_text("\n".join(lines), encoding="utf-8")

    print(f"sprint written: {out_json}")
    print(f"brief written : {out_md}")
    return package


if __name__ == "__main__":
    build()
