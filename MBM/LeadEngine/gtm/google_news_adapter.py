"""
GTM GOOGLE NEWS SIGNAL ADAPTER
=============================================================================
Harvests Google News RSS for industry pain signals, funding announcements,
hiring surges, and company-specific events that indicate buyer intent.

Data Source:
  Google News RSS (free, no API key required)
  https://news.google.com/rss/search?q=<query>&hl=en-US&gl=US&ceid=US:en

Signal Classification:
  - PAIN: cost overruns, layoffs, manual processes, compliance failures
  - GROWTH: funding, expansion, acquisition, new market entry
  - HIRING: talent shortages, open positions, scaling challenges
  - TECHNOLOGY: digital transformation, automation adoption, AI implementation
=============================================================================
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
LOGS_DIR = ROOT_DIR / "MBM" / "LeadEngine" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
NEWS_LOG = LOGS_DIR / "gtm_news_signals.json"
NEWS_ARTIFACTS_FILE = ARTIFACTS_DIR / "gtm_news_intel.json"

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

# Event bus import
try:
    from MBM.LeadEngine.gtm.event_bus import GtmEvent, GtmEventType, GtmEventBus
    _HAS_EVENT_BUS = True
except Exception:
    _HAS_EVENT_BUS = False

# Google News RSS base URL (no API key needed)
GNEWS_RSS_BASE = "https://news.google.com/rss/search"

# Default industry verticals to monitor
DEFAULT_VERTICALS = [
    "AI automation business",
    "construction technology",
    "real estate investment",
    "SaaS startup funding",
    "business process automation",
]

# Default company monitoring list (empty — populated per user)
DEFAULT_COMPANIES: List[str] = []

# Signal classification keywords
SIGNAL_CATEGORIES = {
    "PAIN": [
        "cost overrun", "budget overrun", "layoffs", "downsizing",
        "manual process", "compliance failure", "penalty", "fine",
        "shortage", "bottleneck", "delay", "backlog", "inefficiency",
        "waste", "loss", "declining", "struggling", "bankruptcy",
        "shut down", "closing", "failed", "recall", "sued",
    ],
    "GROWTH": [
        "funding", "raised", "series a", "series b", "ipo",
        "expansion", "acquisition", "acquired", "partnership",
        "new market", "revenue growth", "record revenue",
        "scaling", "new office", "headquarters", "valuation",
    ],
    "HIRING": [
        "hiring", "open positions", "talent shortage", "recruiting",
        "head of", "VP of", "looking for", "job posting",
        "workforce", "staffing", "team growth", "scaling team",
    ],
    "TECHNOLOGY": [
        "AI", "artificial intelligence", "machine learning",
        "automation", "digital transformation", "cloud migration",
        "robotic process", "chatbot", "generative ai",
        "no-code", "low-code", "SaaS", "platform",
    ],
}


def _parse_rss_date(date_str: str) -> Optional[datetime]:
    """Parse RSS pubDate format into datetime."""
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            continue
    return None


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text or "").strip()


class GoogleNewsAdapter:
    """
    Google News RSS adapter for GTM pipeline signal harvesting.

    No API key required — uses the free Google News RSS endpoint.
    """

    def __init__(self, event_bus: Optional[Any] = None):
        self._event_bus = event_bus

    # -- Core search -----------------------------------------------------

    def search_news(
        self,
        query: str,
        days_back: int = 7,
        language: str = "en",
        country: str = "US",
    ) -> List[Dict[str, Any]]:
        """
        Search Google News RSS for articles matching a query.
        Returns parsed article metadata with title, source, date, link.
        """
        if not requests:
            self._log("ERROR", "requests library not available")
            return []

        params = {
            "q": query,
            "hl": f"{language}-{country}",
            "gl": country,
            "ceid": f"{country}:{language}",
        }

        articles = []
        try:
            resp = requests.get(
                GNEWS_RSS_BASE,
                params=params,
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0 (MBM GTM NewsAgent)"},
            )
            if resp.status_code != 200:
                self._log("WARN", f"Google News returned status {resp.status_code} for query: {query}")
                return []

            root = ET.fromstring(resp.content)
            channel = root.find("channel")
            if channel is None:
                return []

            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)

            for item in channel.findall("item"):
                title = _strip_html(item.findtext("title", ""))
                link = item.findtext("link", "")
                pub_date_str = item.findtext("pubDate", "")
                source_el = item.find("source")
                source = source_el.text if source_el is not None else ""
                description = _strip_html(item.findtext("description", ""))

                pub_date = _parse_rss_date(pub_date_str)

                # Filter by date
                if pub_date and pub_date < cutoff:
                    continue

                articles.append({
                    "title": title,
                    "link": link,
                    "source": source,
                    "published": pub_date.isoformat() if pub_date else pub_date_str,
                    "description": description[:500],
                    "query": query,
                })

        except ET.ParseError as e:
            self._log("ERROR", f"RSS XML parse error for query '{query}': {e}")
        except Exception as e:
            self._log("ERROR", f"Google News search failed for '{query}': {e}")

        self._log("INFO", f"Found {len(articles)} articles for query: '{query}'")
        return articles

    # -- Company monitoring ----------------------------------------------

    def monitor_companies(self, company_names: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Monitor specific companies for newsworthy events
        (funding, hiring, expansion, lawsuits, etc.).
        """
        companies = company_names or DEFAULT_COMPANIES
        all_articles = []

        for company in companies:
            articles = self.search_news(f'"{company}"', days_back=14)
            for article in articles:
                article["monitored_company"] = company
            all_articles.extend(articles)
            print(f"[NEWS] {company}: {len(articles)} articles")

        return all_articles

    # -- Pain signal extraction ------------------------------------------

    def extract_pain_signals(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Classify news articles into signal categories (PAIN, GROWTH, HIRING, TECHNOLOGY).
        Returns only articles with identified signals, sorted by relevance.
        """
        signals = []

        for article in articles:
            text = f"{article.get('title', '')} {article.get('description', '')}".lower()
            matched_categories: Dict[str, List[str]] = {}

            for category, keywords in SIGNAL_CATEGORIES.items():
                matched = [kw for kw in keywords if kw.lower() in text]
                if matched:
                    matched_categories[category] = matched

            if not matched_categories:
                continue

            # Determine primary category (most keyword matches)
            primary = max(matched_categories.items(), key=lambda x: len(x[1]))

            signal = {
                "title": article.get("title", ""),
                "link": article.get("link", ""),
                "source": article.get("source", ""),
                "published": article.get("published", ""),
                "description": article.get("description", ""),
                "query": article.get("query", ""),
                "monitored_company": article.get("monitored_company", ""),
                "primary_signal": primary[0],
                "signal_keywords": primary[1],
                "all_signals": {k: v for k, v in matched_categories.items()},
                "signal_strength": sum(len(v) for v in matched_categories.values()),
                "classifier": "gtm_news_signal_classifier",
            }
            signals.append(signal)

            # Emit event for high-strength signals
            if signal["signal_strength"] >= 2:
                self._emit_event("NEWS_SIGNAL", article.get("query", "UNKNOWN"), {
                    "title": signal["title"][:200],
                    "primary_signal": signal["primary_signal"],
                    "strength": signal["signal_strength"],
                    "source": signal["source"],
                })

        signals.sort(key=lambda s: s["signal_strength"], reverse=True)
        self._log("INFO", f"Classified {len(signals)} signals from {len(articles)} articles")
        return signals

    # -- Vertical trends -------------------------------------------------

    def get_trending_verticals(self, verticals: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Scan industry verticals for trending topics and volume.
        Returns a summary per vertical with article counts and top signals.
        """
        verticals = verticals or DEFAULT_VERTICALS
        trends = []

        for vertical in verticals:
            articles = self.search_news(vertical, days_back=7)
            signals = self.extract_pain_signals(articles)

            pain_count = sum(1 for s in signals if s["primary_signal"] == "PAIN")
            growth_count = sum(1 for s in signals if s["primary_signal"] == "GROWTH")
            hiring_count = sum(1 for s in signals if s["primary_signal"] == "HIRING")
            tech_count = sum(1 for s in signals if s["primary_signal"] == "TECHNOLOGY")

            trends.append({
                "vertical": vertical,
                "total_articles": len(articles),
                "total_signals": len(signals),
                "pain_signals": pain_count,
                "growth_signals": growth_count,
                "hiring_signals": hiring_count,
                "technology_signals": tech_count,
                "top_headlines": [s["title"] for s in signals[:5]],
            })

            print(f"[NEWS] {vertical}: {len(articles)} articles, {len(signals)} signals (P:{pain_count} G:{growth_count} H:{hiring_count} T:{tech_count})")

        return trends

    # -- Full Scan Pipeline ----------------------------------------------

    def run_full_scan(
        self,
        verticals: Optional[List[str]] = None,
        companies: Optional[List[str]] = None,
        days_back: int = 7,
    ) -> Dict[str, Any]:
        """
        Run a complete Google News intelligence scan:
        1. Scan industry verticals
        2. Monitor named companies
        3. Extract and classify all signals
        4. Save results
        """
        print("[NEWS SCAN] Starting full Google News intelligence scan...")

        # 1. Vertical trends
        trends = self.get_trending_verticals(verticals)

        # 2. Company monitoring
        company_articles = []
        if companies:
            company_articles = self.monitor_companies(companies)

        # 3. Collect all signals from all verticals
        all_articles = []
        verts = verticals or DEFAULT_VERTICALS
        for v in verts:
            all_articles.extend(self.search_news(v, days_back=days_back))
        all_articles.extend(company_articles)

        all_signals = self.extract_pain_signals(all_articles)

        # 4. Save
        result = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "verticals_scanned": len(trends),
            "companies_monitored": len(companies or []),
            "total_articles": len(all_articles),
            "total_signals": len(all_signals),
            "trends": trends,
            "top_pain_signals": [s for s in all_signals if s["primary_signal"] == "PAIN"][:20],
            "top_growth_signals": [s for s in all_signals if s["primary_signal"] == "GROWTH"][:10],
            "top_hiring_signals": [s for s in all_signals if s["primary_signal"] == "HIRING"][:10],
            "top_technology_signals": [s for s in all_signals if s["primary_signal"] == "TECHNOLOGY"][:10],
        }
        NEWS_ARTIFACTS_FILE.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"[NEWS SCAN] Results saved to {NEWS_ARTIFACTS_FILE}")
        print(f"[NEWS SCAN] Summary: {len(all_articles)} articles → {len(all_signals)} classified signals")

        return result

    # -- Logging & Events ------------------------------------------------

    def _log(self, level: str, message: str) -> None:
        record = {
            "level": level,
            "message": message,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        existing = []
        if NEWS_LOG.exists():
            try:
                existing = json.loads(NEWS_LOG.read_text(encoding="utf-8"))
            except Exception:
                existing = []
        existing.append(record)
        if len(existing) > 500:
            existing = existing[-500:]
        NEWS_LOG.write_text(json.dumps(existing, indent=2), encoding="utf-8")

    def _emit_event(self, event_type_name: str, entity_id: str, payload: Dict[str, Any]) -> None:
        if not _HAS_EVENT_BUS or not self._event_bus:
            return
        try:
            etype = GtmEventType(event_type_name)
            event = GtmEvent(
                event_type=etype,
                entity_id=entity_id,
                producer="GoogleNewsAdapter",
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
    print("GTM GOOGLE NEWS SIGNAL ADAPTER")
    print("=" * 70)

    adapter = GoogleNewsAdapter()

    if "--scan" in sys.argv:
        # Full scan with optional company monitoring
        companies = []
        for i, arg in enumerate(sys.argv):
            if arg == "--companies" and i + 1 < len(sys.argv):
                companies = sys.argv[i + 1].split(",")
        adapter.run_full_scan(companies=companies or None)
    else:
        print("\nQuick test: searching 'AI automation business'...")
        articles = adapter.search_news("AI automation business", days_back=3)
        signals = adapter.extract_pain_signals(articles)

        print(f"\nArticles found: {len(articles)}")
        for a in articles[:5]:
            print(f"  📰 {a['title'][:80]}...")
            print(f"     Source: {a['source']} | {a['published']}")

        print(f"\nPain signals: {len(signals)}")
        for s in signals[:5]:
            print(f"  🎯 [{s['primary_signal']}] {s['title'][:80]}...")
            print(f"     Keywords: {', '.join(s['signal_keywords'][:5])}")

        print(f"\nRun with --scan for a full industry sweep")
