# Scrapling Standard

For scraper-capable MBM services, use Scrapling as the common acquisition/extraction substrate behind a local adapter.

Contract: `source -> Scrapling -> evidence-normalizer -> system QA -> domain ranking -> downstream action`.

Scraping is collection only. Domain systems retain authority over scoring, CRM writes, outreach, and decisions.

Every implementation must preserve source URL/provenance, expose blocked/empty/malformed outcomes explicitly, support dependency health checks and dry-run mode, and refuse fabricated business or contact data.

Repositories may pin/upgrade Scrapling independently, but adapters should preserve the stable normalized evidence contract.
