-- ============================================================
-- 00013 — Property Intelligence Base Schema (JARVIS Worker 2, data side)
-- Canonical base tables + enums for the property-intelligence engine,
-- mirrored from MBM/LeadEngine/prisma/schema.prisma. Migration 00012
-- (Worker 1) only ALTERs these base tables — this migration guarantees
-- they exist so 00012 can be applied against a fresh database.
--
-- Also creates the property tables the pipeline emits into:
--   auctions, business_prospects
-- (Auction / BusinessProspect in the Prisma schema.)
--
-- Idempotent: safe to re-run. Run BEFORE 00012.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Enums (mirror prisma @@map names) ─────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_type') THEN
    CREATE TYPE source_type AS ENUM (
      'county_assessor','property_appraiser','gis','tax_assessor',
      'open_records','municipal_code_enforcement','court_records',
      'business_registry','auction_data','user_import','api_connector'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'verification_status') THEN
    CREATE TYPE verification_status AS ENUM (
      'unverified','pending','verified','rejected','expired'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'disposition_type') THEN
    CREATE TYPE disposition_type AS ENUM (
      'bad_number','wrong_person','non_owner','duplicate',
      'dnc','sold','not_interested','other'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'property_type') THEN
    CREATE TYPE property_type AS ENUM (
      'single_family','multi_family','commercial','industrial',
      'land','condo','townhouse','other'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ownership_type') THEN
    CREATE TYPE ownership_type AS ENUM (
      'individual','llc','corporation','trust','partnership',
      'government','other'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'niche_type') THEN
    CREATE TYPE niche_type AS ENUM (
      'code_violation','vacant','tax_delinquent','absentee','high_equity',
      'free_and_clear','probate','pre_foreclosure','eviction',
      'utility_shutoff','fire_damage','condemned','zombie',
      'commercial_distress','industrial_opportunity'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'lead_status') THEN
    CREATE TYPE lead_status AS ENUM (
      'new','active','qualified','converted','rejected','stale'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'lead_grade') THEN
    CREATE TYPE lead_grade AS ENUM ('a_plus','a','b','c','reject');
  END IF;
END $$;

-- ── properties ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.properties (
  id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  parcel_id          TEXT NOT NULL UNIQUE,
  address_line1      TEXT,
  address_line2      TEXT,
  city               TEXT,
  state              VARCHAR(2),
  zip                VARCHAR(10),
  county             TEXT,
  lat                DOUBLE PRECISION,
  lng                DOUBLE PRECISION,
  property_type      property_type,
  year_built         INTEGER,
  lot_size_sqft      DOUBLE PRECISION,
  building_sqft      DOUBLE PRECISION,
  bedrooms           INTEGER,
  bathrooms          DOUBLE PRECISION,
  estimated_value    DOUBLE PRECISION,
  last_sale_date     TIMESTAMPTZ,
  last_sale_price    DOUBLE PRECISION,
  assessed_value     DOUBLE PRECISION,
  market_value       DOUBLE PRECISION,
  legal_description  TEXT,
  normalized_address TEXT,
  dedupe_key         TEXT UNIQUE,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_properties_county ON public.properties (county);
CREATE INDEX IF NOT EXISTS idx_properties_state_county ON public.properties (state, county);
CREATE INDEX IF NOT EXISTS idx_properties_property_type ON public.properties (property_type);
CREATE INDEX IF NOT EXISTS idx_properties_zip ON public.properties (zip);
CREATE INDEX IF NOT EXISTS idx_properties_created_at ON public.properties (created_at);

-- ── owners ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.owners (
  id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id         UUID NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  name                TEXT NOT NULL,
  owner_type          ownership_type NOT NULL DEFAULT 'other',
  mailing_address     TEXT,
  phone               TEXT,
  email               TEXT,
  is_absentee         BOOLEAN NOT NULL DEFAULT false,
  confidence_score    DOUBLE PRECISION NOT NULL DEFAULT 0,
  verification_status verification_status NOT NULL DEFAULT 'unverified',
  source              TEXT,
  source_url          TEXT,
  source_reference    TEXT,
  verified_at         TIMESTAMPTZ,
  last_verified       TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_owners_property_id ON public.owners (property_id);
CREATE INDEX IF NOT EXISTS idx_owners_owner_type ON public.owners (owner_type);
CREATE INDEX IF NOT EXISTS idx_owners_is_absentee ON public.owners (is_absentee);
CREATE INDEX IF NOT EXISTS idx_owners_confidence_score ON public.owners (confidence_score);
CREATE INDEX IF NOT EXISTS idx_owners_verification_status ON public.owners (verification_status);

-- ── addresses ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.addresses (
  id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id         UUID NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  source_address      TEXT NOT NULL,
  normalized_address  TEXT,
  city                TEXT,
  state               VARCHAR(2),
  zip                 VARCHAR(10),
  county              TEXT,
  lat                 DOUBLE PRECISION,
  lng                 DOUBLE PRECISION,
  geocoded_at         TIMESTAMPTZ,
  normalized_at       TIMESTAMPTZ,
  dedupe_key          TEXT
);
CREATE INDEX IF NOT EXISTS idx_addresses_property_id ON public.addresses (property_id);
CREATE INDEX IF NOT EXISTS idx_addresses_state_county ON public.addresses (state, county);
CREATE INDEX IF NOT EXISTS idx_addresses_dedupe_key ON public.addresses (dedupe_key);

-- ── leads ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.leads (
  id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id          UUID NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  niche                niche_type,
  status               lead_status NOT NULL DEFAULT 'new',
  grade                lead_grade,
  score                INTEGER NOT NULL DEFAULT 0,
  signals              JSONB,
  confidence           DOUBLE PRECISION NOT NULL DEFAULT 0,
  summary              TEXT,
  generated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  claimed_at           TIMESTAMPTZ,
  client_id            TEXT,
  assigned_to          TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  phone                TEXT,
  email                TEXT,
  email_verified       BOOLEAN NOT NULL DEFAULT false,
  contact_name         TEXT,
  skip_trace_source    TEXT,
  skip_trace_confidence DOUBLE PRECISION,
  callability_score    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_leads_property_id ON public.leads (property_id);
CREATE INDEX IF NOT EXISTS idx_leads_status ON public.leads (status);
CREATE INDEX IF NOT EXISTS idx_leads_score ON public.leads (score);
CREATE INDEX IF NOT EXISTS idx_leads_niche ON public.leads (niche);
CREATE INDEX IF NOT EXISTS idx_leads_generated_at ON public.leads (generated_at);
CREATE INDEX IF NOT EXISTS idx_leads_callability_score ON public.leads (callability_score);

-- ── lead_scores ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.lead_scores (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id               UUID NOT NULL UNIQUE REFERENCES public.leads(id) ON DELETE CASCADE,
  overall_score         INTEGER NOT NULL,
  callability_score     INTEGER,
  callability_breakdown JSONB,
  ownership_confidence  DOUBLE PRECISION NOT NULL DEFAULT 0,
  record_freshness      DOUBLE PRECISION NOT NULL DEFAULT 0,
  absentee_signal       DOUBLE PRECISION NOT NULL DEFAULT 0,
  vacancy_indicators    DOUBLE PRECISION NOT NULL DEFAULT 0,
  violation_severity    DOUBLE PRECISION NOT NULL DEFAULT 0,
  tax_delinquency       DOUBLE PRECISION NOT NULL DEFAULT 0,
  equity_proxy          DOUBLE PRECISION NOT NULL DEFAULT 0,
  commercial_opportunity DOUBLE PRECISION NOT NULL DEFAULT 0,
  data_completeness     DOUBLE PRECISION NOT NULL DEFAULT 0,
  duplicate_penalty     DOUBLE PRECISION NOT NULL DEFAULT 0,
  calculated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── auctions ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.auctions (
  id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  property_id     UUID NOT NULL REFERENCES public.properties(id) ON DELETE CASCADE,
  auction_date    TIMESTAMPTZ NOT NULL,
  opening_bid     DOUBLE PRECISION,
  estimated_value DOUBLE PRECISION,
  venue           TEXT,
  case_number     TEXT,
  source          TEXT NOT NULL,
  source_url      TEXT,
  status          TEXT NOT NULL DEFAULT 'scheduled',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_auctions_property_id ON public.auctions (property_id);
CREATE INDEX IF NOT EXISTS idx_auctions_auction_date ON public.auctions (auction_date);
CREATE INDEX IF NOT EXISTS idx_auctions_status ON public.auctions (status);

-- ── business_prospects ────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.business_prospects (
  id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  company_name         TEXT NOT NULL,
  industry             TEXT,
  decision_maker_name  TEXT,
  decision_maker_title TEXT,
  verified_email       TEXT,
  verified_phone       TEXT,
  service_fit          TEXT,
  problem_description  TEXT,
  solution_description TEXT,
  sales_priority_score INTEGER NOT NULL DEFAULT 0,
  neteller_sku         TEXT,
  status               TEXT NOT NULL DEFAULT 'new',
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_business_prospects_company ON public.business_prospects (company_name);
CREATE INDEX IF NOT EXISTS idx_business_prospects_priority ON public.business_prospects (sales_priority_score);