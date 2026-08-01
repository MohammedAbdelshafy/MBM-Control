import os
import sys
import json
import subprocess

def generate_deal_visual(prompt, model="z_image"):
    """
    Submits a generation job to Higgsfield AI CLI and returns the asset URL.
    """
    cmd = [
        "higgsfield", "generate", "create", model,
        "--prompt", prompt,
        "--wait"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=True)
        if res.returncode == 0:
            output = res.stdout.strip()
            print(f"[HIGGSFIELD AI] Successfully generated asset: {output}")
            return output
        else:
            print(f"[HIGGSFIELD AI] Generation warning: {res.stderr.strip()}")
            return None
    except Exception as e:
        print(f"[HIGGSFIELD AI] Execution error: {e}")
        return None

if __name__ == "__main__":
    prompt = "Modern luxury residential villa property exterior, architectural photography, golden hour lighting"
    url = generate_deal_visual(prompt)
    if url:
        print(f"Asset URL: {url}")
