import json
import os
from datetime import datetime, timezone

def run_intake_agent():
    print("=== AAA WORKFLOW 1: AI CLIENT INTAKE & PROPOSAL GENERATOR ===")
    
    inbound_leads = [
        {"name": "TechGrow Logistics", "industry": "Logistics", "budget": "$15k", "pain_point": "Manual route scheduling taking 20 hours/week."},
        {"name": "Zenith Medical Clinics", "industry": "Healthcare", "budget": "$40k", "pain_point": "Patient intake forms are on paper and require manual data entry."},
    ]
    
    results = []
    for lead in inbound_leads:
        print(f"[*] Processing inbound lead: {lead['name']} ({lead['industry']})")
        
        # Simulate AI Agent logic for proposal generation
        proposal_title = f"AI Transformation Strategy for {lead['name']}"
        proposed_solution = ""
        deal_value = 0
        
        if lead['industry'] == "Logistics":
            proposed_solution = "Automated AI Route Orchestration & Predictive Maintenance Dispatch."
            deal_value = 12000
            strategy_details = "1. AI Ingestion of Dispatch Data\n2. Real-time Route Optimization\n3. Driver SMS Notification System"
        else:
            proposed_solution = "Conversational Intake AI Agent with EMR Integration."
            deal_value = 35000
            strategy_details = "1. Website Chatbot for Triaging\n2. HIPAA-Compliant Data Parsing\n3. EMR Sync Automation"
            
        print(f"  [+] Generated Proposal: {proposal_title}")
        print(f"  [+] Deal Value Quoted: ${deal_value:,.2f}")
        
        # ENHANCEMENT: Generate the actual Proposal Document
        doc_filename = f"Proposal_{lead['name'].replace(' ', '_')}.md"
        doc_path = os.path.join(os.path.dirname(__file__), "blueprints", doc_filename)
        with open(doc_path, "w", encoding="utf-8") as f:
            f.write(f"# {proposal_title}\n\n")
            f.write(f"**Prepared For:** {lead['name']}\n")
            f.write(f"**Industry:** {lead['industry']}\n")
            f.write(f"**Identified Pain Point:** {lead['pain_point']}\n\n")
            f.write(f"## Recommended AAA Solution\n{proposed_solution}\n\n")
            f.write(f"## Strategy Breakdown\n{strategy_details}\n\n")
            f.write(f"## Investment Required\n**Total Value:** ${deal_value:,.2f}\n")
        
        print(f"  [+] Proposal document saved to: {doc_path}")
        
        results.append({
            "lead_name": lead['name'],
            "proposal_generated": True,
            "solution": proposed_solution,
            "deal_value": deal_value,
            "status": "PROPOSAL_SENT"
        })
        
    log_file = r"C:\Users\omare\OneDrive\Desktop\AI\MBM\LeadEngine\logs\client_intake_results.json"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, "w") as f:
        json.dump({"timestamp": datetime.now(timezone.utc).isoformat(), "leads_processed": len(results), "proposals": results}, f, indent=4)
        
    print(f"=== INTAKE AGENT COMPLETE | Total Pipeline Quoted: ${sum(r['deal_value'] for r in results):,.2f} ===\n")
    return {"proposals": results, "total_value": sum(r['deal_value'] for r in results)}

if __name__ == "__main__":
    run_intake_agent()
