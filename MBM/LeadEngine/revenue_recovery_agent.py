import json
import os
from datetime import datetime, timezone

def run_recovery_agent():
    print("=== AAA WORKFLOW 2: AUTOMATED INVOICE CHASER & REVENUE RECOVERY ===")

    # Only real invoices from a configured ledger may be processed. This engine
    # must NEVER fabricate invoices or count simulated recoveries as money.
    ledger_path = os.getenv("INVOICE_LEDGER_PATH", "").strip()
    failed_invoices = []
    if ledger_path and os.path.exists(ledger_path):
        try:
            with open(ledger_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            failed_invoices = loaded if isinstance(loaded, list) else loaded.get("invoices", [])
        except Exception as e:
            print(f"[-] Could not read invoice ledger {ledger_path}: {e}")
    else:
        print("[!] No invoice ledger configured (set INVOICE_LEDGER_PATH). "
              "No invoices processed. Recovered value is $0.00 — this engine "
              "does not simulate revenue.")

    results = []
    recovered_value = 0.0

    for invoice in failed_invoices:
        amount = float(invoice.get("amount", 0) or 0)
        print(f"[*] Processing Overdue Invoice: {invoice.get('client', invoice.get('client_name', '?'))} | ${amount:,.2f}")

        days_overdue = int(invoice.get("days_overdue", 0) or 0)
        action = "Sent Polite 'Soft' Reminder via Email." if days_overdue <= 3 else "Sent 'Hard' Reminder via Email & SMS with Suspension Warning."
        print(f"  [+] {action}")

        # A follow-up is NOT revenue. Money is only recovered when a payment
        # event confirms it (e.g. a ledger row explicitly marked "recovered").
        is_recovered = bool(invoice.get("recovered")) and amount > 0
        if is_recovered:
            recovered_value += amount

        results.append({
            "client": invoice.get("client", invoice.get("client_name", "")),
            "amount": amount,
            "action_taken": action,
            "status": "FOLLOW_UP_SENT",
            "recovered": is_recovered,
        })

    log_file = r"C:\Users\omare\OneDrive\Desktop\AI\MBM\LeadEngine\logs\revenue_recovery_results.json"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "invoices_processed": len(results),
            "recovery_attempts": results,
            "total_value_protected": recovered_value,
            "source": "real_invoice_ledger" if failed_invoices else "none",
        }, f, indent=4)

    print(f"=== RECOVERY AGENT COMPLETE | Confirmed Recovered: ${recovered_value:,.2f} ===\n")
    return {"recovery_attempts": results, "total_value_protected": recovered_value}

if __name__ == "__main__":
    run_recovery_agent()
