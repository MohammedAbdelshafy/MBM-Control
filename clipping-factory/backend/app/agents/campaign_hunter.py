"""
CampaignHunterAgent — monitors Clipping.com for new campaigns.

Uses Playwright for browser automation since Clipping.com has no public API.
Designed for robustness: session persistence, CAPTCHA detection, rate limiting.

Security note: credentials are stored in env vars only, never in DB plaintext.
"""
import json
import time
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent
from app.core.redis_client import cache_get, cache_set, distributed_lock


class CampaignHunterAgent(BaseAgent):
    name = "campaign_hunter"

    def __init__(self, db: Session):
        super().__init__(db)
        self._browser = None
        self._page = None
        self._base_url = self.settings.clipping_base_url

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def run(self, page_id: str | None = None) -> AgentResult:
        """
        Scan Clipping.com for new campaigns.
        If page_id is provided, scan only that page; otherwise scan all active pages.
        Falls back to demo seed data when no Clipping.com credentials are configured.
        """
        from app.models.page import Page

        # Demo mode: no credentials → auto-seed realistic campaigns so the pipeline runs
        if self.settings.demo_mode:
            self.logger.info("Demo mode active — seeding sample campaigns (no Clipping.com login)")
            return self._run_demo_mode()

        pages = (
            self.db.query(Page).filter(Page.is_active == True, Page.is_paused == False).all()
        )
        if page_id:
            pages = [p for p in pages if p.id == page_id]

        if not pages:
            return AgentResult.ok({"campaigns_found": 0, "message": "No active pages to scan"})

        total_new = 0
        errors = []

        for page in pages:
            try:
                with distributed_lock(f"scan:{page.id}", timeout=300, blocking_timeout=5):
                    result = self._scan_page(page)
                    total_new += result.get("new_campaigns", 0)
            except Exception as exc:
                self.logger.warning(f"Skipping page {page.id} — lock or scan error: {exc}")
                errors.append({"page_id": page.id, "error": str(exc)})

        return AgentResult.ok(
            {"campaigns_found": total_new, "errors": errors, "pages_scanned": len(pages)}
        )

    # ------------------------------------------------------------------
    # Per-page scanning
    # ------------------------------------------------------------------

    def _scan_page(self, page) -> dict:
        """Authenticate and scrape available campaigns for one page."""
        self._base_url = (page.settings or {}).get("platform_base_url") or self.settings.clipping_base_url
        self.logger.info(f"Scanning page: {page.name} ({page.id}) using base URL: {self._base_url}")

        raw_campaigns = self._fetch_campaigns_with_playwright(page)
        new_count = 0

        for raw in raw_campaigns:
            try:
                created = self._upsert_campaign(raw, page.id)
                if created:
                    new_count += 1
            except Exception as exc:
                self.logger.error(f"Failed to upsert campaign {raw.get('id')}: {exc}")

        self.logger.info(f"Page {page.name}: found {new_count} new campaigns")
        return {"new_campaigns": new_count}

    def _fetch_campaigns_with_playwright(self, page) -> list[dict]:
        """
        Browser automation against Clipping.com.
        Returns a list of raw campaign dicts.

        Tries browser-use (AI-driven) first for resilience against DOM changes.
        Falls back to raw Playwright selectors if browser-use is unavailable.
        Falls back to cached session cookie if available.
        Flags CAPTCHA for human resolution.
        """
        # Try AI-driven browser first — survives Clipping.com DOM updates.
        # asyncio.run() is safe here because Celery workers run in plain OS threads
        # (not gevent/eventlet), so each thread can create its own event loop.
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(self._fetch_campaigns_with_browser_use(page))
            finally:
                loop.close()
            if result:
                self.logger.info(f"browser-use found {len(result)} campaigns")
                return result
        except Exception as exc:
            self.logger.debug(f"browser-use unavailable or failed ({exc}), using Playwright")

        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            self.logger.warning("Playwright not installed — returning mock campaigns")
            return self._mock_campaigns()

        campaigns = []

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )

            # Restore session if available
            if page.session_cookie:
                try:
                    cookies = json.loads(page.session_cookie)
                    context.add_cookies(cookies)
                except Exception:
                    pass

            max_retries = 2
            for attempt in range(1, max_retries + 1):
                try:
                    pw_page.goto(
                        f"{self._base_url}/campaigns",
                        wait_until="networkidle",
                        timeout=30000,
                    )

                    if self._needs_login(pw_page):
                        logged_in = self._login(pw_page)
                        if not logged_in:
                            if attempt < max_retries:
                                self.logger.warning(f"Login failed, retrying ({attempt}/{max_retries})...")
                                continue
                            self.logger.error(f"Skipping page {page_id} — login failed after {max_retries} attempts")
                            browser.close()
                            return []
                        cookies = context.cookies()
                        page.session_cookie = json.dumps(cookies)
                        page.session_expires_at = datetime.now(timezone.utc).isoformat()
                        self.db.flush()

                    if self._has_captcha(pw_page):
                        self.logger.error("CAPTCHA detected — human intervention required")
                        from app.core.redis_client import publish_event
                        publish_event("alerts", {
                            "type": "captcha_required",
                            "page_id": page.id,
                            "ts": datetime.now(timezone.utc).isoformat(),
                        })
                        browser.close()
                        return []

                    campaigns = self._parse_campaign_list(pw_page)

                    cookies = context.cookies()
                    page.session_cookie = json.dumps(cookies)
                    self.db.flush()
                    break  # success — exit retry loop

                except PWTimeout as exc:
                    self.logger.error(f"Playwright timeout (attempt {attempt}/{max_retries}): {exc}")
                    if attempt == max_retries:
                        raise
                    continue
                finally:
                    if attempt == max_retries:
                        browser.close()

        return campaigns

    def _needs_login(self, pw_page) -> bool:
        return pw_page.url.startswith(f"{self._base_url}/login") or \
               pw_page.query_selector("[data-testid='login-form']") is not None

    def _login(self, pw_page, max_attempts: int = 2) -> bool:
        """Log in and verify success. Returns True if login was successful."""
        method = self.settings.clipping_auth_method
        self.logger.info(f"Logging in to {self._base_url} via {method}")
        pw_page.goto(f"{self._base_url}/login", wait_until="networkidle")

        if method == "discord":
            self._login_discord(pw_page)
        elif method == "google":
            self._login_google(pw_page)
        else:
            pw_page.fill("[name='email']", self.settings.clipping_email)
            pw_page.fill("[name='password']", self.settings.clipping_password)
            pw_page.click("[type='submit']")
            pw_page.wait_for_url(f"{self._base_url}/**", timeout=15000)

        # Verify login succeeded
        if self._needs_login(pw_page):
            self.logger.error(f"Login via {method} failed — still on login page")
            return False
        self.logger.info(f"Login via {method} successful")
        return True

    def _login_discord(self, pw_page) -> None:
        """Complete the Discord OAuth flow for Clipping.com."""
        from playwright.sync_api import TimeoutError as PWTimeout

        # Click the "Login with Discord" button on Clipping.com
        try:
            pw_page.click(
                "button:has-text('Discord'), a:has-text('Discord'), "
                "[data-provider='discord'], [href*='discord']",
                timeout=8000,
            )
        except PWTimeout:
            # Some pages use a generic "Continue with" pattern
            pw_page.click(":is(button,a):has-text('Continue with Discord')", timeout=5000)

        # Wait for redirect to discord.com OAuth page
        pw_page.wait_for_url("*discord.com/oauth2/**", timeout=15000)

        # Fill Discord credentials
        pw_page.fill("input[name='email']", self.settings.clipping_email)
        pw_page.fill("input[name='password']", self.settings.clipping_password)
        pw_page.click("button[type='submit']")

        # Discord may show an "Authorize" scope approval page
        try:
            pw_page.wait_for_selector(
                "button:has-text('Authorize'), button:has-text('Allow')", timeout=6000
            )
            pw_page.click("button:has-text('Authorize'), button:has-text('Allow')")
        except PWTimeout:
            pass  # already authorized — goes straight back to Clipping.com

        # Wait for redirect back to Clipping.com
        pw_page.wait_for_url(f"{self._base_url}/**", timeout=20000)
        self.logger.info("Discord OAuth login successful")

    def _login_google(self, pw_page) -> None:
        """Complete the Google OAuth flow for Clipping.com."""
        from playwright.sync_api import TimeoutError as PWTimeout
        pw_page.click("button:has-text('Google'), a:has-text('Google')", timeout=8000)
        pw_page.wait_for_url("*accounts.google.com/**", timeout=15000)
        pw_page.fill("input[type='email']", self.settings.clipping_email)
        pw_page.click("#identifierNext, button:has-text('Next')")
        pw_page.wait_for_selector("input[type='password']", timeout=8000)
        pw_page.fill("input[type='password']", self.settings.clipping_password)
        pw_page.click("#passwordNext, button:has-text('Next')")
        pw_page.wait_for_url(f"{self._base_url}/**", timeout=20000)
        self.logger.info("Google OAuth login successful")

    def _has_captcha(self, pw_page) -> bool:
        """Detect CAPTCHA challenges including reCAPTCHA, hCaptcha, Cloudflare Turnstile, and image/text CAPTCHAs."""
        selectors = [
            ".captcha", "iframe[src*='recaptcha']", "iframe[src*='hcaptcha']",
            "iframe[src*='turnstile']", "[class*='cf-turnstile']", "[id*='turnstile']",
            "[class*='h-captcha']", "div[data-sitekey]", "img[src*='captcha']",
            "input[name*='captcha']", "[aria-label*='captcha']",
        ]
        for sel in selectors:
            if pw_page.query_selector(sel):
                return True
        # Check page text for CAPTCHA keywords
        body_text = pw_page.inner_text("body")
        captcha_keywords = ["captcha", "verify you are human", "security check", "are you human"]
        return any(kw in body_text.lower() for kw in captcha_keywords)

    def _parse_campaign_list(self, pw_page) -> list[dict]:
        """Extract campaign data from the page DOM."""
        campaigns = []
        try:
            pw_page.wait_for_selector("[data-testid='campaign-card'], .campaign-card", timeout=10000)
            cards = pw_page.query_selector_all("[data-testid='campaign-card'], .campaign-card")
            for card in cards[: self.settings.clipping_max_campaigns_per_scan]:
                try:
                    campaigns.append(self._extract_card_data(card, pw_page))
                except Exception as exc:
                    self.logger.debug(f"Failed to parse card: {exc}")
        except Exception as exc:
            self.logger.warning(f"Failed to find campaign cards: {exc}")
        return campaigns

    def _extract_card_data(self, card, pw_page) -> dict:
        """
        Extract structured data from a single campaign card element.
        Important: extract ALL card-level data BEFORE navigating away,
        because the card element handle becomes detached after page navigation.
        """
        def text(selector: str) -> str:
            el = card.query_selector(selector)
            return el.inner_text().strip() if el else ""

        def attr(selector: str, attribute: str) -> str:
            el = card.query_selector(selector)
            return el.get_attribute(attribute) or "" if el else ""

        import re as _re

        # Extract all card-level data before any page navigation
        campaign_id = attr("[data-campaign-id]", "data-campaign-id") or \
                      attr("a", "href").split("/")[-1]
        campaign_url = f"{self._base_url}/campaigns/{campaign_id}"

        card_title = text("[data-testid='campaign-title'], .campaign-title, h3")
        card_brand = text("[data-testid='brand-name'], .brand-name")
        pay_text = text(".pay-rate, [data-testid='pay-rate']")
        card_due = text(".due-date, [data-testid='due-date']")
        card_source = attr("a[data-source]", "data-source")

        payout_per_1k_views = None
        if pay_text:
            match = _re.search(r'\$\s*([0-9]+(?:\.[0-9]+)?)\s*(?:per\s*1k|/1k|\/1000|per\s*1000)', pay_text, _re.IGNORECASE)
            if match:
                payout_per_1k_views = float(match.group(1))

        # Navigate into the campaign detail page (this detaches the card handle)
        docs_url, source_url, raw_requirements = self._fetch_campaign_detail(
            campaign_url, pw_page
        )

        return {
            "id": campaign_id,
            "title": card_title,
            "brand": card_brand,
            "url": campaign_url,
            "pay": pay_text,
            "payout_per_1k_views": payout_per_1k_views,
            "due_date": card_due,
            "source_url": source_url or card_source,
            "docs_url": docs_url,
            "raw_requirements": raw_requirements,
        }

    def _fetch_campaign_detail(
        self, campaign_url: str, pw_page
    ) -> tuple[str | None, str | None, str | None]:
        """
        Navigate to the campaign detail page and extract:
        - docs_url: link to the requirements Google Doc / PDF
        - source_url: the video to clip
        - raw_requirements: page text for initial storage

        Returns (docs_url, source_url, raw_requirements).
        """
        import re

        try:
            pw_page.goto(campaign_url, wait_until="networkidle", timeout=20000)
            html = pw_page.content()
            page_text = pw_page.inner_text("main, body")[:3000]

            docs_url = None
            source_url = None

            # ── Docs file ──────────────────────────────────────────────
            # Google Docs links
            gdoc = re.search(
                r'https://docs\.google\.com/document/d/[A-Za-z0-9_-]+[^"\'>\s]*',
                html,
            )
            if gdoc:
                docs_url = gdoc.group(0).split("?")[0]

            # Google Drive file
            if not docs_url:
                gdrive = re.search(r'https://drive\.google\.com/file/d/[A-Za-z0-9_-]+', html)
                if gdrive:
                    docs_url = gdrive.group(0)

            # PDF links
            if not docs_url:
                pdf = re.search(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', html, re.IGNORECASE)
                if pdf:
                    href = pdf.group(1)
                    docs_url = href if href.startswith("http") else (
                        self._base_url.rstrip("/") + "/" + href.lstrip("/")
                    )

            # ── Source video URL ───────────────────────────────────────
            yt = re.search(r'https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)[A-Za-z0-9_-]+', html)
            if yt:
                source_url = yt.group(0)

            if not source_url:
                gdrive_src = re.search(r'https://drive\.google\.com/file/d/[A-Za-z0-9_-]+', html)
                if gdrive_src and gdrive_src.group(0) != docs_url:
                    source_url = gdrive_src.group(0)

            if not source_url:
                dbox = re.search(r'https://www\.dropbox\.com/[^\s"\']+', html)
                if dbox:
                    source_url = dbox.group(0)

            return docs_url, source_url, page_text

        except Exception as exc:
            self.logger.debug(f"Could not fetch campaign detail {campaign_url}: {exc}")
            return None, None, None

    def _upsert_campaign(self, raw: dict, page_id: str) -> bool:
        """Create campaign if it doesn't exist. Returns True if created."""
        from app.models.campaign import Campaign, CampaignStatus

        platform_id = raw.get("id", "")
        if not platform_id:
            return False

        existing = (
            self.db.query(Campaign)
            .filter(Campaign.platform_campaign_id == platform_id)
            .first()
        )
        if existing:
            return False

        campaign = Campaign(
            platform_campaign_id=platform_id,
            page_id=page_id,
            title=raw.get("title", "Untitled Campaign"),
            brand_name=raw.get("brand"),
            campaign_url=raw.get("url"),
            source_url=raw.get("source_url"),
            docs_url=raw.get("docs_url"),
            status=CampaignStatus.DISCOVERED,
            raw_requirements=raw.get("raw_requirements") or json.dumps(raw),
            payout_per_1k_views=raw.get("payout_per_1k_views"),
            max_payout_cap=raw.get("max_payout_cap"),
            platform_name=raw.get("platform_name", "Clipping.com"),
        )
        self.db.add(campaign)
        self.db.flush()

        self._audit("campaign", campaign.id, "created", metadata={"source": "hunter"})
        self.logger.info(f"New campaign discovered: {campaign.title[:60]} ({campaign.id})")

        # Trigger intelligence agent via Celery
        from app.workers.campaign_tasks import analyze_campaign
        analyze_campaign.apply_async(args=[campaign.id], queue="campaigns")

        return True

    # ------------------------------------------------------------------
    # AI-driven browser fallback (browser-use)
    # ------------------------------------------------------------------

    async def _fetch_campaigns_with_browser_use(self, page) -> list[dict]:
        """
        Use browser-use (AI-native browser agent) to discover campaigns.
        Resilient to DOM changes because Claude reads the page semantically
        rather than relying on hardcoded CSS selectors.
        """
        from langchain_anthropic import ChatAnthropic
        from browser_use import Agent as BrowserAgent

        base_url = (page.settings or {}).get("platform_base_url") or self.settings.clipping_base_url

        auth_method = self.settings.clipping_auth_method
        if auth_method == "discord":
            login_instruction = (
                f"Go to {base_url}/login, click the 'Login with Discord' button, "
                f"then on the Discord page enter email '{self.settings.clipping_email}' and "
                f"password '{self.settings.clipping_password}', click Login, then click Authorize if prompted."
            )
        else:
            login_instruction = (
                f"Go to {base_url}/login and log in with "
                f"email '{self.settings.clipping_email}' and password '{self.settings.clipping_password}'."
            )

        task = (
            f"{login_instruction} "
            f"Then navigate to {base_url}/campaigns and return a JSON list "
            "of all available campaign cards. Each item must have: id, title, brand, url, pay, due_date. "
            f"Return at most {self.settings.clipping_max_campaigns_per_scan} campaigns."
        )

        llm = ChatAnthropic(
            model=self.settings.ai_fast_model,
            api_key=self.settings.anthropic_api_key,
        )
        agent = BrowserAgent(task=task, llm=llm)
        result = await agent.run()

        raw = result.final_result() if hasattr(result, "final_result") else str(result)

        # Parse JSON from the agent's text output
        import json, re
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return []

    # ------------------------------------------------------------------
    # Development fallback
    # ------------------------------------------------------------------

    def _run_demo_mode(self) -> "AgentResult":
        """
        Seed realistic demo campaigns without hitting Clipping.com.
        Ensures demo Pages exist, then upserts demo campaigns onto them.
        """
        from app.models.page import Page
        import uuid as _uuid

        # Get or create the demo page
        demo_page = self.db.query(Page).filter(Page.platform_id == "demo-page").first()
        if not demo_page:
            demo_page = Page(
                id=str(_uuid.uuid4()),
                name="Demo Page",
                platform_id="demo-page",
                email="demo@example.com",
                is_active=True,
            )
            self.db.add(demo_page)
            self.db.flush()
            self.logger.info(f"Created demo page: {demo_page.id}")

        # Get or create the Muslim Clipping demo page
        muslim_page = self.db.query(Page).filter(Page.platform_id == "muslim-clipping-page").first()
        if not muslim_page:
            muslim_page = Page(
                id=str(_uuid.uuid4()),
                name="Muslim Clipping Profile",
                platform_id="muslim-clipping-page",
                email="muslimsclipping@example.com",
                is_active=True,
                settings={"platform_base_url": "https://muslimsclipping.com"}
            )
            self.db.add(muslim_page)
            self.db.flush()
            self.logger.info(f"Created Muslim Clipping page: {muslim_page.id}")

        raw_campaigns = self._demo_campaigns()
        new_count = 0
        for raw in raw_campaigns:
            try:
                # Route campaign to the corresponding page based on platform name
                target_page_id = muslim_page.id if raw.get("platform_name") == "MuslimsClipping.com" else demo_page.id
                created = self._upsert_campaign(raw, target_page_id)
                if created:
                    new_count += 1
            except Exception as exc:
                self.logger.error(f"Demo upsert failed for {raw.get('id')}: {exc}")

        return AgentResult.ok({
            "campaigns_found": new_count,
            "mode": "demo",
            "message": f"Demo mode: {new_count} campaigns seeded. Set CLIPPING_EMAIL + CLIPPING_PASSWORD in .env to connect to real Clipping.com.",
        })

    def _demo_campaigns(self) -> list[dict]:
        """Realistic demo campaigns representing multiple platforms ($2.50 to $6.50 CPM)."""
        ts = int(time.time())
        return [
            {
                "id": f"whop-finance-{ts}",
                "title": "Finance / Crypto Viral Clips (Whop Rewards)",
                "brand": "TradeMasters",
                "platform_name": "Whop",
                "url": "https://whop.com/content-rewards/finance-demo",
                "pay": "$5.00 per 1k views",
                "payout_per_1k_views": 5.00,
                "max_payout_cap": 5000.00,
                "due_date": "2026-07-30",
                "source_url": "https://cdn.pixabay.com/video/2020/02/17/32511-392669641_large.mp4",
                "requirements": {
                    "duration_min": 15, "duration_max": 60,
                    "aspect_ratio": "9:16", "platform": "TikTok",
                    "caption_required": True, "hook_required": True,
                    "resolution": "1080x1920", "fps": 30,
                },
            },
            {
                "id": f"whop-gaming-{ts}",
                "title": "Gaming Setup Reviews — 1k View Bounty",
                "brand": "GamerGear",
                "platform_name": "Whop",
                "url": "https://whop.com/content-rewards/gaming-demo",
                "pay": "$4.50 per 1k views",
                "payout_per_1k_views": 4.50,
                "max_payout_cap": 2500.00,
                "due_date": "2026-07-25",
                "source_url": "https://cdn.pixabay.com/video/2020/02/17/32511-392669641_large.mp4",
                "requirements": {
                    "duration_min": 10, "duration_max": 25,
                    "aspect_ratio": "9:16", "platform": "YouTube",
                    "caption_required": True, "hook_required": False,
                    "resolution": "1080x1920", "fps": 60,
                },
            },
            {
                "id": f"vyro-tech-{ts}",
                "title": "Tech Guru Shorts — High Payout",
                "brand": "TechGuru",
                "platform_name": "Vyro",
                "url": "https://vyro.com/bounties/tech-demo",
                "pay": "$4.00 per 1k views",
                "payout_per_1k_views": 4.00,
                "max_payout_cap": 10000.00,
                "due_date": "2026-07-30",
                "source_url": "https://cdn.pixabay.com/video/2020/02/17/32511-392669641_large.mp4",
                "requirements": {
                    "duration_min": 20, "duration_max": 45,
                    "aspect_ratio": "9:16", "platform": "Instagram",
                    "caption_required": True, "hook_required": True,
                    "resolution": "1080x1920", "fps": 30,
                },
            },
            {
                "id": f"muslimsclipping-lectures-{ts}",
                "title": "Islamic Lectures & Reminders short edits (Strictly Halal)",
                "brand": "FaithFirst",
                "platform_name": "MuslimsClipping.com",
                "url": "https://muslimsclipping.com/campaigns/lectures",
                "pay": "$6.50 per 1k views",
                "payout_per_1k_views": 6.50,
                "max_payout_cap": 3000.00,
                "due_date": "2026-08-15",
                "source_url": "https://cdn.pixabay.com/video/2020/02/17/32511-392669641_large.mp4",
                "requirements": {
                    "duration_min": 20, "duration_max": 45,
                    "aspect_ratio": "9:16", "platform": "TikTok",
                    "caption_required": True, "hook_required": True,
                    "resolution": "1080x1920", "fps": 30,
                },
            },
            {
                "id": f"clipping-techreview-{ts}",
                "title": "Tech Review Short Clips — YouTube Shorts",
                "brand": "GadgetVerse",
                "platform_name": "Clipping.com",
                "url": "https://clipping.com/campaigns/tech-review",
                "pay": "$4.20 per 1k views",
                "payout_per_1k_views": 4.20,
                "max_payout_cap": 4000.00,
                "due_date": "2026-07-28",
                "source_url": "https://cdn.pixabay.com/video/2020/02/17/32511-392669641_large.mp4",
                "requirements": {
                    "duration_min": 15, "duration_max": 50,
                    "aspect_ratio": "9:16", "platform": "YouTube",
                    "caption_required": True, "hook_required": True,
                    "resolution": "1080x1920", "fps": 30,
                },
            },
            {
                "id": f"clipping-cooking-lowpay-{ts}",
                "title": "Generic Cooking Clips — Low Pay Rate",
                "brand": "EasyBake",
                "platform_name": "Clipping.com",
                "url": "https://clipping.com/campaigns/cooking",
                "pay": "$2.50 per 1k views",
                "payout_per_1k_views": 2.50,
                "max_payout_cap": 500.00,
                "due_date": "2026-07-28",
                "source_url": "https://cdn.pixabay.com/video/2020/02/17/32511-392669641_large.mp4",
                "requirements": {
                    "duration_min": 30, "duration_max": 60,
                    "aspect_ratio": "9:16", "platform": "Instagram",
                    "caption_required": True, "hook_required": False,
                    "resolution": "1080x1920", "fps": 30,
                },
            },
        ]

    def _mock_campaigns(self) -> list[dict]:
        """Return mock data when Playwright is unavailable (dev/test)."""
        return self._demo_campaigns()
