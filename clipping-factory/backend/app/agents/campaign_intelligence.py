"""
CampaignIntelligenceAgent — uses Claude to parse campaign requirements
into a structured, machine-readable profile.

Extracts: duration, aspect ratio, platform, caption requirements,
hook style, due dates, payment, content restrictions, scoring criteria.
"""
from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent


class CampaignIntelligenceAgent(BaseAgent):
    name = "campaign_intelligence"

    def __init__(self, db: Session):
        super().__init__(db)

    def run(self, campaign_id: str) -> AgentResult:
        from app.models.campaign import Campaign, CampaignStatus

        campaign = self.db.query(Campaign).filter(Campaign.id == campaign_id).first()
        if not campaign:
            return AgentResult.fail(f"Campaign {campaign_id} not found")

        self.logger.info(f"Analyzing requirements for campaign: {campaign.title[:60]}")
        old_status = campaign.status

        # Try extracting requirements directly from raw_requirements JSON first
        parsed = self._extract_requirements_from_raw(campaign.raw_requirements)
        if parsed:
            self.logger.info("Requirements extracted directly from raw data (no AI needed)")
            return self._process_parsed_requirements(campaign, parsed, old_status)

        # Fetch requirements: campaign page + any linked docs file
        raw_text = campaign.raw_requirements or ""

        if campaign.campaign_url:
            scraped = self._scrape_requirements_page(campaign.campaign_url)
            if scraped:
                raw_text = scraped

        # If hunter already found a docs URL, fetch it directly too
        if campaign.docs_url:
            docs_content = self._fetch_docs_content(campaign.docs_url)
            if docs_content:
                raw_text += "\n\n--- REQUIREMENTS DOCUMENT (direct) ---\n" + docs_content[:6000]

        # Parse with AI
        parsed = self._parse_requirements_with_ai(campaign.title, raw_text)
        if not parsed:
            return AgentResult.fail("Failed to parse requirements")

        return self._process_parsed_requirements(campaign, parsed, old_status)

    def _process_parsed_requirements(self, campaign, parsed: dict, old_status: str) -> AgentResult:
        from app.models.campaign import CampaignStatus

        campaign.requirements = parsed
        campaign.opportunity_score = self._score_opportunity(parsed)
        campaign.intelligence_notes = parsed.get("notes", "")

        # Map payout and caps
        if parsed.get("payment_per_clip") is not None:
            campaign.payment_per_accepted_clip = float(parsed["payment_per_clip"])
        if parsed.get("payout_per_1k_views") is not None:
            campaign.payout_per_1k_views = float(parsed["payout_per_1k_views"])
        if parsed.get("max_payout_cap") is not None:
            campaign.max_payout_cap = float(parsed["max_payout_cap"])
        if parsed.get("due_date"):
            campaign.due_at = parsed["due_date"]
        if parsed.get("source_url") and not campaign.source_url:
            campaign.source_url = parsed["source_url"]

        # Check payout threshold (skip if below limit)
        payout = campaign.payout_per_1k_views
        if payout is not None and payout < self.settings.min_payout_per_1k_views:
            campaign.status = CampaignStatus.FAILED
            campaign.error_message = f"Skipped: payout per 1k views (${payout:.2f}) is below the minimum threshold (${self.settings.min_payout_per_1k_views:.2f})"
            self.db.flush()
            self._audit("campaign", campaign.id, "rejected_low_payout", old_status, CampaignStatus.FAILED)
            self.logger.info(f"Campaign {campaign.id} rejected due to low payout: ${payout:.2f}/1k views (min ${self.settings.min_payout_per_1k_views:.2f})")
            return AgentResult.ok({"status": "skipped_low_payout", "payout": payout})

        # Otherwise, transition to READY
        campaign.status = CampaignStatus.READY
        self.db.flush()
        self._audit("campaign", campaign.id, "requirements_parsed", old_status, CampaignStatus.READY)

        self.logger.info(
            f"Campaign {campaign.id} ready. Score: {campaign.opportunity_score:.2f} | "
            f"Pay rate: ${campaign.payout_per_1k_views or 0.0}/1k views | "
            f"Platform: {parsed.get('platform', 'unknown')}"
        )

        # Trigger content acquisition
        if campaign.source_url:
            from app.workers.video_tasks import acquire_content
            acquire_content.apply_async(args=[campaign.id], queue="acquisition")

        return AgentResult.ok({"requirements": parsed, "opportunity_score": campaign.opportunity_score})

    # ------------------------------------------------------------------

    def _scrape_requirements_page(self, url: str) -> str | None:
        """
        Fetch campaign details page + any linked docs file (Google Doc or PDF).
        Combines all text so Claude receives the full brief.
        """
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                ctx = browser.new_context()
                pw_page = ctx.new_page()
                pw_page.goto(url, wait_until="networkidle", timeout=30000)

                # Main page text
                page_text = pw_page.inner_text("main, .campaign-details, body") or ""

                # Find linked docs (Google Doc, PDF, or any downloadable brief)
                docs_url = self._find_docs_url(pw_page)
                browser.close()

            # Fetch docs content
            docs_text = ""
            if docs_url:
                self.logger.info(f"Found docs file: {docs_url}")
                docs_text = self._fetch_docs_content(docs_url) or ""

            combined = "\n\n--- CAMPAIGN PAGE ---\n" + page_text[:5000]
            if docs_text:
                combined += "\n\n--- REQUIREMENTS DOCUMENT ---\n" + docs_text[:6000]

            return combined.strip()[:12000]

        except Exception as exc:
            self.logger.warning(f"Could not scrape requirements page: {exc}")
            return None

    def _find_docs_url(self, pw_page) -> str | None:
        """
        Look for linked requirements documents on the campaign page.
        Handles Google Docs, Google Drive, PDF links, and embedded iframes.
        """
        import re

        page_html = pw_page.content()

        # Google Docs / Drive links
        gdoc_match = re.search(
            r'https://docs\.google\.com/document/d/[A-Za-z0-9_-]+[^"\'>\s]*',
            page_html,
        )
        if gdoc_match:
            return gdoc_match.group(0).split("?")[0]

        # Google Drive file links
        gdrive_match = re.search(
            r'https://drive\.google\.com/file/d/[A-Za-z0-9_-]+[^"\'>\s]*',
            page_html,
        )
        if gdrive_match:
            return gdrive_match.group(0)

        # PDF links
        pdf_match = re.search(r'href=["\']([^"\']*\.pdf[^"\']*)["\']', page_html, re.IGNORECASE)
        if pdf_match:
            href = pdf_match.group(1)
            if href.startswith("http"):
                return href
            # Relative URL
            base = self.settings.clipping_base_url
            return base.rstrip("/") + "/" + href.lstrip("/")

        # Iframe src pointing to a doc
        iframe_match = re.search(
            r'<iframe[^>]+src=["\']([^"\']*docs\.google\.com[^"\']*)["\']',
            page_html,
            re.IGNORECASE,
        )
        if iframe_match:
            return iframe_match.group(1)

        # Explicit "brief" or "requirements" download links
        brief_match = re.search(
            r'href=["\']([^"\']+)["\'][^>]*>(?:[^<]*)(brief|requirements?|doc|download)[^<]*</a',
            page_html,
            re.IGNORECASE,
        )
        if brief_match:
            href = brief_match.group(1)
            if href.startswith("http"):
                return href

        return None

    def _fetch_docs_content(self, url: str) -> str | None:
        """
        Fetch and extract text from a linked requirements document.
        Supports Google Docs (export as txt), PDFs, and plain text URLs.
        """
        import re

        try:
            # Google Docs → export as plain text
            doc_id_match = re.search(r"/document/d/([A-Za-z0-9_-]+)", url)
            if doc_id_match:
                doc_id = doc_id_match.group(1)
                export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
                return self._http_get_text(export_url)

            # Google Drive PDF or file
            drive_match = re.search(r"/file/d/([A-Za-z0-9_-]+)", url)
            if drive_match:
                file_id = drive_match.group(1)
                dl_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm=t"
                return self._fetch_pdf_text_from_url(dl_url)

            # Direct PDF
            if ".pdf" in url.lower():
                return self._fetch_pdf_text_from_url(url)

            # Fallback: fetch as plain text
            return self._http_get_text(url)

        except Exception as exc:
            self.logger.warning(f"Could not fetch docs content from {url}: {exc}")
            return None

    def _http_get_text(self, url: str) -> str | None:
        """Fetch a URL and return its text content."""
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        }
        response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
        response.raise_for_status()
        ct = response.headers.get("Content-Type", "")
        if "application/pdf" in ct:
            return self._extract_pdf_bytes(response.content)
        return response.text[:10000]

    def _fetch_pdf_text_from_url(self, url: str) -> str | None:
        """Download a PDF and extract its text."""
        import requests
        response = requests.get(url, timeout=60, allow_redirects=True)
        response.raise_for_status()
        return self._extract_pdf_bytes(response.content)

    def _extract_pdf_bytes(self, pdf_bytes: bytes) -> str | None:
        """Extract plain text from PDF bytes. Tries pdfplumber then PyPDF2."""
        import io

        # Try pdfplumber (richer extraction)
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text = "\n".join(
                    page.extract_text() or "" for page in pdf.pages[:20]
                )
                return text[:10000] if text.strip() else None
        except ImportError:
            pass
        except Exception as exc:
            self.logger.debug(f"pdfplumber failed: {exc}")

        # Fallback: PyPDF2
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            text = "\n".join(
                page.extract_text() or "" for page in reader.pages[:20]
            )
            return text[:10000] if text.strip() else None
        except ImportError:
            self.logger.warning("Neither pdfplumber nor PyPDF2 installed — PDF not parsed")
            return None
        except Exception as exc:
            self.logger.debug(f"PyPDF2 failed: {exc}")
            return None

    def _extract_requirements_from_raw(self, raw_json: str | None) -> dict | None:
        """Try to extract structured requirements from raw_requirements JSON without AI."""
        if not raw_json:
            return None
        import json as _json
        try:
            data = _json.loads(raw_json)
            reqs = data.get("requirements") or data.get("parsed") or {}
            if not isinstance(reqs, dict):
                reqs = {}
            required = {"platform", "duration_min", "duration_max"}
            if required.intersection(reqs.keys()):
                schema_fields = {
                    "platform", "aspect_ratio", "resolution", "fps",
                    "duration_min", "duration_max", "caption_required",
                    "caption_style", "hook_required", "hook_style",
                    "payment_per_clip", "currency", "due_date", "source_url",
                    "content_category", "max_submissions", "banned_words",
                    "required_keywords", "style_notes", "difficulty", "notes",
                }
                return {k: v for k, v in reqs.items() if k in schema_fields}
        except (_json.JSONDecodeError, TypeError):
            pass
        return None

    # Niche RPM multipliers (from 2026 clipping economy research)
    # Finance, Tech/SaaS, and Streaming/IRL have the highest CPMs
    _NICHE_RPM = {
        "finance":          5.0,   # $3-5 CPM, high conversion
        "tech":             4.0,   # $3-5 CPM, SaaS audience
        "saas":             4.0,
        "crypto":           4.5,   # $3-6 CPM, volatile but high
        "streaming":        3.5,   # $100-300 RPM for IRL
        "irl":              3.0,
        "gaming":           2.5,   # $2-3 CPM
        "real_estate":      3.0,   # $2-4 CPM
        "health":           3.0,   # $2-4 CPM
        "fitness":          2.5,   # $2-3 CPM
        "education":        2.0,   # $1-3 CPM
        "entertainment":    1.5,   # $1-2 CPM
        "general":          1.0,   # baseline
    }

    _DEFAULT_NICHE = "general"

    _REQUIREMENTS_SCHEMA = {
        "type": "object",
        "properties": {
            "platform":           {"type": ["string", "null"], "enum": ["TikTok", "Instagram Reels", "YouTube Shorts", "general", None]},
            "aspect_ratio":       {"type": ["string", "null"], "enum": ["9:16", "16:9", "1:1", None]},
            "resolution":         {"type": ["string", "null"]},
            "fps":                {"type": ["number", "null"]},
            "duration_min":       {"type": ["number", "null"]},
            "duration_max":       {"type": ["number", "null"]},
            "caption_required":   {"type": ["boolean", "null"]},
            "caption_style":      {"type": ["string", "null"]},
            "hook_required":      {"type": ["boolean", "null"]},
            "hook_style":         {"type": ["string", "null"]},
            "payment_per_clip":   {"type": ["number", "null"]},
            "payout_per_1k_views": {"type": ["number", "null"]},
            "max_payout_cap":      {"type": ["number", "null"]},
            "currency":           {"type": ["string", "null"]},
            "max_submissions":    {"type": ["integer", "null"]},
            "due_date":           {"type": ["string", "null"]},
            "source_url":         {"type": ["string", "null"]},
            "content_category":   {"type": ["string", "null"]},
            "banned_words":       {"type": "array",  "items": {"type": "string"}},
            "required_keywords":  {"type": "array",  "items": {"type": "string"}},
            "style_notes":        {"type": ["string", "null"]},
            "difficulty":         {"type": ["string", "null"], "enum": ["easy", "medium", "hard", None]},
            "notes":              {"type": ["string", "null"]},
        },
        "required": ["platform", "duration_min", "duration_max"],
    }

    _SYSTEM_PROMPT = (
        "You are a campaign analyst for a video clipping platform. "
        "Extract campaign requirements precisely and completely. "
        "Use null for any field not mentioned in the brief."
    )

    def _parse_requirements_with_ai(self, title: str, raw_text: str) -> dict | None:
        """Send requirements text to Claude for structured extraction via tool_use."""
        from app.services.ai_service import AIService

        ai = AIService()
        prompt = (
            f"Campaign Title: {title}\n\n"
            f"Raw Requirements:\n{raw_text[:6000]}\n\n"
            "Extract all campaign requirements using the structured_output tool."
        )

        result = ai.complete_structured(
            prompt,
            schema=self._REQUIREMENTS_SCHEMA,
            model=self.settings.ai_fast_model,
            system=self._SYSTEM_PROMPT,
            cache_system=True,
        )

        if result is None:
            self.logger.error("Structured requirements extraction returned None")
        return result

    def _score_opportunity(self, requirements: dict) -> float:
        """
        Score 0.0 to 1.0 based on how attractive the campaign is.
        Factors: payment, niche RPM, difficulty, platform, duration, urgency.
        """
        score = 0.5  # baseline

        # Payment per clip
        pay = requirements.get("payment_per_clip") or 0
        if pay >= 50:
            score += 0.2
        elif pay >= 25:
            score += 0.1
        elif pay >= 10:
            score += 0.05

        # Niche RPM multiplier (high-CPM niches score higher)
        niche = (requirements.get("content_category") or "").lower()
        rpm = self._NICHE_RPM.get(niche, self._NICHE_RPM.get(self._DEFAULT_NICHE, 1.0))
        if rpm >= 4.0:
            score += 0.25   # finance, crypto, tech
        elif rpm >= 3.0:
            score += 0.15   # real estate, health, streaming
        elif rpm >= 2.0:
            score += 0.05   # gaming, fitness, education
        # general/baseline gets no bonus

        # Difficulty
        difficulty = requirements.get("difficulty", "medium")
        if difficulty == "easy":
            score += 0.1
        elif difficulty == "hard":
            score -= 0.1

        # Platform (known platforms easier to target)
        if requirements.get("platform") in ("TikTok", "Instagram Reels", "YouTube Shorts"):
            score += 0.05

        # Reasonable duration
        dur_max = requirements.get("duration_max") or 60
        if 30 <= dur_max <= 90:
            score += 0.05

        # Due date urgency (penalize very close deadlines)
        due = requirements.get("due_date")
        if due:
            try:
                from datetime import date
                days_left = (date.fromisoformat(due) - date.today()).days
                if days_left < 1:
                    score -= 0.4
                elif days_left < 3:
                    score -= 0.1
            except Exception:
                pass

        return max(0.0, min(1.0, score))

    def projected_rpm(self, requirements: dict) -> float:
        """Return estimated RPM for this campaign based on niche."""
        niche = (requirements.get("content_category") or "").lower()
        return self._NICHE_RPM.get(niche, self._NICHE_RPM.get(self._DEFAULT_NICHE, 1.0))

    def projected_cpm(self, requirements: dict) -> float:
        """Return estimated CPM for the platform."""
        platform = requirements.get("platform", "TikTok")
        from app.models.social_post import SocialPlatform
        return SocialPlatform.estimated_cpm(platform.lower().replace(" ", "_"))
