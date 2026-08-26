"""Whitelisted API entry points (thin; heavy logic in real_estate_media).

Only callable after the app is bench-installed on a site. Guards follow
D-019: no financial posting, no autonomous deletion.
"""
from __future__ import annotations

import json

import frappe
from frappe import _


@frappe.whitelist()
def route_agent(agent: str) -> dict:
    """Qualify + route one Real Estate Agent into the campaign queue."""
    from .real_estate_media.automation import qualify_and_route

    doc = frappe.get_doc("Real Estate Agent", agent)
    settings = frappe.get_single("RE Media Settings").as_dict()
    existing = frappe.get_all("Real Estate Agent",
                              filters={"name": ("!=", agent)},
                              fields=["*"])
    result = qualify_and_route(
        doc.as_dict(), settings=dict(settings),
        existing_agents=existing,
        enqueue_dialer=lambda payload: frappe.enqueue(
            "contec.api.export_dialer_row", queue="short", payload=json.dumps(payload, default=str)),
    )
    return result


@frappe.whitelist()
def export_dialer_row(payload: str) -> None:
    """Emit one CONTEC_REAL_ESTATE_AI_MEDIA row for the MBM telephony bridge."""
    row = json.loads(payload)
    frappe.logger("re_media").info({"campaign": "CONTEC_REAL_ESTATE_AI_MEDIA",
                                    "dialer_row": row})


@frappe.whitelist()
def generate_sample(agent: str, listing_id: str) -> dict:
    """GENERATE_PROPERTY_SAMPLE with duplicate + limit guards."""
    from .real_estate_media.sample_store import (
        build_sample_record, generation_limit_reached, is_duplicate_sample,
    )

    settings = frappe.get_single("RE Media Settings").as_dict()
    existing = frappe.get_all("Property Sample",
                              filters={"agent_id": agent}, fields=["*"])
    if is_duplicate_sample(existing, listing_id, agent):
        return {"blocked": True, "reason": "duplicate_sample"}
    if generation_limit_reached(len(existing), dict(settings)):
        return {"blocked": True, "reason": "generation_limit"}

    agent_doc = frappe.get_doc("Real Estate Agent", agent).as_dict()
    # Listing assets must be supplied by the operator/importer; we never scrape
    # private assets. Missing assets -> honest BLOCKED record.
    images = []
    record = build_sample_record(agent_doc,
                                 {"listing_id": listing_id},
                                 images, settings=dict(settings))
    return {"blocked": False, "record": record}


@frappe.whitelist()
def dashboard() -> dict:
    from .real_estate_media.analytics import dashboard_counts

    agents = frappe.get_all("Real Estate Agent", fields=["*"])
    samples = frappe.get_all("Property Sample", fields=["*"])
    jobs = frappe.get_all("Fulfillment Job", fields=["*"])
    won = [j for j in jobs if j.get("status") == "DELIVERED" and j.get("quoted_price")]
    return dashboard_counts(agents=agents, samples=samples, call_events=[],
                            quotes=[], won=won, production_events=[])
