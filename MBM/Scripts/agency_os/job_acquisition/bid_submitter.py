import time

def submit_bid(job_id: str, proposal_text: str, budget: int):
    """
    Mock script representing a Playwright automation that logs into Upwork
    and physically submits the proposal.
    """
    print(f"[Bid Submitter] Preparing to bid on Job {job_id}...")
    print(f"[Bid Submitter] Launching headless browser...")
    time.sleep(1)
    print(f"[Bid Submitter] Navigating to proposal page...")
    time.sleep(1)
    
    print(f"[Bid Submitter] Filling out cover letter: \n{proposal_text[:50]}...\n")
    print(f"[Bid Submitter] Setting budget to ${budget}")
    
    time.sleep(1)
    print(f"[Bid Submitter] Clicked 'Submit Proposal'!")
    return {"status": "success", "job_id": job_id, "budget_submitted": budget}

if __name__ == "__main__":
    print("Testing Bid Submitter in Dry-Run Mode")
    result = submit_bid("UPW-12345", "Hi, I can build your AI Voice agent using FastAPI...", 500)
    print("Result:", result)
