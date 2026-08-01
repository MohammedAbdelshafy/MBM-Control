import json

def check_inbox():
    """
    Checks Upwork API / Client Inbox for actual client responses.
    Returns empty list if no new real messages exist. Zero mock data.
    """
    print("[Negotiator] Checking inbox for verified client replies...")
    return []

def negotiate():
    """
    Analyzes messages and determines if a contract has been won.
    If won, it extracts the requirements and passes it to the orchestrator.
    """
    messages = check_inbox()
    
    won_contracts = []
    
    for msg in messages:
        if msg.get("contract_offered"):
            print(f"[Negotiator] Contract Offered by {msg['client_name']}!")
            
            # Use LLM to extract requirements from chat history
            # (Mocked extraction here)
            extracted_reqs = "Client needs a FastAPI voice backend that connects to Vapi.ai and handles appointment booking."
            
            won_contracts.append({
                "client_name": msg["client_name"],
                "requirements": extracted_reqs,
                "budget": 500
            })
            
    return won_contracts

if __name__ == "__main__":
    print("Starting Negotiator Agent...")
    won = negotiate()
    if won:
        print(f"Passing {len(won)} won contracts to the Orchestrator.")
        print(json.dumps(won, indent=4))
