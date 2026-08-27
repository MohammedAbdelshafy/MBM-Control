# PERSISTENCE_PLAN.md — Acquisition-Disposition Engine Persistence

**Date:** 2026-08-27
**Decision:** Supabase is the single source of truth for all new persistence.

---

## EXISTING INFRASTRUCTURE

| System | Status | Use For |
|---|---|---|
| Supabase (remote Postgres) | ACTIVE, 28+ tables, 16 migrations | Canonical store for all entities |
| Prisma schema | NEVER MIGRATED (design artifact) | Ignore — do not use |
| leads_database.json | ACTIVE (481K lines, dialer) | Keep as dialer export format |
| SalesforceOS SQLite | ACTIVE (local mirror) | Deprecate — sync from Supabase |
| canonical_deals_memory.json | ACTIVE (JSON file) | Deprecate — use Supabase canonical_deals |

---

## ENTITY CLASSIFICATION

### Existing in Supabase (REUSE)

| Entity | Supabase Table | Status |
|---|---|---|
| Property | `properties` | EXISTS |
| Owner | `owners` | EXISTS |
| Lead | `leads` | EXISTS |
| LeadScore | `lead_scores` | EXISTS |
| BuyerProfile | `buyer_profiles` | EXISTS |
| BuyerMatch | `buyer_matches` | EXISTS |
| Deal | `canonical_deals` | EXISTS |
| Disposition | `dispositions` | EXISTS |
| Parcel | `parcels` | EXISTS |
| EvidenceRecord | `evidence_records` | EXISTS |
| ScoringConfig | `scoring_configs` | EXISTS |
| OutreachCampaign | `outreach_campaigns` | EXISTS |
| OutreachTemplate | `outreach_templates` | EXISTS |

### New Tables Required (CREATE)

| Entity | Table | Purpose |
|---|---|---|
| BuyerBuyBox | `buyer_buy_boxes` | Structured buy box criteria |
| DealSubmission | `deal_submissions` | Deal intake records |
| SocialInteraction | `social_interactions` | Social CTA routing |
| NextBestAction | `next_best_actions` | Priority-based actions |
| FollowUp | `follow_ups` | Scheduled follow-ups |
| ContentAsset | `content_assets` | Content pieces |
| Campaign | `campaigns` | Marketing campaigns |
| AttributionEvent | `attribution_events` | Content→revenue chain |
| RevenueEvent | `revenue_events` | Financial transactions |
| Transaction | `transactions` | Deal closings |
| DemandSignal | `demand_signals` | Cached demand by segment |
| SourceAnalytics | `source_analytics` | Per-source performance |
| AuditLogEntry | `audit_log_entries` | Structured event log |

### Do NOT Create (reuse existing)

| Concept | Reuse |
|---|---|
| Person | `leads` + `owners` + `buyer_profiles` (role-based) |
| Property | `properties` (existing) |
| Deal | `canonical_deals` (existing) |
| Pipeline Record | `deal_submissions` (new) + `canonical_deals` stages |
| Interaction | `calls` + `social_interactions` (new) |

---

## SERVICE LAYER ARCHITECTURE

```
UI/API (Express endpoints or React)
  ↓
Application Service (Python: ad_service.py)
  ↓
Domain Engine (buyer_buy_box_engine.py, deal_scoring_engine.py, etc.)
  ↓
Repository (Python: ad_repository.py — Supabase client)
  ↓
Supabase Postgres
```

Key rule: **Domain engines never touch the database directly.**
Repositories handle all persistence. Services wire engines to repositories.

---

## DEDUPLICATION RULES

| Entity | Identity Key | Conflict Resolution |
|---|---|---|
| Property | normalized_address + parcel_id | Merge if same parcel_id |
| Person | normalized_phone OR normalized_email | Link if same phone |
| Buyer | buyer_id (UUID) | No merge — unique |
| Deal | id (UUID) | No merge — unique |
| Content | content_id (UUID) | No merge — unique |

When uncertain: flag as `POSSIBLE_DUPLICATE`, surface for review.

---

## MIGRATION STRATEGY

1. Create new tables via Supabase migration (additive only)
2. Do NOT modify existing tables
3. Do NOT drop any columns
4. Do NOT overwrite existing data
5. Keep JSON file engines working (backward compatible)
6. New persistence layer is opt-in — engines still work standalone
