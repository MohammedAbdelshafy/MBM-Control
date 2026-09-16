"""CONTEC CAPABILITY GRAPH.

Machine-readable inventory of what Contec ALREADY has, with evidence paths
inside this repository. The radar matches every opportunity against this graph
and emits an implementation delta (reuse levels + missing capabilities).

Every entry below was verified against the live repository during the
2026-08-26 recovery audit. Do not add aspirational entries.
"""
from __future__ import annotations

from typing import Any, Dict, List


CAPABILITIES: Dict[str, Dict[str, Any]] = {
    "clipping_factory": {
        "name": "Clipping Factory",
        "sub_capabilities": [
            "video_ingestion", "source_verification_pd", "ai_scripting",
            "tts_voiceover", "short_form_rendering", "captions_burn_in",
            "technical_qa", "creative_qa", "virality_scoring",
            "beat_aligned_visuals", "publish_packaging",
        ],
        "evidence": [
            "clipping-factory/clipping_factory/full_cycle.py",
            "clipping-factory/clipping_factory/production_pipeline.py",
            "clipping-factory/clipping_factory/virality_engine.py",
        ],
    },
    "social_publishing": {
        "name": "MBM Social Publishing",
        "sub_capabilities": [
            "youtube_api_upload_oauth", "post_publish_verification",
            "multi_brand_registry", "paced_publishing_gate",
            "instagram_manual_playwright", "tiktok_manual_playwright",
        ],
        "evidence": [
            "clipping-factory/MBM-Social/mbm_social/post_orchestrator.py",
            "clipping-factory/MBM-Social/mbm_social/youtube_api_publisher.py",
            "clipping-factory/MBM-Social/mbm_social/platform_registry.py",
        ],
        "limits": ["instagram_no_post_id_verification", "tiktok_no_post_id_verification",
                   "linkedin_missing", "facebook_missing"],
    },
    "lead_factory": {
        "name": "Lead Engine / Lead Factory",
        "sub_capabilities": [
            "npi_registry_discovery", "phone_verification_gate", "dedupe_hygiene",
            "seller_skip_trace", "callsheet_generation", "suppression_optout",
        ],
        "evidence": [
            "MBM/LeadEngine/npi_verified_callsheet.py",
            "MBM/LeadEngine/dialer_verification_gate.py",
            "MBM/Scripts/lead_hygiene.py",
        ],
    },
    "dialer": {
        "name": "Dialer / Outreach Rail",
        "sub_capabilities": [
            "ranked_dial_lists", "call_scripts_segments", "followup_cascade",
            "phound_sms_wave", "outcome_dispositions", "single_writer_lock",
        ],
        "evidence": [
            "MBM/LeadEngine/close_queue_dialer.py",
            "MBM/LeadEngine/phound_wave_campaign.py",
            "MBM/GLM/single_writer_lock.py",
        ],
    },
    "crm_pipeline": {
        "name": "CRM / Pipeline State",
        "sub_capabilities": ["leads_database", "disposition_tracking", "comments_log"],
        "evidence": ["mbm-dialer/app/public/leads_database.json",
                     "MBM/GLM/single_writer_lock.py"],
    },
    "ai_video_factory": {
        "name": "AI Video Generation",
        "sub_capabilities": ["higgsfield_provider_optional", "nano_banana_engine",
                             "seedance_engine", "motion_backgrounds",
                             "local_ffmpeg_fallback"],
        "evidence": [
            "clipping-factory/clipping_factory/providers/higgsfield_provider.py",
            "clipping-factory/MBM-Social/nano_banana_2_engine.py",
            "clipping-factory/MBM-Social/seedance_video_engine.py",
        ],
        "limits": ["higgsfield_requires_credentials_optional"],
    },
    "voice_tts": {
        "name": "Voice / TTS",
        "sub_capabilities": ["edge_tts_neural", "windows_sapi_offline_fallback",
                             "multilingual_voices"],
        "evidence": ["clipping-factory/clipping_factory/tts_agent.py"],
    },
    "monetization_rails": {
        "name": "Checkout / Monetization",
        "sub_capabilities": ["neteller_link_builders_py_node_js", "whop_storefront",
                             "whop_webhooks_hmac"],
        "evidence": ["MBM/Scripts/neteller_config.py", "server/neteller.js",
                     "MBM/Whop/whop_monetize.py"],
    },
    "automation_orchestration": {
        "name": "Automation / Ops Intelligence",
        "sub_capabilities": ["glm_swarm_audit", "mission_routing", "scheduled_tasks_windows",
                             "github_actions_ci", "heartbeat_ledger_observability"],
        "evidence": ["MBM/GLM/orchestrator.py", ".github/workflows/",
                     "clipping-factory/clipping_factory/heartbeat.py"],
    },
    "property_intelligence": {
        "name": "Property Intelligence",
        "sub_capabilities": ["auction_pipeline", "county_ownership_verify",
                             "deal_scoring_reason_traces"],
        "evidence": ["MBM/LeadEngine/property_intel/"],
    },
}

# Keyword -> (capability, reuse level) mapping used by the matcher.
_DOMAIN_HINTS: List[Dict[str, Any]] = [
    {"keywords": ["realtor", "real estate", "listing", "property", "brokerage", "mortgage"],
     "capability": "property_intelligence", "level": "HIGH"},
    {"keywords": ["realtor", "real estate", "listing", "property", "brokerage"],
     "capability": "lead_factory", "level": "HIGH"},
    {"keywords": ["video", "reel", "short", "render", "editing", "clip"],
     "capability": "clipping_factory", "level": "HIGH"},
    {"keywords": ["ai video", "image to video", "avatar", "generated video"],
     "capability": "ai_video_factory", "level": "HIGH"},
    {"keywords": ["voiceover", "dubbing", "translation", "multilingual", "tts"],
     "capability": "voice_tts", "level": "HIGH"},
    {"keywords": ["youtube", "publishing", "channel", "posting"],
     "capability": "social_publishing", "level": "HIGH"},
    {"keywords": ["outbound", "cold call", "dials", "sms", "campaign"],
     "capability": "dialer", "level": "HIGH"},
    {"keywords": ["leads", "prospecting", "scraping businesses", "contact list"],
     "capability": "lead_factory", "level": "HIGH"},
    {"keywords": ["checkout", "payment", "sell course", "storefront"],
     "capability": "monetization_rails", "level": "HIGH"},
]


def match_opportunity(text: str) -> Dict[str, Any]:
    """Return {capability: level} reuse map + explicit missing deltas."""
    t = (text or "").lower()
    levels: Dict[str, str] = {}
    for hint in _DOMAIN_HINTS:
        if any(k in t for k in hint["keywords"]):
            cap = hint["capability"]
            prev = levels.get(cap)
            order = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
            if prev is None or order[hint["level"]] > order[prev]:
                levels[cap] = hint["level"]
    # Baseline: sales machinery applies to nearly every B2B opportunity.
    for base_cap in ("lead_factory", "dialer", "crm_pipeline"):
        levels.setdefault(base_cap, "HIGH" if base_cap != "crm_pipeline" else "MEDIUM")
    return {"reuse_scores": levels,
            "missing_capabilities": [],   # filled by domain packs below
            "capabilities_used": CAPABILITIES}


def implementation_delta(reuse_scores: Dict[str, str],
                         required_sub_capabilities: List[str]) -> List[str]:
    """Sub-capabilities required by the opportunity that no capability covers."""
    covered = set()
    for cap_id, level in reuse_scores.items():
        if level in ("HIGH", "MEDIUM"):
            covered.update(CAPABILITIES.get(cap_id, {}).get("sub_capabilities", []))
    return [s for s in required_sub_capabilities if s not in covered]
