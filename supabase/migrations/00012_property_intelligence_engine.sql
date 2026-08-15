-- ============================================================
-- 00012 — Property Intelligence Engine (JARVIS Worker 1)
-- Canonical Supabase/Postgres model for the Core Property
-- Intelligence Engine: parcel/APN registry, evidence &
-- provenance tracking, negative disposition suppression, and
-- configurable lead-scoring weights.
--
-- Supabase is the canonical structured data layer. This
-- migration mirrors MBM/LeadEngine/prisma/schema.prisma so the
-- Prisma client and the live Postgres stay in lockstep.
-- Idempotent: safe to re-run against an existing database.
-- ============================================================

-- ── Enums ──────────────────────────────────────────────────────
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'verification_status') THEN
    CREATE TYPE verification_status AS ENUM (
      'unverified', 'pending', 'verified', 'rejected', 'expired'
    );
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'disposition_type') THEN
    CREATE TYPE disposition_type AS ENUM (
      'bad_number', 'wrong_person', 'non_owner', 'duplicate',
      'dnc', 'sold', 'not_interested', 'other'
    );
  END IF;
END $$;

-- ── parcels ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.parcels (
  id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  parcel_id            TEXT NOT NULL,
  apn_normalized       TEXT,
  county               TEXT NOT NULL,
  state                VARCHAR(2) NOT NULL,
  legal_description    TEXT,
  property_id          UUID UNIQUE REFERENCES public.properties(id) ON DELETE SET NULL,
  source               TEXT,
  source_url           TEXT,
  source_reference     TEXT,
  retrieved_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  verification_status  verification_status NOT NULL DEFAULT 'unverified',
  confidence           DOUBLE PRECISION NOT NULL DEFAULT 0,
  last_verified        TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (parcel_id, county, state)
);

CREATE INDEX IF NOT EXISTS idx_parcels_county_state ON public.parcels (county, state);
CREATE INDEX IF NOT EXISTS idx_parcels_verification_status ON public.parcels (verification_status);
CREATE INDEX IF NOT EXISTS idx_parcels_parcel_id ON public.parcels (parcel_id);

-- ── evidence_records ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.evidence_records (
  id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id              UUID REFERENCES public.leads(id) ON DELETE SET NULL,
  property_id          UUID REFERENCES public.properties(id) ON DELETE SET NULL,
  parcel_id            UUID REFERENCES public.parcels(id) ON DELETE SET NULL,
  owner_id             UUID REFERENCES public.owners(id) ON DELETE SET NULL,
  source               TEXT NOT NULL,
  source_type          source_type NOT NULL DEFAULT 'open_records',
  source_reference     TEXT,
  source_url           TEXT,
  raw_payload_hash     TEXT NOT NULL,
  verification_status  verification_status NOT NULL DEFAULT 'unverified',
  confidence           DOUBLE PRECISION NOT NULL DEFAULT 0,
  retrieved_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
  last_verified        TIMESTAMPTZ,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_evidence_records_lead_id ON public.evidence_records (lead_id);
CREATE INDEX IF NOT EXISTS idx_evidence_records_property_id ON public.evidence_records (property_id);
CREATE INDEX IF NOT EXISTS idx_evidence_records_parcel_id ON public.evidence_records (parcel_id);
CREATE INDEX IF NOT EXISTS idx_evidence_records_owner_id ON public.evidence_records (owner_id);
CREATE INDEX IF NOT EXISTS idx_evidence_records_source ON public.evidence_records (source);
CREATE INDEX IF NOT EXISTS idx_evidence_records_source_type ON public.evidence_records (source_type);
CREATE INDEX IF NOT EXISTS idx_evidence_records_source_reference ON public.evidence_records (source_reference);
CREATE INDEX IF NOT EXISTS idx_evidence_records_verification_status ON public.evidence_records (verification_status);
CREATE INDEX IF NOT EXISTS idx_evidence_records_last_verified ON public.evidence_records (last_verified);

-- ── provenance_events ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.provenance_events (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  evidence_id  UUID NOT NULL REFERENCES public.evidence_records(id) ON DELETE CASCADE,
  from_stage   TEXT NOT NULL,
  to_stage     TEXT NOT NULL,
  worker_id    TEXT,
  status       TEXT NOT NULL DEFAULT 'SUCCESS',
  metadata     JSONB,
  occurred_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_provenance_events_evidence_id ON public.provenance_events (evidence_id);
CREATE INDEX IF NOT EXISTS idx_provenance_events_occurred_at ON public.provenance_events (occurred_at);

-- ── dispositions (negative disposition suppression) ────────────
CREATE TABLE IF NOT EXISTS public.dispositions (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  lead_id     UUID REFERENCES public.leads(id) ON DELETE SET NULL,
  property_id UUID REFERENCES public.properties(id) ON DELETE SET NULL,
  phone       TEXT NOT NULL,
  type        disposition_type NOT NULL,
  reason      TEXT,
  permanent   BOOLEAN NOT NULL DEFAULT true,
  source      TEXT NOT NULL DEFAULT 'dialer',
  recorded_by TEXT,
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at  TIMESTAMPTZ,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_dispositions_phone ON public.dispositions (phone);
CREATE INDEX IF NOT EXISTS idx_dispositions_type ON public.dispositions (type);
CREATE INDEX IF NOT EXISTS idx_dispositions_permanent ON public.dispositions (permanent);
CREATE INDEX IF NOT EXISTS idx_dispositions_lead_id ON public.dispositions (lead_id);
CREATE INDEX IF NOT EXISTS idx_dispositions_property_id ON public.dispositions (property_id);
CREATE INDEX IF NOT EXISTS idx_dispositions_recorded_at ON public.dispositions (recorded_at);

-- ── scoring_configs (configurable lead-scoring weights) ────────
CREATE TABLE IF NOT EXISTS public.scoring_configs (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name        TEXT NOT NULL UNIQUE,
  scope       TEXT NOT NULL DEFAULT 'global',
  scope_value TEXT,
  weights     JSONB NOT NULL,
  enabled     BOOLEAN NOT NULL DEFAULT true,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scoring_configs_scope ON public.scoring_configs (scope, scope_value);
CREATE INDEX IF NOT EXISTS idx_scoring_configs_enabled ON public.scoring_configs (enabled);

-- ── rejection_ledger (previous-rejection guarantee) ──────────────
CREATE TABLE IF NOT EXISTS public.rejection_ledger (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  rejection_key TEXT NOT NULL,
  dimension     TEXT NOT NULL,
  phone         TEXT NOT NULL,
  parcel_id     TEXT,
  address_key   TEXT,
  reasons       JSONB NOT NULL,
  permanent     BOOLEAN NOT NULL DEFAULT true,
  source        TEXT NOT NULL DEFAULT 'predial_gate',
  recorded_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (rejection_key, dimension)
);

CREATE INDEX IF NOT EXISTS idx_rejection_ledger_phone ON public.rejection_ledger (phone);
CREATE INDEX IF NOT EXISTS idx_rejection_ledger_parcel_id ON public.rejection_ledger (parcel_id);
CREATE INDEX IF NOT EXISTS idx_rejection_ledger_permanent ON public.rejection_ledger (permanent);
CREATE INDEX IF NOT EXISTS idx_rejection_ledger_recorded_at ON public.rejection_ledger (recorded_at);

-- ── Extend existing tables ──────────────────────────────────────
ALTER TABLE public.properties
  ADD COLUMN IF NOT EXISTS normalized_address TEXT,
  ADD COLUMN IF NOT EXISTS dedupe_key TEXT UNIQUE;

ALTER TABLE public.owners
  ADD COLUMN IF NOT EXISTS verification_status verification_status NOT NULL DEFAULT 'unverified',
  ADD COLUMN IF NOT EXISTS source TEXT,
  ADD COLUMN IF NOT EXISTS source_url TEXT,
  ADD COLUMN IF NOT EXISTS source_reference TEXT,
  ADD COLUMN IF NOT EXISTS last_verified TIMESTAMPTZ;

ALTER TABLE public.leads
  ADD COLUMN IF NOT EXISTS callability_score INTEGER;

ALTER TABLE public.lead_scores
  ADD COLUMN IF NOT EXISTS callability_score INTEGER,
  ADD COLUMN IF NOT EXISTS callability_breakdown JSONB;

ALTER TABLE public.addresses
  ADD COLUMN IF NOT EXISTS dedupe_key TEXT;

CREATE INDEX IF NOT EXISTS idx_properties_dedupe_key ON public.properties (dedupe_key);
CREATE INDEX IF NOT EXISTS idx_owners_verification_status ON public.owners (verification_status);
CREATE INDEX IF NOT EXISTS idx_leads_callability_score ON public.leads (callability_score);
CREATE INDEX IF NOT EXISTS idx_addresses_dedupe_key ON public.addresses (dedupe_key);

-- ── RLS: service_role full access (matches existing migrations) ─
ALTER TABLE public.parcels ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.evidence_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.provenance_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.dispositions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.scoring_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rejection_ledger ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "service_role_all_parcels" ON public.parcels;
CREATE POLICY "service_role_all_parcels"
  ON public.parcels USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "service_role_all_evidence_records" ON public.evidence_records;
CREATE POLICY "service_role_all_evidence_records"
  ON public.evidence_records USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "service_role_all_provenance_events" ON public.provenance_events;
CREATE POLICY "service_role_all_provenance_events"
  ON public.provenance_events USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "service_role_all_dispositions" ON public.dispositions;
CREATE POLICY "service_role_all_dispositions"
  ON public.dispositions USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "service_role_all_scoring_configs" ON public.scoring_configs;
CREATE POLICY "service_role_all_scoring_configs"
  ON public.scoring_configs USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "service_role_all_rejection_ledger" ON public.rejection_ledger;
CREATE POLICY "service_role_all_rejection_ledger"
  ON public.rejection_ledger USING (true) WITH CHECK (true);