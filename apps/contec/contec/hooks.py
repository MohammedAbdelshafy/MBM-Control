"""Contec custom app hooks.

D-004: ALL Contec logic lives here; zero vendor edits.
Real Estate AI Media vertical: doc_events enforce dedup + opt-out guards.
"""
app_name = "contec"

doc_events = {
    ("Lead",): {},  # reserved: RE-agent custom-field guards when app installed
}

# Real Estate AI Media doctypes (installed with the app; see apps/contec/contec/doctype)
RE_MEDIA_DOCTYPES = [
    "Real Estate Agent",
    "Property Sample",
    "Fulfillment Job",
    "RE Media Settings",
]

RE_MEDIA_CAMPAIGN = "CONTEC_REAL_ESTATE_AI_MEDIA"
