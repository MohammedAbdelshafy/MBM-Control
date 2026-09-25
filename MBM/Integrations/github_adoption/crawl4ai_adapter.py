from __future__ import annotations

from dataclasses import dataclass

from .security import assert_public_url, wrap_untrusted_content


@dataclass(frozen=True)
class CrawlOutput:
    source_url: str
    markdown: str
    trusted_instructions: bool = False


async def crawl_markdown(url: str) -> CrawlOutput:
    """Run Crawl4AI as an optional, sandboxed web-ingestion dependency.

    The dependency is intentionally imported lazily so MBM-Control remains
    installable without Crawl4AI. The returned content is always marked as
    untrusted web data.
    """
    safe_url = assert_public_url(url)

    try:
        from crawl4ai import AsyncWebCrawler
    except ImportError as exc:
        raise RuntimeError(
            "Crawl4AI is not installed. Install the pinned evaluation version "
            "with: pip install crawl4ai==0.9.4"
        ) from exc

    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=safe_url)

    markdown = getattr(result, "markdown", "") or ""
    return CrawlOutput(
        source_url=safe_url,
        markdown=wrap_untrusted_content(safe_url, markdown),
        trusted_instructions=False,
    )
