import time
import subprocess
import os
from datetime import datetime, timezone
from pathlib import Path

# Daemon config
INTERVAL_MINUTES = 15
BASE_DIR = Path(__file__).resolve().parent

def run_daemon():
    print("="*60)
    print(" [DAEMON] MBM SOCIAL POSTING DAEMON INITIALIZED")
    print(f" Interval: Every {INTERVAL_MINUTES} minutes")
    print("="*60)
    
    while True:
        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        print(f"\n[{current_time}] Waking up to execute 'npm run post:all'...")
        
        try:
            # Run the post:all command
            result = subprocess.run(
                ["npm", "run", "post:all"],
                cwd=str(BASE_DIR),
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode == 0:
                print(f"[+] Posting workflow executed successfully.")
                # Print the summary lines
                lines = result.stdout.strip().split('\n')
                for line in lines[-5:]:
                    print(f"    {line}")
            else:
                print(f"[-] Posting workflow failed with error code {result.returncode}.")
                print(f"    Error: {result.stderr.strip()[:200]}...")
                
        except Exception as e:
            print(f"[-] Daemon encountered a fatal error during execution: {e}")
            
        print(f"\n[DAEMON] Sleeping for {INTERVAL_MINUTES} minutes...")
        time.sleep(INTERVAL_MINUTES * 60)

if __name__ == "__main__":
    run_daemon()
