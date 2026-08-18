"""
GTM FACEBOOK INTELLIGENCE ADAPTER
=============================================================================
Harvests Facebook Groups, Pages, and marketplace signals for GTM lead discovery.

Data Sources:
  1. RapidAPI facebook-scraper-api4 — Groups/Pages search and post scraping
  2. RapidAPI local-business-data   — Cross-reference company contacts
  3. Graceful degradation           — Falls back to Local Business Data if Facebook API 403s

Safety:
  All results are normalized into the standard BuyerHunterAdapter evidence card
  format. No data is fabricated — missing fields are flagged, not filled.
=============================================================================
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
LOGS_DIR = ROOT_DIR / "MBM" / "LeadEngine" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
FB_INTEL_LOG = LOGS_DIR / "gtm_facebook_intel.json"
FB_PROSPECTS_FILE = ARTIFACTS_DIR / "gtm_facebook_prospects.json"

try:
    from dotenv import load_dotenv
    for env_file in [ROOT_DIR / ".env.local", ROOT_DIR / ".env"]:
        if env_file.exists():
            load_dotenv(env_file)
except Exception:
    pass

try:
    import requests
except ImportError:
    requests = None

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")

# RapidAPI endpoint configuration
FB_SCRAPER_HOST = "facebook-scraper-api4.p.rapidapi.com"
LOCAL_BIZ_HOST = "local-business-data.p.rapidapi.com"

# Default search queries for B2B intelligence
DEFAULT_GROUP_KEYWORDS = [
    "AI automation business owners",
    "real estate investors wholesale",
    "construction technology",
    "agency owners SaaS",
    "small business automation",
]

DEFAULT_PAGE_QUERIES = [
    "AI automation agency",
    "real estate investment company",
    "construction technology software",
    "business process automation",
]

# Pain signal keywords for intent classification
PAIN_KEYWORDS = [
    "struggling with", "anyone know", "looking for", "need help",
    "recommendation", "how do you", "what tool", "frustrated",
    "manual process", "too expensive", "wasting time", "hiring",
    "can't find", "bottleneck", "scaling", "overwhelmed",
    "automating", "spreadsheet", "pain point", "problem",
]

# Event bus import
try:
    from MBM.LeadEngine.gtm.event_bus import GtmEvent, GtmEventType, GtmEventBus
    _HAS_EVENT_BUS = True
except Exception:
    _HAS_EVENT_BUS = False


def _rapidapi_headers(host: str) -> Dict[str, str]:
    return {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": host,
    }


class FacebookIntelAdapter:
    """
    Facebook Intelligence Adapter for the GTM pipeline.

    Harvests Groups, Pages, and pain signal posts from Facebook
    via RapidAPI, with fallback to Local Business Data.
    """

    def __init__(self, event_bus: Optional[Any] = None):
        self._event_bus = event_bus
        self._fb_available: Optional[bool] = None

    # -- Availability check ----------------------------------------------

    def _check_fb_api(self) -> bool:
        """Check if Facebook Scraper API is accessible."""
        if self._fb_available is not None:
            return self._fb_available
        if not requests or not RAPIDAPI_KEY:
            self._fb_available = False
            return False
        try:
            resp = requests.get(
                f"https://{FB_SCRAPER_HOST}/",
                headers=_rapidapi_headers(FB_SCRAPER_HOST),
                timeout=5,
            )
            self._fb_available = resp.status_code != 403
        except Exception:
            self._fb_available = False
        return self._fb_available

    # -- Facebook Groups -------------------------------------------------

    def search_groups(self, keywords: Optional[List[str]] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search Facebook Groups matching industry keywords.
        Returns group metadata with member counts.
        """
        keywords = keywords or DEFAULT_GROUP_KEYWORDS
        groups = []

        if not self._check_fb_api():
            self._log("WARN", "Facebook API unavailable — skipping group search")
            return groups

        for kw in keywords:
            try:
                resp = requests.get(
                    f"https://{FB_SCRAPER_HOST}/v2/search_groups",
                    headers=_rapidapi_headers(FB_SCRAPER_HOST),
                    params={"query": kw, "limit": str(min(limit, 10))},
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("data", data.get("results", []))
                    if isinstance(results, list):
                        for item in results:
                            groups.append({
                                "id": item.get("id") or item.get("group_id", ""),
                                "name": item.get("name", ""),
                                "description": (item.get("description") or "")[:300],
                                "member_count": item.get("member_count", item.get("members", 0)),
                                "privacy": item.get("privacy", "UNKNOWN"),
                                "url": item.get("url") or f"https://facebook.com/groups/{item.get('id', '')}",
                                "keyword": kw,
                                "source": "facebook-scraper-api4",
                            })
                elif resp.status_code == 403:
                    self._fb_available = False
                    self._log("WARN", f"Facebook API returned 403 for groups search: {kw}")
                    break
            except Exception as e:
                self._log("ERROR", f"Groups search failed for '{kw}': {e}")

        self._log("INFO", f"Found {len(groups)} groups across {len(keywords)} keyword searches")
        return groups[:limit]

    # -- Facebook Pages --------------------------------------------------

    def search_pages(self, query: Optional[str] = None, queries: Optional[List[str]] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Search Facebook Pages for companies and extract contact info.
        Falls back to Local Business Data if Facebook API is unavailable.
        """
        search_queries = queries or ([query] if query else DEFAULT_PAGE_QUERIES)
        pages = []

        if self._check_fb_api():
            for q in search_queries:
                try:
                    resp = requests.get(
                        f"https://{FB_SCRAPER_HOST}/v2/search_pages",
                        headers=_rapidapi_headers(FB_SCRAPER_HOST),
                        params={"query": q, "limit": str(min(limit, 10))},
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        results = data.get("data", data.get("results", []))
                        if isinstance(results, list):
                            for item in results:
                                pages.append({
                                    "id": item.get("id") or item.get("page_id", ""),
                                    "name": item.get("name", ""),
                                    "category": item.get("category", ""),
                                    "description": (item.get("description") or "")[:300],
                                    "followers": item.get("followers", item.get("fan_count", 0)),
                                    "phone": item.get("phone", ""),
                                    "email": item.get("email", ""),
                                    "website": item.get("website", ""),
                                    "url": item.get("url") or f"https://facebook.com/{item.get('id', '')}",
                                    "location": item.get("location", {}) if isinstance(item.get("location"), dict) else {},
                                    "query": q,
                                    "source": "facebook-scraper-api4",
                                })
                except Exception as e:
                    self._log("ERROR", f"Pages search failed for '{q}': {e}")
        else:
            # Fallback to Local Business Data API
            self._log("INFO", "Using Local Business Data fallback for page discovery")
            pages = self._local_business_fallback(search_queries, limit)

        self._log("INFO", f"Found {len(pages)} pages/businesses across {len(search_queries)} queries")
        return pages[:limit]

    # -- Group Post Scraping ---------------------------------------------

    def scrape_group_posts(self, group_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Scrape recent posts from a Facebook Group for pain signal mining.
        """
        posts = []
        if not self._check_fb_api() or not group_id:
            return posts

        try:
            resp = requests.get(
                f"https://{FB_SCRAPER_HOST}/v2/group_posts",
                headers=_rapidapi_headers(FB_SCRAPER_HOST),
                params={"group_id": str(group_id), "limit": str(limit)},
                timeout=20,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", data.get("posts", []))
                if isinstance(results, list):
                    for item in results:
                        text = item.get("text") or item.get("message") or item.get("content") or ""
                        posts.append({
                            "post_id": item.get("id") or item.get("post_id", ""),
                            "text": text[:1000],
                            "author": item.get("author") or item.get("user_name", ""),
                            "timestamp": item.get("timestamp") or item.get("created_at", ""),
                            "reactions": item.get("reactions", item.get("likes", 0)),
                            "comments": item.get("comments_count", item.get("comments", 0)),
                            "group_id": group_id,
                            "source": "facebook-scraper-api4",
                        })
        except Exception as e:
            self._log("ERROR", f"Group post scrape failed for group {group_id}: {e}")

        return posts

    # -- Contact Enrichment ----------------------------------------------

    def enrich_with_local_business(self, company_name: str, location: str = "") -> Dict[str, Any]:
        """
        Cross-reference a company name with Local Business Data API
        to get verified phone/email/address.
        """
        if not requests or not RAPIDAPI_KEY:
            return {"status": "NO_API_KEY", "company": company_name}

        query = f"{company_name} {location}".strip()
        try:
            resp = requests.get(
                f"https://{LOCAL_BIZ_HOST}/search",
                headers=_rapidapi_headers(LOCAL_BIZ_HOST),
                params={"query": query, "limit": "3", "language": "en"},
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                results = data.get("data", [])
                if results and isinstance(results, list):
                    best = results[0]
                    return {
                        "status": "ENRICHED",
                        "company": best.get("name", company_name),
                        "phone": best.get("phone_number") or best.get("international_phone_number", ""),
                        "email": best.get("email", ""),
                        "address": best.get("address", ""),
                        "website": best.get("website", ""),
                        "rating": best.get("rating", 0),
                        "reviews": best.get("reviews", 0),
                        "place_id": best.get("place_id", ""),
                        "source": "local-business-data",
                    }
        except Exception as e:
            self._log("ERROR", f"Local business enrichment failed for '{company_name}': {e}")

        return {"status": "NOT_FOUND", "company": company_name}

    # -- Intent Signal Extraction ----------------------------------------

    def extract_intent_signals(self, posts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Classify Facebook posts into pain/intent signal categories.
        Returns only posts with identified pain signals.
        """
        signals = []
        for post in posts:
            text = (post.get("text") or "").lower()
            matched = [kw for kw in PAIN_KEYWORDS if kw in text]
            if matched:
                signal = {
                    "post_id": post.get("post_id", ""),
                    "text_preview": post.get("text", "")[:300],
                    "author": post.get("author", ""),
                    "pain_keywords": matched,
                    "pain_score": min(100, len(matched) * 15 + 20),
                    "group_id": post.get("group_id", ""),
                    "source": "facebook_intent_classifier",
                    "timestamp": post.get("timestamp", ""),
                }
                signals.append(signal)

                # Emit event if bus available
                self._emit_event("FACEBOOK_SIGNAL", post.get("post_id", "UNKNOWN"), {
                    "author": post.get("author", ""),
                    "pain_score": signal["pain_score"],
                    "keywords": matched[:5],
                })

        signals.sort(key=lambda s: s["pain_score"], reverse=True)
        self._log("INFO", f"Extracted {len(signals)} intent signals from {len(posts)} posts")
        return signals

    # -- Full Sweep Pipeline ---------------------------------------------

    def run_full_sweep(
        self,
        group_keywords: Optional[List[str]] = None,
        page_queries: Optional[List[str]] = None,
        scrape_top_groups: int = 3,
    ) -> Dict[str, Any]:
        """
        Run a complete Facebook intelligence sweep:
        1. Search groups
        2. Search pages
        3. Scrape top groups for posts
        4. Extract pain signals
        5. Enrich top prospects with Local Business Data
        6. Save results
        """
        print("[FB INTEL] Starting full Facebook intelligence sweep...")

        # 1. Groups
        groups = self.search_groups(group_keywords)
        print(f"[FB INTEL] Found {len(groups)} groups")

        # 2. Pages
        pages = self.search_pages(queries=page_queries)
        print(f"[FB INTEL] Found {len(pages)} pages/businesses")

        # 3. Scrape top groups
        all_posts = []
        top = sorted(groups, key=lambda g: g.get("member_count", 0), reverse=True)[:scrape_top_groups]
        for g in top:
            gid = g.get("id")
            if gid:
                posts = self.scrape_group_posts(gid, limit=30)
                all_posts.extend(posts)
                print(f"[FB INTEL]   Scraped {len(posts)} posts from '{g.get('name', gid)}'")

        # 4. Intent signals
        signals = self.extract_intent_signals(all_posts)
        print(f"[FB INTEL] Classified {len(signals)} pain signals from {len(all_posts)} posts")

        # 5. Enrich top page prospects
        enriched = []
        for page in pages[:10]:
            if page.get("phone") or page.get("email"):
                enriched.append({**page, "enrichment_status": "ALREADY_ENRICHED"})
            else:
                enrichment = self.enrich_with_local_business(
                    page.get("name", ""),
                    str(page.get("location", {}).get("city", "")),
                )
                enriched.append({**page, **enrichment})
        print(f"[FB INTEL] Enriched {len(enriched)} prospects with contact data")

        # 6. Save
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "groups_found": len(groups),
            "pages_found": len(pages),
            "posts_scraped": len(all_posts),
            "intent_signals": len(signals),
            "enriched_prospects": len(enriched),
            "groups": groups,
            "pages": pages,
            "signals": signals[:20],
            "prospects": enriched,
        }
        FB_PROSPECTS_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"[FB INTEL] Results saved to {FB_PROSPECTS_FILE}")

        return result

    # -- Fallback --------------------------------------------------------

    def _local_business_fallback(self, queries: List[str], limit: int) -> List[Dict[str, Any]]:
        """Use Local Business Data API when Facebook API is unavailable."""
        results = []
        if not requests or not RAPIDAPI_KEY:
            return results

        for q in queries:
            try:
                resp = requests.get(
                    f"https://{LOCAL_BIZ_HOST}/search",
                    headers=_rapidapi_headers(LOCAL_BIZ_HOST),
                    params={"query": q, "limit": str(min(limit, 10)), "language": "en"},
                    timeout=15,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    for item in data.get("data", []):
                        fb_url = item.get("facebook_url", "")
                        website = item.get("website", "")
                        if "facebook.com" in (website or "").lower():
                            fb_url = fb_url or website
                        results.append({
                            "id": item.get("place_id", ""),
                            "name": item.get("name", ""),
                            "category": item.get("type", ""),
                            "phone": item.get("phone_number") or item.get("international_phone_number", ""),
                            "email": item.get("email", ""),
                            "website": website,
                            "url": fb_url or "",
                            "address": item.get("address", ""),
                            "query": q,
                            "source": "local-business-data-fallback",
                        })
            except Exception as e:
                self._log("ERROR", f"Local business fallback failed for '{q}': {e}")

        return results[:limit]

    # -- Logging & Events ------------------------------------------------

    def _log(self, level: str, message: str) -> None:
        record = {
            "level": level,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        existing = []
        if FB_INTEL_LOG.exists():
            try:
                existing = json.loads(FB_INTEL_LOG.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        existing.append(record)
        # Keep last 500 entries
        if len(existing) > 500:
            existing = existing[-500:]
        FB_INTEL_LOG.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def _emit_event(self, event_type_name: str, entity_id: str, payload: Dict[str, Any]) -> None:
        if not _HAS_EVENT_BUS or not self._event_bus:
            return
        try:
            etype = GtmEventType(event_type_name)
            event = GtmEvent(
                event_type=etype,
                entity_id=entity_id,
                producer="FacebookIntelAdapter",
                payload=payload,
            )
            self._event_bus.publish(event)
        except (ValueError, Exception):
            pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=" * 70)
    print("GTM FACEBOOK INTELLIGENCE ADAPTER")
    print(f"RapidAPI Key: {'✅ Present' if RAPIDAPI_KEY else '❌ Missing'}")
    print("=" * 70)

    adapter = FacebookIntelAdapter()

    if "--sweep" in sys.argv:
        adapter.run_full_sweep()
    else:
        print("\nQuick page search test...")
        pages = adapter.search_pages("AI automation agency", limit=5)
        for p in pages[:5]:
            print(f"  📄 {p.get('name', 'N/A')} | ☎ {p.get('phone', 'N/A')} | 🌐 {p.get('website', 'N/A')}")
        print(f"\nRun with --sweep for a full intelligence sweep")
