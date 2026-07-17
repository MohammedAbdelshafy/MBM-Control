# Data Source Registry
*Fallback hierarchy to ensure continuous mission execution. If Priority 1 is unavailable, instantly default to Priority 2.*

## Tier 1: Premium Verification (High Automation, High Cost)
| Source | Status | Cost | Availability | Data Quality | Automation Readiness | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PropStream** | `Locked` | Paid (Sub) | High | Excellent | High (API) | Primary engine for signal stacking and equity data. |
| **BatchLeads** | `Offline`| Paid | High | Excellent | High (API) | Preferred for Skip Tracing and SMS verification. |

## Tier 2: Open Gov & Public (Medium Automation, Free)
| Source | Status | Cost | Availability | Data Quality | Automation Readiness | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **County Assessor**| `Ready` | Free | Always | High (Slow) | Low/Medium | Fallback for tax defaults. Requires custom scraper per county. |
| **Socrata 311** | `Ready` | Free | Always | Medium | High (API) | Excellent for early distress signals (Code violations). |
| **Sheriff Sales** | `Ready` | Free | Scheduled | High | Low | Requires parsing PDF/HTML lists from local GovEase/County sites. |

## Tier 3: Aggregator Scraping (Hard Automation, Free/Low Cost)
| Source | Status | Cost | Availability | Data Quality | Automation Readiness | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Zillow** | `Ready` | Free | Always | Medium (Messy) | Low (Bot blocking) | Pre-foreclosure indicators available, but contact info requires skip-tracing. |
| **Facebook Groups**| `Ready` | Free | Always | Low | Very Low | Excellent for cash buyers; requires manual Playwright auth. |

## Execution Protocol
If `evidence_collector` fails to authenticate a Tier 1 source, it MUST NOT ABORT the mission. It must automatically fail over to a Tier 2 or Tier 3 source, log the degradation in the artifact, and continue execution.
