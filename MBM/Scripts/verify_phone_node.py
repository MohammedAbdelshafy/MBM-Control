#!/usr/bin/env python3
"""
Antigravity Phone Node Diagnostic & Verification Script
=========================================================
Checks the status of the Android phone execution node via Tailscale & SSH.
"""

import sys
import shutil
import subprocess
from pathlib import Path

PHONE_HOSTNAME = "mohammeds-s24-ultra"
PHONE_TAILSCALE_IP = "100.68.198.108"
SSH_PORT = 8022
KEY_PATH = Path.home() / ".ssh" / "id_ed25519_phone"


def check_tailscale_status():
    tailscale_bin = shutil.which("tailscale") or r"C:\Program Files\Tailscale\tailscale.exe"
    if not Path(tailscale_bin).exists():
        return False, "Tailscale binary not found"
    
    try:
        res = subprocess.run([tailscale_bin, "status"], capture_output=True, text=True, timeout=10)
        lines = res.stdout.splitlines()
        for line in lines:
            if PHONE_TAILSCALE_IP in line or PHONE_HOSTNAME in line:
                is_online = "offline" not in line.lower()
                return is_online, line.strip()
        return False, f"Device {PHONE_HOSTNAME} not found in Tailscale status"
    except Exception as e:
        return False, str(e)


def check_ssh_reachability():
    if not KEY_PATH.exists():
        return False, "SSH private key missing"

    ssh_bin = shutil.which("ssh") or r"C:\Windows\System32\OpenSSH\ssh.exe"
    cmd = [
        ssh_bin,
        "-p", str(SSH_PORT),
        "-i", str(KEY_PATH),
        "-o", "BatchMode=yes",
        "-o", "ConnectTimeout=5",
        "-o", "StrictHostKeyChecking=accept-new",
        f"{PHONE_TAILSCALE_IP}",
        "export PATH=/data/data/com.termux/files/usr/bin:$PATH; whoami; uname -a; git --version; tmux list-sessions; tmux list-windows -t antigravity"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
        if res.returncode == 0:
            return True, res.stdout.strip()
        else:
            return False, res.stderr.strip() or f"SSH exited with code {res.returncode}"
    except Exception as e:
        return False, str(e)


def main():
    print("=" * 60)
    print("ANTIGRAVITY PHONE NODE DIAGNOSTIC")
    print("=" * 60)
    
    # 1. Tailscale
    ts_ok, ts_info = check_tailscale_status()
    print(f"Tailscale Status:    {'ONLINE' if ts_ok else 'OFFLINE / DISCONNECTED'}")
    print(f"Tailscale Info:      {ts_info}")
    
    # 2. SSH & Node
    ssh_ok, ssh_info = check_ssh_reachability()
    print(f"SSH Reachability:    {'PASS' if ssh_ok else 'FAIL'}")
    if ssh_ok:
        print(f"Node Info:\n{ssh_info}")
    else:
        print(f"SSH Details:         {ssh_info}")
    print("=" * 60)


if __name__ == "__main__":
    main()
