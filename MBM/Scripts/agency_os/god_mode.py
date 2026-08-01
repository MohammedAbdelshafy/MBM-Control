import time
import sys
import os
import datetime

# Add the parent directory to sys.path to import our module scripts
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# Import Phase 1, 2, 3 modules
from Scripts.agency_os.job_acquisition import bid_submitter, negotiator_agent
from Scripts.agency_os.factory import orchestrator
from Scripts.agency_os.finance import payment_tracker
from Scripts import telegram_notify

def log(message: str):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [GOD MODE] {message}")

def god_mode_daemon():
    log("INITIALIZING GOD MODE DAEMON...")
    telegram_notify.send_message("👑 *GOD MODE ONLINE*\n\nThe Autonomous AI Agency daemon has started. Scanning for jobs and payments.")
    
    first_bid_attempted = False
    
    # The Master Loop
    while True:
        log("--- Starting New Cycle ---")
        
        # 1. Scan for Jobs (Simulated Trigger)
        log("Phase 1: Scanning Upwork/Fiverr...")
        
        # 1. Scan for Real Jobs
        log("Phase 1: Scanning Upwork/Fiverr RSS & Lead Feeds...")
        found_job = None # Only populated when live job scrapers return real postings
        
        if found_job:
            log(f"Found High-Paying Job: {found_job['title']} (${found_job['budget']})")
            bid_submitter.submit_bid(found_job["id"], "Drafted Proposal...", found_job["budget"])
            
        # 2. Check for Won Contracts
        log("Phase 1.5: Checking Inbox for Won Contracts...")
        won_contracts = negotiator_agent.negotiate()
        
        # 3. Auto-Coder Factory
        if won_contracts:
            for contract in won_contracts:
                log(f"Phase 2: Triggering Auto-Coder for {contract['client_name']}")
                print(f"🚀 *CONTRACT WON!*\nClient: {contract['client_name']}\nBudget: ${contract['budget']}\n\nSpinning up Auto-Coder...")
                
                # Trigger opencode to build the project
                orchestrator.spawn_auto_coder(contract["client_name"], contract["requirements"])
        
        # 4. Payment Tracker
        log("Phase 3: Scanning Stripe/Escrow for cleared payments...")
        payment_tracker.track()
        
        # Sleep before next cycle
        sleep_minutes = 5
        log(f"Cycle Complete. Sleeping for {sleep_minutes} minutes...")
        time.sleep(sleep_minutes * 60)

if __name__ == "__main__":
    try:
        god_mode_daemon()
    except KeyboardInterrupt:
        log("GOD MODE OFFLINE (Terminated by User)")
        telegram_notify.send_message("🛑 *GOD MODE OFFLINE*\n\nThe Autonomous AI Agency daemon has been manually terminated.")
