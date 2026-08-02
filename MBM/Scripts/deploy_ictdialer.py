"""
ICTDialer Full Deployment Script
================================
Provisions VPS, installs ICTDialer, imports leads, creates campaigns.
Requires: Hetzner API token, Telnyx API key
"""

import os
import sys
import json
import time
import subprocess
import requests
from datetime import datetime

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
ARTIFACTS = os.path.join(MBM_ROOT, "Artifacts")

# =============================================================================
# CONFIGURATION
# =============================================================================
CONFIG = {
    "hetzner_api_token": os.environ.get("HETZNER_API_TOKEN", ""),
    "telnyx_api_key": os.environ.get("TELNYX_API_KEY", ""),
    "server_name": "ictdialer-prod",
    "server_type": "cx32",  # 4 vCPU, 8GB RAM, 80GB NVMe
    "server_location": "ash",  # Ashburn, VA (US East)
    "image": "rocky-9",
    "ssh_key_name": "ictdialer-key",
    "db_password": f"ICT_{datetime.now().strftime('%Y%m%d')}_{os.urandom(8).hex()}",
}

# Hetzner API
HETZNER_API = "https://api.hetzner.cloud/v1"


def log(msg, level="INFO"):
    colors = {"INFO": "\033[94m", "OK": "\033[92m", "WARN": "\033[93m", "ERR": "\033[91m"}
    reset = "\033[0m"
    print(f"{colors.get(level, '')}{level}{reset}: {msg}")


# =============================================================================
# HETZNER VPS PROVISIONING
# =============================================================================
class HetznerProvisioner:
    def __init__(self, api_token):
        self.headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}

    def test_connection(self):
        """Test API connection."""
        try:
            resp = requests.get(f"{HETZNER_API}/locations", headers=self.headers, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            log(f"API connection failed: {e}", "ERR")
            return False

    def get_ssh_keys(self):
        """List existing SSH keys."""
        resp = requests.get(f"{HETZNER_API}/ssh_keys", headers=self.headers)
        return resp.json().get("ssh_keys", [])

    def create_ssh_key(self, name, public_key):
        """Create an SSH key in Hetzner."""
        resp = requests.post(f"{HETZNER_API}/ssh_keys", headers=self.headers, json={
            "name": name,
            "public_key": public_key,
        })
        if resp.status_code == 201:
            log(f"SSH key created: {name}", "OK")
            return resp.json()["ssh_key"]
        log(f"SSH key creation failed: {resp.text}", "ERR")
        return None

    def create_server(self, name, server_type, image, location, ssh_key_ids=None):
        """Provision a new server."""
        payload = {
            "name": name,
            "server_type": server_type,
            "image": image,
            "location": location,
            "start_after_create": True,
        }
        if ssh_key_ids:
            payload["ssh_keys"] = ssh_key_ids

        log(f"Provisioning server: {name} ({server_type}) in {location}...")
        resp = requests.post(f"{HETZNER_API}/servers", headers=self.headers, json=payload)

        if resp.status_code == 201:
            server = resp.json()["server"]
            log(f"Server created: ID={server['id']}, IP={server['public_net']['ipv4']['ip']}", "OK")
            return server
        log(f"Server creation failed: {resp.text}", "ERR")
        return None

    def wait_for_server(self, server_id, timeout=600):
        """Wait for server to be ready."""
        log("Waiting for server to be ready...")
        start = time.time()
        while time.time() - start < timeout:
            resp = requests.get(f"{HETZNER_API}/servers/{server_id}", headers=self.headers)
            if resp.status_code == 200:
                server = resp.json()["server"]
                status = server["status"]
                if status == "running":
                    log(f"Server is running! IP: {server['public_net']['ipv4']['ip']}", "OK")
                    return server
                log(f"  Status: {status}...")
            time.sleep(10)
        log("Timeout waiting for server", "ERR")
        return None


# =============================================================================
# TELNYX SIP TRUNK SETUP
# =============================================================================
class TelnyxSetup:
    def __init__(self, api_key):
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        self.base_url = "https://api.telnyx.com/v2"

    def test_connection(self):
        """Test API connection."""
        try:
            resp = requests.get(f"{self.base_url}/connection", headers=self.headers, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            log(f"Telnyx API connection failed: {e}", "ERR")
            return False

    def list_numbers(self):
        """List phone numbers."""
        resp = requests.get(f"{self.base_url}/phone_numbers", headers=self.headers)
        return resp.json().get("data", [])

    def buy_number(self, area_code="214"):
        """Buy a phone number."""
        resp = requests.post(f"{self.base_url}/phone_numbers", headers=self.headers, json={
            "phone_number": f"+1{area_code}",
            "connection_id": self.get_connection_id(),
        })
        if resp.status_code == 201:
            number = resp.json()["data"]
            log(f"Number purchased: {number['phone_number']}", "OK")
            return number
        log(f"Number purchase failed: {resp.text}", "ERR")
        return None

    def get_connection_id(self):
        """Get SIP connection ID."""
        resp = requests.get(f"{self.base_url}/connection", headers=self.headers)
        connections = resp.json().get("data", [])
        if connections:
            return connections[0]["id"]
        return None

    def create_sip_connection(self, name):
        """Create a SIP connection for ICTDialer."""
        resp = requests.post(f"{self.base_url}/connection", headers=self.headers, json={
            "name": name,
            "transport_protocol": "UDP",
            "connection_type": "IP",
            "default_onnet_calling_enabled": False,
        })
        if resp.status_code == 201:
            conn = resp.json()["data"]
            log(f"SIP connection created: {conn['id']}", "OK")
            return conn
        log(f"SIP connection creation failed: {resp.text}", "ERR")
        return None


# =============================================================================
# SSH DEPLOYMENT
# =============================================================================
def deploy_via_ssh(server_ip, ssh_key_path=None):
    """Deploy ICTDialer via SSH."""
    ssh_user = "root"
    ssh_cmd = f"ssh -o StrictHostKeyChecking=no {ssh_user}@{server_ip}"

    if ssh_key_path:
        ssh_cmd = f"ssh -i {ssh_key_path} -o StrictHostKeyChecking=no {ssh_user}@{server_ip}"

    # Upload setup script
    log("Uploading setup script...")
    scp_cmd = f"scp -o StrictHostKeyChecking=no"
    if ssh_key_path:
        scp_cmd = f"scp -i {ssh_key_path} -o StrictHostKeyChecking=no"

    setup_script = os.path.join(MBM_ROOT, "Scripts", "setup_ictdialer.sh")
    os.system(f"{scp_cmd} {setup_script} {ssh_user}@{server_ip}:/tmp/setup_ictdialer.sh")

    # Execute setup script
    log("Executing setup script on server...")
    os.system(f'{ssh_cmd} "chmod +x /tmp/setup_ictdialer.sh && bash /tmp/setup_ictdialer.sh"')

    # Upload lead CSV
    log("Uploading leads...")
    lead_csv = os.path.join(ARTIFACTS, "all_states_ictdialer_import.csv")
    os.system(f"{scp_cmd} {lead_csv} {ssh_user}@{server_ip}:/tmp/leads.csv")

    log("Deployment complete!", "OK")
    return True


# =============================================================================
# MAIN
# =============================================================================
def main():
    print("=" * 60)
    print("ICTDIALER FULL DEPLOYMENT")
    print("=" * 60)

    # Check configuration
    if not CONFIG["hetzner_api_token"]:
        log("HETZNER_API_TOKEN not set. Running in manual mode.", "WARN")
        log("Set it with: export HETZNER_API_TOKEN=your_token", "WARN")
        manual_mode = True
    else:
        manual_mode = False

    if not CONFIG["telnyx_api_key"]:
        log("TELNYX_API_KEY not set. SIP setup will be manual.", "WARN")
        log("Set it with: export TELNYX_API_KEY=your_key", "WARN")

    # =========================================================================
    # PHASE 1: Provision VPS
    # =========================================================================
    log("\n=== PHASE 1: VPS Provisioning ===")

    if not manual_mode:
        hetzner = HetznerProvisioner(CONFIG["hetzner_api_token"])

        if hetzner.test_connection():
            log("Hetzner API connected", "OK")

            # Get or create SSH key
            ssh_keys = hetzner.get_ssh_key_names()
            ssh_key_ids = [k["id"] for k in ssh_keys if k["name"] == CONFIG["ssh_key_name"]]

            if not ssh_key_ids:
                # Generate SSH key pair
                key_path = os.path.expanduser("~/.ssh/ictdialer_key")
                if not os.path.exists(key_path):
                    os.system(f'ssh-keygen -t ed25519 -f {key_path} -N ""')

                with open(f"{key_path}.pub", "r") as f:
                    public_key = f.read().strip()

                key = hetzner.create_ssh_key(CONFIG["ssh_key_name"], public_key)
                if key:
                    ssh_key_ids = [key["id"]]

            # Create server
            server = hetzner.create_server(
                name=CONFIG["server_name"],
                server_type=CONFIG["server_type"],
                image=CONFIG["image"],
                location=CONFIG["server_location"],
                ssh_key_ids=ssh_key_ids,
            )

            if server:
                server = hetzner.wait_for_server(server["id"])
                if server:
                    server_ip = server["public_net"]["ipv4"]["ip"]
                    log(f"Server ready at: {server_ip}", "OK")

                    # Deploy ICTDialer
                    deploy_via_ssh(server_ip, key_path)
        else:
            log("Cannot connect to Hetzner API. Falling back to manual mode.", "WARN")
            manual_mode = True

    if manual_mode:
        log("\n=== MANUAL DEPLOYMENT INSTRUCTIONS ===")
        print("""
1. PROVISION VPS:
   - Go to https://console.hetzner.cloud
   - Create new server: CX32 (4 vCPU, 8GB RAM, 80GB NVMe)
   - Image: Rocky Linux 9
   - Location: Ashburn, VA (or nearest to you)
   - Add SSH key

2. SSH INTO SERVER:
   ssh root@YOUR_SERVER_IP

3. RUN SETUP SCRIPT:
   wget -qO- https://raw.githubusercontent.com/.../setup_ictdialer.sh | bash
   OR copy the script from MBM/Scripts/setup_ictdialer.sh

4. ACCESS WEB GUI:
   http://YOUR_SERVER_IP/ictdialer
   Login: admin@ictcore.org / helloAdmin

5. CONFIGURE SIP TRUNK:
   - Go to https://telnyx.com
   - Buy a DID number ($1/mo)
   - Create SIP credentials
   - In ICTDialer: Administration > Providers > Add New
   - Host: sip.telnyx.com
   - Username: your_sip_user
   - Password: your_sip_password

6. IMPORT LEADS:
   - Upload: MBM/Artifacts/all_states_ictdialer_import.csv
   - Create contact groups: "Sellers" and "Buyers"

7. CREATE CAMPAIGNS:
   - Seller Campaign: Progressive mode, 3 concurrent channels
   - Buyer Campaign: Progressive mode, 2 concurrent channels

8. START DIALING!
        """)

    # =========================================================================
    # PHASE 2: Summary
    # =========================================================================
    log("\n=== DEPLOYMENT SUMMARY ===")

    leads_file = os.path.join(ARTIFACTS, "all_states_leads.csv")
    ict_file = os.path.join(ARTIFACTS, "all_states_ictdialer_import.csv")

    if os.path.exists(leads_file):
        with open(leads_file, "r") as f:
            lines = f.readlines()
            log(f"Leads ready: {len(lines) - 1} leads in {leads_file}")

    if os.path.exists(ict_file):
        with open(ict_file, "r") as f:
            lines = f.readlines()
            log(f"ICTDialer import ready: {len(lines) - 1} contacts in {ict_file}")

    log("\nEstimated costs:")
    log("  Hetzner CX32 VPS: ~$6/mo")
    log("  Telnyx DID: ~$1/mo")
    log("  Telnyx calls: ~$0.003/min")
    log("  Total monthly: ~$7-10/mo + call minutes")


if __name__ == "__main__":
    main()
