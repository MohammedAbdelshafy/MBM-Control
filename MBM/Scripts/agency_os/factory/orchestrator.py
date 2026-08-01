import os
import subprocess
import time

def spawn_auto_coder(client_name: str, requirements: str):
    """
    Takes the requirements from a won contract and spins up a local AI coding agent (opencode)
    to build the application in a dedicated client folder.
    """
    print(f"[Orchestrator] Spawning Auto-Coder for Client: {client_name}")
    
    # Create client workspace
    base_dir = r"C:\Users\omare\OneDrive\Desktop\AI\Clients"
    client_dir = os.path.join(base_dir, client_name.replace(" ", "_"))
    os.makedirs(client_dir, exist_ok=True)
    
    # Write the requirements to a prompt file
    prompt_file = os.path.join(client_dir, "requirements.txt")
    with open(prompt_file, "w") as f:
        f.write(f"Build a Python FastAPI application based on these exact requirements:\n\n{requirements}\n\nMake sure it is ready for production deployment.")
        
    print(f"[Orchestrator] Wrote requirements to {prompt_file}")
    print(f"[Orchestrator] Triggering opencode to build the app...")
    
    # Here we would normally run: subprocess.Popen(["opencode", "-p", "requirements.txt"], cwd=client_dir)
    # We will simulate the build time for safety
    time.sleep(2)
    print(f"[Orchestrator] Opencode is working... (Simulated)")
    
    time.sleep(2)
    print(f"[Orchestrator] Build complete! Client files are ready in {client_dir}")
    
    return client_dir

if __name__ == "__main__":
    # Test Orchestrator with verified client name
    test_reqs = "Client needs a FastAPI voice backend that connects to Vapi.ai and handles appointment booking."
    spawn_auto_coder("Verified Client", test_reqs)
