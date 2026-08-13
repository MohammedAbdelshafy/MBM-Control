#!/usr/bin/env python3
"""
Higgsfield-Integrated Dialer Extension
======================================
Enhances the close_queue_dialer.py with Higgsfield AI visual generation.
Integrates deal-specific imagery into call scripts and call queuing.
"""

import os
import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime


def generate_deal_visuals(prompt, model="z_image"):
    """
    Submits a generation job to Higgsfield AI CLI and returns the asset URL(s).
    """
    cmd = [
        "higgsfield", "generate", "create", model,
        "--prompt", prompt,
        "--wait"
    ]
    try:
        res = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120, shell=True
        )
        if res.returncode == 0:
            output = res.stdout.strip()
            print(f"[HIGHSFFIELD AI] Successfully generated asset: {output}")
            return output
        else:
            print(f"[HIGHSFFIELD AI] Generation warning: {res.stderr.strip()}")
            return None
    except Exception as e:
        print(f"[HIGHSFFIELD AI] Execution error: {e}")
        return None


def enrich_lead_with_visuals(lead, prompt_template="Deal Visual Theme"):
    """
    Enriches a lead with Higgsfield-generated visual assets.
    Returns a dictionary with original lead data plus generated URLs.
    """
    # Load lead data
    lead_data = lead.copy()
    
    # Generate visuals for this lead
    visual_url = generate_deal_visuals(prompt_template)
    
    if visual_url:
        lead_data["visual_url"] = visual_url
        lead_data["visual_generated_at"] = datetime.now().isoformat()
        lead_data["visual_source"] = "higgsfield_z_image"
    else:
        lead_data["visual_url"] = None
        lead_data["visual_generated_at"] = None
        lead_data["visual_source"] = "none"
    
    return lead_data


def create_enriched_lead_record(lead_id, enriched_lead):
    """
    Persists the enriched lead record to the call sheet database.
    """
    ARTIFACTS = Path(__file__).resolve().parent.parent.parent / "MBM" / "Artifacts"
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    
    # Ensure the leads database file exists
    leads_db = ARTIFACTS / "mbm-dialer" / "app" / "public" / "leads_database.json"
    if not leads_db.exists():
        print(f"[HIGHSFFIELD DAILER] Creating new leads database at {leads_db}")
    
    # Load existing leads
    if leads_db.exists():
        with open(leads_db, "r", encoding="utf-8") as f:
            leads = json.load(f)
    else:
        leads = []
    
    # Find or create the lead
    lead = next((l for l in leads if l.get("id") == lead_id), None)
    if not lead:
        lead = {
            "id": lead_id,
            "name": "Unnamed Lead",
            "contact": "unknown",
            "phone": "",
            "company": "Unknown Company",
            "vertical": "General",
            "details": {},
            "Call_Script": ""
        }
        leads.append(lead)
    
    # Enrich with visuals
    enriched = enrich_lead_with_visuals(lead)
    
    # Save back
    with open(leads_db, "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, ensure_ascii=False)
    
    print(f"[HIGHSFFIELD DAILER] Lead {lead_id} enriched with visuals")
    return enriched


def generate_call_script_with_visuals(lead, offer_text=None):
    """
    Generates a personalized call script incorporating visual theme info.
    """
    # Determine vertical tag for script
    vertical = lead.get("vertical", "General").strip()
    
    # Build offer text
    if offer_text is None:
        offer_text = (
            "We buy houses as-is with a 7-day cash close, zero agent fees, "
            "and we cover all closing costs."
        )
    
    # Build the script with visual theme mention
    script_lines = [
        "=" * 80,
        f"⭐ THE MASTER SCRIPT: {lead.get('company', 'Your Practice')} ⭐",
        "=" * 80,
        "",
        "[PROSPECT DETAILS]",
        f"👤 Name: {lead.get('contact', 'unknown')}",
        f"🏥 Practice: {lead.get('company', 'Unknown Company')}",
        f"📞 Phone: {lead.get('phone', '')}",
        f"💉 Vertical: {vertical}",
        "",
        "[1. THE PATTERN INTERRUPT]",
        "Hey {contact}, this is Mohammed. I know I'm catching you entirely off guard right now... do you have 30 seconds for me to tell you why I called, and you can hang up if you hate it?",
        "",
        "[2. THE HOOK]",
        "I run a patient-acquisition engine specifically for {vertical} clinics in your area. I have a list of verified local patients looking for treatment, but my current partner clinic is fully booked. Are you currently taking on new patients at {lead.get('company', 'your practice')}?",
        "",
        "[3. THE QUALIFICATION]",
        "Perfect. We don't sell marketing. We physically drop pre-qualified, cash-ready patients directly into your schedule, and we handle all the no-show follow-ups.",
        "",
        "[4. THE CLOSE (RISK REVERSAL)]",
        f"Our {offer_text} is $497/mo, but here's the catch: I don't want you to pay me a single cent until after our first onboarding call, when you physically see the system working.",
        "If it doesn't make sense, we walk away. Sound fair enough to just take a look?",
        "",
        "--- END OF SCRIPT ---",
    ]
    
    return "\n".join(script_lines)


def main():
    """Main entry point for the Higgsfield-enhanced dialer."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Higgsfield-Integrated Dialer")
    parser.add_argument("--dry-run", action="store_true", help="Queue only (no live calls)")
    parser.add_argument("--live", action="store_true", help="Run interactive manual dialer")
    parser.add_argument("--limit", type=int, default=None, help="Max leads to dial")
    parser.add_argument("--sheet", default=None, help="Override call sheet path")
    parser.add_argument("--prompt", default="Deal Visual Theme", help="Prompt for Higgsfield image generation")
    
    args = parser.parse_args()
    
    # Load call sheet
    BASE = Path(__file__).resolve().parent
    ARTIFACTS = BASE.parent.parent / "MBM" / "Artifacts"
    LOGS = BASE / "logs"
    CALLSHEET = ARTIFACTS / "npi_verified_callsheet.csv"
    
    if not CALLSHEET.exists():
        print(f"[ERROR] Call sheet not found: {CALLSHEET}")
        print("Run npi_verified_callsheet.py first to generate the call sheet.")
        sys.exit(1)
    
    # Load leads
    if not LOGS.exists():
        print("[INFO] No disposition logs found. Starting fresh.")
    else:
        with open(CALLSHEET, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    
    if not rows:
        print("[WARN] No leads loaded from call sheet.")
        sys.exit(0)
    
    # Display leads
    print(f"\n=== TOP {min(args.limit or 15)} DIALABLE LEADS ===\n")
    for i, row in enumerate(rows[:args.limit], 1):
        print(f"{i:>3} | Priority: {row.get('priority', '')} | "
              f"Phone: {row.get('phone', '')} | "
              f"Company: {row.get('company_name', '')} | "
              f"Vertical: {row.get('vertical_tag', '')}")
    
    # Process each lead
    for row in rows:
        lead_id = row.get("id", "")
        
        # Enrich with visuals
        enriched = create_enriched_lead_record(lead_id, row)
        
        # Generate script with visual theme
        offer_text = enriched.get("Call_Script", {}).get("offer", None)
        if not offer_text:
            offer_text = "We buy houses as-is with a 7-day cash close, zero fees, and cover all closing costs."
        
        script = generate_call_script_with_visuals(enriched, offer_text)
        
        # Record disposition (even if dry-run)
        if args.dry_run:
            print(f"[DRY-RUN] Would record: {row.get('phone', '')} -> {script.split(chr(10))[-1].strip()}")
        elif args.live:
            print(f"\n[INTERACTIVE] Calling {row.get('phone', '')}...")
            # In a real implementation, this would call the Twilio bridge
            # For now, we just simulate recording the call
            print(f"[SIMULATED] Script sent to {row.get('company', '')}")
        else:
            print(f"\n[LIVE] Calling {row.get('phone', '')}...")
            print(f"Script: {script}")
    
    print("\n✓ Higgsfield-enhanced dialer completed.")


if __name__ == "__main__":
    main()