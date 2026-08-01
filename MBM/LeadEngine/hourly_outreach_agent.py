import time
import os
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

# Add current path to sys.path
BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent.parent.resolve()
sys.path.append(str(BASE_DIR))

from revenue_tracker import RevenueTracker
from revenue_seeker import RevenueSeeker
from revenue_enforcer import RevenueEnforcer
from campaign_grabber_agent import CampaignsGrabberAgent

LOG_FILE = BASE_DIR / 'logs' / 'hourly_agent.log'
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[HOURLY OUTREACH AGENT] {timestamp} - {msg}"
    try:
        print(log_line)
    except UnicodeEncodeError:
        print(log_line.encode('ascii', errors='replace').decode('ascii'))
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_line + '\n')

def run_hourly_cycle():
    log("============================================================")
    log("=== STARTING HOURLY REVENUE, OUTREACH, VIDEO & POSTING CYCLE ===")
    log("============================================================")

    # ─── STEP 0: Revenue Tracker & Enforcer Pre-flight Check ───
    revenue = RevenueTracker()
    enforcer = RevenueEnforcer()
    seeker = RevenueSeeker()
    grabber = CampaignsGrabberAgent()

    if revenue.state.get("paused"):
        log("⛔ PIPELINE PAUSED BY REVENUE ENFORCER — HUMAN_REVIEW_REQUIRED")
        log("⛔ Run: python revenue_tracker.py unpause  — to resume after human review")
        log("=== Hourly Cycle SKIPPED (paused). ===")
        return

    # Pre-flight KPI audit
    kpi_report = enforcer.audit_kpis(min_volume=30)
    log(f"Enforcer Pre-flight KPI Audit Status: {kpi_report['overall_status']}")

    config = revenue.apply_pending_adjustments()
    target_deals = config["target_deals"]
    extra_markets = config["extra_markets"]
    template_mode = config["template_mode"]

    log(f"Active revenue config: target={target_deals}, extra_markets={extra_markets}, template={template_mode}")

    base_cities = 'new york,miami,los angeles,austin,chicago,houston,dallas,phoenix,atlanta,las vegas,london,madrid'
    if extra_markets:
        base_cities += ',' + ','.join(extra_markets)
        log(f"Market expansion active: +{len(extra_markets)} cities")

    markets_list = [c.strip() for c in base_cities.split(',')]

    # ─── STEP 1: Seeker Agent Opportunity Hunting ───
    log("--- STEP 1: Seeker Agent Opportunity Hunting & Prioritization ---")
    try:
        seek_res = seeker.seek_opportunities(target=target_deals, markets=markets_list)
        log(f"Seeker output: Found {seek_res.get('total_found', 0)} leads (Tier A: {seek_res.get('tier_a', 0)}, Tier B: {seek_res.get('tier_b', 0)})")
    except Exception as e:
        log(f"Seeker error: {e}")

    # ─── STEP 1.5: Campaigns Grabber Agent (Clipping & Voice Agents Creation) ───
    log("--- STEP 1.5: Campaigns Grabber Agent (Clipping & Voice Agents Creation) ---")
    try:
        grab_summary = grabber.grab_all()
        log(f"Campaigns Grabber output: Grabbed {grab_summary.get('clipping_campaigns_grabbed', 0)} Clipping Campaigns & Created {grab_summary.get('voice_agents_created', 0)} Voice Agents")
    except Exception as e:
        log(f"Campaigns Grabber error: {e}")

    # ─── STEP 1.8: Seller Monetization Agent (Buyer Hunting & Lead Pack Monetization) ───
    log("--- STEP 1.8: Seller Monetization Agent (Buyer Sourcing & Lead Pack Sales) ---")
    monetization_script = BASE_DIR / 'seller_monetization_agent.py'
    try:
        log("Executing Seller Monetization Agent for Lead Pack buyer sales...")
        subprocess.run([sys.executable, str(monetization_script)], capture_output=True, text=True, timeout=300)
    except Exception as e:
        log(f"Error executing Seller Monetization Agent: {e}")

    # ─── STEP 2: Lead Engine Daemon Pipeline Execution ───
    log("--- STEP 2: Lead Engine Daemon Execution ---")
    lead_engine_script = BASE_DIR / 'lead_engine_daemon.py'
    cmd = [
        sys.executable,
        str(lead_engine_script),
        '--cities', base_cities,
        '--target-deals', str(target_deals),
        '--outreach'
    ]
    
    try:
        log(f"Triggering Lead Engine Daemon for {target_deals} global deals & live offer emailing...")
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        log(f"Lead Engine execution snippet: {res.stdout[-300:] if res.stdout else 'No output'}")
        if res.stderr:
            log(f"Lead Engine stderr snippet: {res.stderr[-300:]}")
    except Exception as e:
        log(f"Error executing Lead Engine Daemon: {e}")
        
    # ─── STEP 3: Multi-Touch Cadence Engine (Follow-Ups) ───
    log("--- STEP 3: Multi-Touch Cadence Engine ---")
    cadence_script = BASE_DIR / 'multi_touch_cadence_agent.py'
    try:
        log("Executing Multi-Touch Follow-Up Cadence Engine...")
        subprocess.run([sys.executable, str(cadence_script)], capture_output=True, text=True, timeout=300)
    except Exception as e:
        log(f"Error executing Cadence Engine: {e}")

    # ─── STEP 4: WhatsApp & SMS Direct Links Generator ───
    log("--- STEP 4: WhatsApp & SMS Blaster Links ---")
    wa_script = BASE_DIR / 'whatsapp_sms_blaster.py'
    try:
        log("Generating WhatsApp & SMS direct campaign links...")
        subprocess.run([sys.executable, str(wa_script)], capture_output=True, text=True, timeout=300)
    except Exception as e:
        log(f"Error generating WhatsApp links: {e}")

    # ─── STEP 5: Video Generation & Higgsfield Visuals ───
    log("--- STEP 5: Video Generation & Higgsfield Visual Assets ---")
    visual_gen_script = BASE_DIR / 'higgsfield_visual_generator.py'
    try:
        log("Generating Higgsfield AI luxury deal visuals & thumbnail assets...")
        subprocess.run([sys.executable, str(visual_gen_script)], capture_output=True, text=True, timeout=300)
    except Exception as e:
        log(f"Error generating deal visuals: {e}")

    # ─── STEP 6: Clipping Campaign Scan & Clip Building ───
    log("--- STEP 6: Clipping Factory Cloud Scan & Clip Generation ---")
    cloud_scan_script = ROOT_DIR / 'clipping-factory' / 'cloud_scan.py'
    try:
        if cloud_scan_script.exists():
            log("Scanning clipping.com for viral campaigns...")
            subprocess.run([sys.executable, str(cloud_scan_script)], capture_output=True, text=True, timeout=300)
        else:
            log("cloud_scan.py not found, skipping cloud scan")
    except Exception as e:
        log(f"Error in clipping scan: {e}")

    # ─── STEP 7: Multi-Channel YouTube & Social Queue Posting ───
    log("--- STEP 7: Multi-Channel Social Posting & Brand Publishing ---")
    master_pub_script = ROOT_DIR / 'MBM' / 'Scripts' / 'master_publisher.py'
    try:
        if master_pub_script.exists():
            log("Executing Master Social Publisher across brand channels...")
            subprocess.run([sys.executable, str(master_pub_script)], capture_output=True, text=True, timeout=600)
        else:
            log("master_publisher.py not found, skipping social publish")
    except Exception as e:
        log(f"Error executing Master Social Publisher: {e}")

    # ─── STEP 8: Historical Lead Re-enrichment ───
    log("--- STEP 8: Historical Lead Re-enrichment ---")
    enrich_script = BASE_DIR / 'enrich_old_leads.py'
    try:
        log("Re-enriching historical leads database...")
        subprocess.run([sys.executable, str(enrich_script)], capture_output=True, text=True, timeout=300)
    except Exception as e:
        log(f"Error running historical lead enrichment: {e}")

    # ─── STEP 8.5: Live Direct Email Queue Sender ───
    log("--- STEP 8.5: Live Direct Email Queue Sender ---")
    email_sender_script = ROOT_DIR / 'server' / 'emailSender.js'
    try:
        if email_sender_script.exists():
            log("Draining email queue & sending cash offer emails to clients...")
            subprocess.run(['node', str(email_sender_script)], capture_output=True, text=True, timeout=300)
        else:
            log("emailSender.js not found, skipping email queue drain")
    except Exception as e:
        log(f"Error executing email queue sender: {e}")

    # ─── STEP 9: THE QUESTION — Revenue Tracker Gate Check ───
    log("============================================================")
    log("💰 REVENUE GATE — ASKING THE QUESTION: 'Have we made any money?'")
    log("============================================================")

    verdict = revenue.hourly_revenue_check()

    if verdict["made_money"]:
        log(f"✅ ANSWER: YES — Score: {verdict['score']}")
        log(f"   Signals: {verdict['signals']}")
    else:
        log(f"❌ ANSWER: NO — Score: {verdict['score']}")
        log(f"   Signals: {verdict['signals']}")
        log(f"   Escalation: {verdict['escalation_level']}")
        if verdict["adjustments"]:
            log(f"   Queued Adjustments for Next Cycle:")
            for adj in verdict["adjustments"]:
                log(f"     → {adj['description']}")

    # ─── STEP 10: Enforcer Verdict & SLA Rule Enforcement ───
    log("--- STEP 10: Revenue Enforcer Enforcement ---")
    enforce_res = enforcer.enforce_verdict(verdict)
    log(f"Enforcer Actions: {enforce_res['actions_enforced']}")

    log("============================================================")
    log("=== Hourly Cycle Complete. Waiting 60 minutes for next run. ===")
    log("============================================================")

def main():
    log("Initializing Hourly Outreach Agent Daemon...")
    while True:
        try:
            run_hourly_cycle()
        except Exception as e:
            log(f"Unhandled error in main loop: {e}")
        
        # Sleep for 1 hour (3600 seconds)
        time.sleep(3600)

if __name__ == "__main__":
    main()
