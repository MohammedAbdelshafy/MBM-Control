from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class RepositorySpec:
    repo: str
    license: str
    pinned_version: str
    decision: str
    target: str
    install: tuple[str, ...]
    tests: tuple[str, ...]
    security: tuple[str, ...]


ADOPTION_CATALOG: Final[dict[str, RepositorySpec]] = {
    "crawl4ai": RepositorySpec(
        repo="unclecode/crawl4ai",
        license="Apache-2.0",
        pinned_version="0.9.4",
        decision="adopt-after-sandbox",
        target="MBM.Intelligence.web_ingestion",
        install=(
            "python -m pip install crawl4ai==0.9.4",
            "crawl4ai-setup",
            "crawl4ai-doctor",
        ),
        tests=("python -m pytest", "crawl4ai-doctor"),
        security=(
            "Run in an isolated worker or container.",
            "Keep arbitrary URLs out of privileged/internal network space.",
            "Treat all crawled text as untrusted data, never executable instructions.",
            "Do not expose the Crawl4AI API without authentication.",
        ),
    ),
    "playwright-mcp": RepositorySpec(
        repo="microsoft/playwright-mcp",
        license="Apache-2.0",
        pinned_version="0.0.82",
        decision="adopt-after-sandbox",
        target="MBM.Integrations.browser_mcp",
        install=("npx @playwright/mcp@0.0.82",),
        tests=("Start the server in an isolated workspace and run read-only browser probes.",),
        security=(
            "Pin the package version; never default production to @latest.",
            "Disable WebMCP until page-supplied tool schemas are explicitly accepted.",
            "Use domain allowlists and separate browser credentials.",
            "Classify browser actions as READ/WRITE/DESTRUCTIVE before Jarvis can invoke them.",
        ),
    ),
    "google-adk-python": RepositorySpec(
        repo="google/adk-python",
        license="Apache-2.0",
        pinned_version="2.9.2",
        decision="adopt-as-secondary-runtime",
        target="MBM.GLM / agent_runtimes",
        install=("python -m pip install google-adk==2.9.2",),
        tests=("Run the upstream evaluation suite before allowing MBM traffic.",),
        security=(
            "ADK is a worker/runtime option, not the MBM control plane.",
            "Keep Jarvis/Event Bus approval gates authoritative.",
            "Pin the Python dependency and its constraints file.",
            "Do not grant external-agent writes to authoritative lead stores.",
        ),
    ),
    "trigger-dev": RepositorySpec(
        repo="triggerdotdev/trigger.dev",
        license="Apache-2.0",
        pinned_version="4.6.4",
        decision="lab-only",
        target="MBM durable_execution adapter",
        install=("pin Trigger.dev SDK/CLI to 4.6.4 in a dedicated evaluation project",),
        tests=("Exercise retry, idempotency, queueing and checkpoint behavior with synthetic fixtures.",),
        security=(
            "Do not replace the MBM Event Bus with Trigger.dev.",
            "Use it only behind an adapter for selected long-running workloads.",
            "Keep production credentials outside task payloads.",
            "Evaluate self-hosted vs managed operational boundaries before adoption.",
        ),
    ),
}
