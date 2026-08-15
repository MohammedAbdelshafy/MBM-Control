-- ============================================================
-- 00014 — Canonical Unified Deal Memory (JARVIS Master Ecosystem)
-- Unifies Property Deals (Auction.com / Foreclosure / Distressed RE)
-- and Business AI Deals (TranchAI / B2B AI Automation / High-Ticket)
-- under a single, authoritative provenance-backed schema.
--
-- Idempotent: safe to re-run against existing database.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Enums ──────────────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'canonical_deal_type') THEN
    CREATE TYPE canonical_deal_type AS ENUM (
      'property', 'business_ai'
    );
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'canonical_deal_stage') THEN
    CREATE TYPE canonical_deal_stage AS ENUM (
      'NEW', 'QUALIFIED', 'CONTACTED', 'CONNECTED', 'DISCOVERY',
      'INTERESTED', 'DEMO_BOOKED', 'DEMO_COMPLETE', 'PROPOSAL',
      'NEGOTIATION', 'CLOSED_WON', 'CLOSED_LOST', 'FOLLOW_UP',
      'DNC', 'DISQUALIFIED', 'STALE'
    );
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'monetization_route') THEN
    CREATE TYPE monetization_route AS ENUM (
      'BUY', 'MATCH_TO_BUYER', 'WHOLESALE_ASSIGNMENT',
      'INVESTOR_INTRODUCTION', 'AI_RETAINER', 'AI_SETUP_FEE',
      'SOFTWARE_LICENSE', 'OTHER_VERIFIED_PATH'
    );
  END IF;
END $$;

-- ── canonical_deals ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.canonical_deals (
  id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  deal_type             canonical_deal_type NOT NULL,
  lead_id               TEXT NOT NULL,
  source                TEXT NOT NULL,
  source_url            TEXT,
  source_date           TEXT,
  retrieved_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  -- Entity / Contact Information
  owner_name            TEXT NOT NULL DEFAULT '',
  company_name          TEXT NOT NULL DEFAULT '',
  contact_phone         TEXT NOT NULL DEFAULT '',
  contact_email         TEXT NOT NULL DEFAULT '',
  contact_source        TEXT NOT NULL DEFAULT '',
  
  -- Vertical & Location
  vertical              TEXT NOT NULL,
  city                  TEXT NOT NULL DEFAULT '',
  state                 TEXT NOT NULL DEFAULT '',
  county                TEXT NOT NULL DEFAULT '',
  parcel_id             TEXT,
  property_address      TEXT,
  
  -- Signals & Scoring (0-100)
  signals               JSONB NOT NULL DEFAULT '[]'::jsonb,
  opportunity_score     INTEGER NOT NULL DEFAULT 0,
  callability_score     INTEGER NOT NULL DEFAULT 0,
  deal_score            INTEGER NOT NULL DEFAULT 0,
  motivation_score      INTEGER NOT NULL DEFAULT 0,
  buyer_fit_score       INTEGER NOT NULL DEFAULT 0,
  economic_confidence   INTEGER NOT NULL DEFAULT 0,
  
  -- Deal Economics & Offer
  estimated_arv         DOUBLE PRECISION,
  starting_bid          DOUBLE PRECISION,
  calculated_mao        DOUBLE PRECISION,
  estimated_repair_cost DOUBLE PRECISION,
  potential_fee         DOUBLE PRECISION,
  primary_offer         TEXT NOT NULL DEFAULT '',
  neteller_link         TEXT,
  monetization_route    monetization_route NOT NULL DEFAULT 'OTHER_VERIFIED_PATH',
  tier                  TEXT NOT NULL DEFAULT 'Tier B',
  
  -- Strategic Thesis & Risk Analysis
  why_this_deal         TEXT NOT NULL DEFAULT '',
  why_now               TEXT NOT NULL DEFAULT '',
  economic_thesis       TEXT NOT NULL DEFAULT '',
  risks                 TEXT NOT NULL DEFAULT '',
  unknown_variables     TEXT NOT NULL DEFAULT '',
  
  -- Sales Execution & Scripts
  sales_script          TEXT NOT NULL DEFAULT '',
  objection_handling    JSONB NOT NULL DEFAULT '{}'::jsonb,
  
  -- Stage Management
  stage                 canonical_deal_stage NOT NULL DEFAULT 'NEW',
  reason                TEXT NOT NULL DEFAULT '',
  next_action           TEXT NOT NULL DEFAULT 'VERIFY_CONTACT',
  next_action_at        TIMESTAMPTZ,
  assigned_owner        TEXT NOT NULL DEFAULT 'jarvis-closer',
  outcome               TEXT NOT NULL DEFAULT 'PENDING',
  
  -- Evidence Provenance & Confidence
  evidence_provenance   JSONB NOT NULL DEFAULT '[]'::jsonb,
  confidence            DOUBLE PRECISION NOT NULL DEFAULT 0.0,
  is_prime_callable     BOOLEAN NOT NULL DEFAULT false,
  suppression_state     TEXT NOT NULL DEFAULT 'ACTIVE',
  
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (lead_id, deal_type)
);

-- Indexes for lightning queries
CREATE INDEX IF NOT EXISTS idx_canonical_deals_type ON public.canonical_deals (deal_type);
CREATE INDEX IF NOT EXISTS idx_canonical_deals_stage ON public.canonical_deals (stage);
CREATE INDEX IF NOT EXISTS idx_canonical_deals_vertical ON public.canonical_deals (vertical);
CREATE INDEX IF NOT EXISTS idx_canonical_deals_deal_score ON public.canonical_deals (deal_score DESC);
CREATE INDEX IF NOT EXISTS idx_canonical_deals_callability ON public.canonical_deals (callability_score DESC);
CREATE INDEX IF NOT EXISTS idx_canonical_deals_prime ON public.canonical_deals (is_prime_callable);
CREATE INDEX IF NOT EXISTS idx_canonical_deals_phone ON public.canonical_deals (contact_phone);
CREATE INDEX IF NOT EXISTS idx_canonical_deals_created_at ON public.canonical_deals (created_at);

-- ── deal_stage_history ─────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.deal_stage_history (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  deal_id      UUID NOT NULL REFERENCES public.canonical_deals(id) ON DELETE CASCADE,
  from_stage   canonical_deal_stage NOT NULL,
  to_stage     canonical_deal_stage NOT NULL,
  reason       TEXT,
  next_action  TEXT,
  changed_by   TEXT NOT NULL DEFAULT 'system',
  metadata     JSONB,
  occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_deal_stage_history_deal_id ON public.deal_stage_history (deal_id);
CREATE INDEX IF NOT EXISTS idx_deal_stage_history_occurred ON public.deal_stage_history (occurred_at);

-- ── RLS Policies ───────────────────────────────────────────────
ALTER TABLE public.canonical_deals ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.deal_stage_history ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_all_canonical_deals" ON public.canonical_deals;
CREATE POLICY "service_role_all_canonical_deals"
  ON public.canonical_deals USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "service_role_all_deal_stage_history" ON public.deal_stage_history;
CREATE POLICY "service_role_all_deal_stage_history"
  ON public.deal_stage_history USING (true) WITH CHECK (true);
