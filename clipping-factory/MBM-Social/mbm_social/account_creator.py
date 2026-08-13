import asyncio
import random
import time
from pathlib import Path
import yaml
from playwright.async_api import async_playwright

BASE_DIR = Path(__file__).resolve().parent.parent
BRANDS_DIR = BASE_DIR / "Brands"
USER_DATA_DIR_BASE = BASE_DIR / "mbm_social"

async def get_brands():
    brands = []
    if BRANDS_DIR.exists():
        for b in BRANDS_DIR.iterdir():
            if b.is_dir() and (b / "brand.yaml").exists():
                try:
                    with open(b / "brand.yaml", "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                        if data.get("active", True):
                            brands.append(data)
                except Exception as e:
                    print(f"Failed to load {b.name}: {e}")
    return brands

async def create_accounts(brand_config: dict):
    brand_slug = brand_config.get("slug")
    if not brand_slug:
        return
        
    print(f"\n{'='*50}")
    print(f" Launching Account Creator for: {brand_slug}")
    print(f"{'='*50}")
    
    email = brand_config.get("gmail_account", "")
    ig_handle = brand_config.get("social_handles", {}).get("instagram", "").strip("@")
    tiktok_handle = brand_config.get("social_handles", {}).get("tiktok", "").strip("@")
    
    if not email:
        print(f" WARNING: No gmail_account found for {brand_slug}. Please check brand.yaml.")
        return

    # Generate a secure password to use for the new accounts
    password = f"MBM_{brand_slug.capitalize()}2026!"
    
    print(f"Email: {email}")
    print(f"Suggested Password: {password}")
    print(f"IG Handle: {ig_handle}")
    print(f"TikTok Handle: {tiktok_handle}")
    
    brand_clean = brand_slug.strip().lower().replace(" ", "").replace("-", "_")
    profile_dir = USER_DATA_DIR_BASE / f"youtube_profile_{brand_clean}"
    
    async with async_playwright() as p:
        print(f"Opening isolated profile for {brand_slug}...")
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--disable-features=IsolateOrigins,site-per-process",
                "--disable-site-isolation-trials",
                "--disable-web-security",
            ],
        )
        
        # --- INSTAGRAM ---
        print("\n [INSTAGRAM]")
        page = await browser.new_page()

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)

        await page.goto("https://www.instagram.com/accounts/emailsignup/")

        print("Waiting for page load...")
        try:
            await page.wait_for_selector('input[name="emailOrPhone"]', timeout=10000)
            await _human_type(page, 'input[name="emailOrPhone"]', email)
            await page.wait_for_timeout(random.randint(500, 1500))

            display_name = brand_config.get("display_name", brand_slug)
            await _human_type(page, 'input[name="fullName"]', display_name)
            await page.wait_for_timeout(random.randint(500, 1500))

            if ig_handle:
                await _human_type(page, 'input[name="username"]', ig_handle)
                await page.wait_for_timeout(random.randint(500, 1500))

            await _human_type(page, 'input[name="password"]', password)
            print(" Registration fields pre-filled for Instagram.")
        except Exception as e:
            print(f" WARNING: Could not automatically fill Instagram fields: {e}")
            
        print("\n PAUSED: Please complete the Instagram registration (solve captcha, enter OTP).")
        input("Press ENTER when you have successfully created the Instagram account...")
        
        # --- TIKTOK ---
        print("\n [TIKTOK]")
        await page.goto("https://www.tiktok.com/signup/email")
        print("Navigated to TikTok signup.")
        
        try:
            print("Attempting to pre-fill TikTok...")
            await page.wait_for_timeout(3000) # Give TikTok a moment to render
            
            # Try filling email
            email_inputs = await page.locator('input[type="email"], input[name="email"]').all()
            if email_inputs:
                await email_inputs[0].fill(email)
                
            # Try filling password
            pass_inputs = await page.locator('input[type="password"]').all()
            if pass_inputs:
                await pass_inputs[0].fill(password)
                
            print(" Registration fields pre-filled for TikTok.")
        except Exception as e:
            print(f" WARNING: Could not automatically fill TikTok fields: {e}")
        
        print("\n PAUSED: Please complete the TikTok registration (solve captcha, enter OTP).")
        print(f"Email: {email} | Password: {password}")
        input("Press ENTER when you have successfully created the TikTok account...")
        
        await browser.close()
        print(f" Finished account setup for {brand_slug}.")

async def main():
    brands = await get_brands()
    if not brands:
        print("No active brands found in Brands directory.")
        return
        
    print(f"Found {len(brands)} active brands. Starting setup...")
    for brand in brands:
        await create_accounts(brand)
        
    print("\n All brands processed! The persistent sessions have been saved.")

if __name__ == "__main__":
    asyncio.run(main())


# ─── ANTI-FLAGGING HELPERS ──────────────────────────────────────────
async def _human_type(page, selector: str, text: str, delay_ms: int = None):
    """Type into a selector with human-like per-key delays."""
    if delay_ms is None:
        delay_ms = random.randint(80, 200)
    el = await page.wait_for_selector(selector, timeout=10000)
    await el.type(text, delay=delay_ms)
