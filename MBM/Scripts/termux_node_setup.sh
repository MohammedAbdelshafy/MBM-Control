#!/data/data/com.termux/files/usr/bin/bash
# ==============================================================================
# ANTIGRAVITY PHONE NODE SETUP SCRIPT (TERMUX)
# Run this inside Termux on your Android phone to configure it as an Antigravity node.
# ==============================================================================

set -e

echo "=== [1/5] Updating Termux packages ==="
pkg update -y
pkg install -y openssh tmux git

echo "=== [2/5] Setting up SSH Authorized Keys ==="
mkdir -p ~/.ssh
chmod 700 ~/.ssh

PUB_KEY="ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAWt3ctfPRShBqDoexvcQoNFUvEF8ihrTfrnHTf4bi/v antigravity-phone"

if ! grep -q "$PUB_KEY" ~/.ssh/authorized_keys 2>/dev/null; then
    echo "$PUB_KEY" >> ~/.ssh/authorized_keys
    echo "Added Antigravity public key to ~/.ssh/authorized_keys"
fi
chmod 600 ~/.ssh/authorized_keys

echo "=== [3/5] Starting SSH Server (sshd on port 8022) ==="
pkill sshd 2>/dev/null || true
sshd
echo "sshd started on port 8022."

echo "=== [4/5] Creating Persistent Tmux Session: 'antigravity' ==="
if ! tmux has-session -t antigravity 2>/dev/null; then
    tmux new-session -d -s antigravity -n main
    tmux new-window -t antigravity -n opencode
    tmux new-window -t antigravity -n mbm
    tmux new-window -t antigravity -n logs
    tmux new-window -t antigravity -n git
    echo "Created tmux session 'antigravity' with 5 windows (main, opencode, mbm, logs, git)."
else
    echo "Tmux session 'antigravity' already running."
fi

echo "=== [5/5] Node Discovery & Verification ==="
echo "Hostname: $(hostname)"
echo "User:     $(whoami)"
echo "Port:     8022"
echo "SSH:      $(ssh -V 2>&1)"
echo "Tmux:     $(tmux -V)"
echo "Git:      $(git --version)"
echo ""
echo "=== Node Setup Complete! ==="
echo "Ensure Tailscale is connected on your phone."
echo "You can now connect from Windows using: ssh phone-antigravity"
