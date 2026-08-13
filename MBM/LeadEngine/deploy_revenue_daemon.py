import time
import subprocess
import os
from datetime import datetime, timezone
from pathlib import Path

# Daemon config
INTERVAL_HOURS = 6
BASE_DIR = Path(__file__).resolve().parent
MASTER_SCRIPT = BASE_DIR / "master_online_revenue_workflow.py"

def run_daemon():
    print("="*60)
    print(" [DAEMON] MBM REVENUE DAEMON INITIALIZED")
    print(f" Interval: Every {INTERVAL_HOURS} hours")
    print("="*60)
    
    while True:
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"\n[{current_time}] Waking up to execute Master Online Revenue Workflow...")
        
        try:
            # We use subprocess to run the master workflow independently, ensuring it doesn't crash the daemon
            result = subprocess.run(
                ["python", str(MASTER_SCRIPT)],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                print(f"[+] Workflow executed successfully.")
                # We can print the last few lines of the output for visibility
                lines = result.stdout.strip().split('\n')
                for line in lines[-5:]:
                    print(f"    {line}")
            else:
                print(f"[-] Workflow failed with error code {result.returncode}.")
                print(f"    Error: {result.stderr.strip()[:200]}...")
                
        except Exception as e:
            print(f"[-] Daemon encountered a fatal error during execution: {e}")
            
        print(f"\n[DAEMON] Sleeping for {INTERVAL_HOURS} hours...")
        # Convert hours to seconds
        time.sleep(INTERVAL_HOURS * 3600)

if __name__ == "__main__":
    run_daemon()
