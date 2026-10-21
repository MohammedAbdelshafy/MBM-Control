import os
from gcp_secrets import create_or_update_secret

def main():
    token = os.getenv("PHOUND_TOKEN", "")
    personas = os.getenv("PHOUND_PERSONAS", "")
    if not token or not personas:
        raise SystemExit("PHOUND_TOKEN and PHOUND_PERSONAS must be set in the environment")
    
    print("Uploading PHOUND_TOKEN to Secret Manager...")
    create_or_update_secret("PHOUND_TOKEN", token)
    
    print("Uploading PHOUND_PERSONAS to Secret Manager...")
    create_or_update_secret("PHOUND_PERSONAS", personas)
    
    print("Successfully added Phound secrets to GCP Secret Manager!")

if __name__ == "__main__":
    main()
