import os
import time
import webbrowser
from playwright.sync_api import sync_playwright

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")

def update_env(key, value):
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r") as f:
            lines = f.readlines()
            
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f'{key}="{value}"\n'
            updated = True
            break
            
    if not updated:
        lines.append(f'{key}="{value}"\n')
        
    with open(ENV_PATH, "w") as f:
        f.writelines(lines)

def run_upwork_capture():
    print("🚀 Launching browser for Upwork Login...")
    print("Please log into Upwork. I will automatically grab your session cookies once you are logged in!")
    
    with sync_playwright() as p:
        # Launch non-headless so the user can interact
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto("https://www.upwork.com/ab/account-security/login")
        
        # Wait for user to log in (url changes to find-work or they close the browser)
        print("Waiting for you to log in... (timeout in 3 minutes)")
        try:
            page.wait_for_url("**/nx/find-work/**", timeout=180000)
            print("✅ Login detected! Extracting cookies...")
            time.sleep(3) # Give it a second to settle
        except Exception:
            print("Timeout or browser closed before finding the dashboard. Extracting whatever cookies we have.")
            
        cookies = context.cookies()
        
        # We need the full cookie string to pass to our RSS/bidding scripts
        cookie_string = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        
        update_env("UPWORK_SESSION_COOKIE", cookie_string)
        print("✅ Upwork cookies successfully saved to .env!")
        
        browser.close()

def guide_stripe_setup():
    print("\n💳 Now let's get your Stripe setup.")
    print("Since Stripe requires identity verification (KYC), I cannot create the account for you.")
    print("Opening Stripe Registration page...")
    
    webbrowser.open("https://dashboard.stripe.com/register")
    
    print("\nInstructions for Stripe:")
    print("1. Complete the registration in your browser.")
    print("2. Once inside the dashboard, search for 'API Keys' at the top.")
    print("3. Copy the 'Secret key' (starts with sk_live_ or sk_test_).")
    
    stripe_key = input("\n👉 Paste your Stripe Secret Key here (or press Enter to skip): ").strip()
    if stripe_key:
        update_env("STRIPE_API_KEY", stripe_key)
        print("✅ Stripe key saved to .env!")
    else:
        print("Skipped Stripe key setup.")

if __name__ == "__main__":
    if not os.path.exists(ENV_PATH):
        # Create from example if doesn't exist
        example_path = ENV_PATH + ".example"
        if os.path.exists(example_path):
            with open(example_path, "r") as f1, open(ENV_PATH, "w") as f2:
                f2.write(f1.read())
    
    try:
        run_upwork_capture()
    except Exception as e:
        print(f"Failed Upwork automation: {e}")
        
    guide_stripe_setup()
    print("\n🎉 Setup Complete! You can now run god_mode.py")
