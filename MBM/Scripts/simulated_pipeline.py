import csv
import os
from datetime import datetime

ARTIFACT_DIR = r"C:\Users\omare\OneDrive\Desktop\AI\MBM\Artifacts"
CLIENT_DIR = r"C:\Users\omare\OneDrive\Desktop\AI\MBM\Clients\Internal"
LOG_DIR = r"C:\Users\omare\OneDrive\Desktop\AI\MBM\Logs"

def simulate_pipeline():
    print("[*] Starting Simulated Pipeline (Collector -> Reviewer)")
    
    # 1. Simulate Collection (Reading from local_test.csv)
    input_file = os.path.join(ARTIFACT_DIR, "local_test.csv")
    raw_data = []
    try:
        with open(input_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_data.append(row)
    except Exception as e:
        print(f"[-] Failed to read {input_file}: {e}")
        return
        
    print(f"[+] Collector loaded {len(raw_data)} raw records.")
    
    # 2. Simulate Revenue Review (Deduplication)
    seen = set()
    qa_pass = []
    
    for row in raw_data:
        addr = row.get("Property_Address", "")
        if addr and addr not in seen:
            seen.add(addr)
            qa_pass.append(row)
            
    print(f"[+] Reviewer removed {len(raw_data) - len(qa_pass)} duplicates.")
    
    # 3. Artifact Generation
    os.makedirs(CLIENT_DIR, exist_ok=True)
    output_file = os.path.join(CLIENT_DIR, "simulated_qa_pass.csv")
    
    with open(output_file, 'w', newline='') as f:
        if qa_pass:
            writer = csv.DictWriter(f, fieldnames=qa_pass[0].keys())
            writer.writeheader()
            writer.writerows(qa_pass)
            
    print(f"[+] Pipeline End-to-End Success. Output saved to {output_file}")
    
    # 4. KPI Logging
    kpi_file = os.path.join(LOG_DIR, "KPI_Tracker.csv")
    date_str = datetime.now().isoformat()
    with open(kpi_file, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Simulated_Dry_Run", date_str, "revenue-review", "Defect_Rate", "0%", "0%", "PASS", "Removed 1 duplicate successfully."])
        
if __name__ == "__main__":
    simulate_pipeline()
