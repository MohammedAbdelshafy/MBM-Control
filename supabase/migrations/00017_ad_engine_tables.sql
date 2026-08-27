-- Migration: Acquisition-Disposition Engine Tables
-- Date: 2026-08-27
-- Strategy: Additive only. No existing tables modified.

-- ============================================================
-- BUYER BUY BOX
-- Structured buyer profile with buy box criteria
-- ============================================================
CREATE TABLE IF NOT EXISTS buyer_buy_boxes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id TEXT UNIQUE NOT NULL,
    buyer_name TEXT NOT NULL,
    company TEXT DEFAULT '',

    -- Location
    markets JSONB DEFAULT '[]',
    zip_codes JSONB DEFAULT '[]',
    radius_miles REAL DEFAULT 25.0,

    -- Property Requirements
    property_types JSONB DEFAULT '["SFR"]',
    min_beds INT DEFAULT 0,
    max_beds INT DEFAULT 0,
    min_baths REAL DEFAULT 0,
    min_sqft INT DEFAULT 0,
    max_sqft INT DEFAULT 0,
    min_lot_acres REAL DEFAULT 0,
    max_lot_acres REAL DEFAULT 0,

    -- Financial
    price_min REAL DEFAULT 0,
    price_max REAL DEFAULT 0,
    arv_min REAL DEFAULT 0,
    arv_max REAL DEFAULT 0,
    rehab_min REAL DEFAULT 0,
    rehab_max REAL DEFAULT 0,
    min_spread REAL DEFAULT 0,
    min_cash_on_cash REAL DEFAULT 0,
    min_yield REAL DEFAULT 0,

    -- Strategy
    strategy JSONB DEFAULT '["FIX_AND_FLIP"]',
    cash_or_finance JSONB DEFAULT '["CASH"]',
    closing_speed_days INT DEFAULT 14,
    occupancy_preference TEXT DEFAULT 'ANY',

    -- Deal Types
    preferred_deal_types JSONB DEFAULT '["WHOLESALE"]',
    avoid_list JSONB DEFAULT '[]',

    -- Activity & Reliability
    last_verified TIMESTAMPTZ DEFAULT NOW(),
    source TEXT DEFAULT 'manual',
    reliability_score REAL DEFAULT 50,
    activity_score REAL DEFAULT 50,
    verification_status TEXT DEFAULT 'UNVERIFIED',
    total_closes INT DEFAULT 0,
    avg_days_to_close REAL DEFAULT 0,
    last_offer_date TIMESTAMPTZ,
    last_close_date TIMESTAMPTZ,

    -- Contact
    phone TEXT DEFAULT '',
    email TEXT DEFAULT '',
    whatsapp TEXT DEFAULT '',
    instagram TEXT DEFAULT '',
    facebook TEXT DEFAULT '',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_buyer_buy_boxes_markets ON buyer_buy_boxes USING GIN (markets);
CREATE INDEX IF NOT EXISTS idx_buyer_buy_boxes_property_types ON buyer_buy_boxes USING GIN (property_types);
CREATE INDEX IF NOT EXISTS idx_buyer_buy_boxes_verification ON buyer_buy_boxes (verification_status);
CREATE INDEX IF NOT EXISTS idx_buyer_buy_boxes_activity ON buyer_buy_boxes (activity_score DESC);

-- ============================================================
-- DEAL SUBMISSIONS
-- Low-friction deal intake from deal sources
-- ============================================================
CREATE TABLE IF NOT EXISTS deal_submissions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Contact (Deal Source)
    source_name TEXT DEFAULT '',
    source_phone TEXT DEFAULT '',
    source_email TEXT DEFAULT '',
    source_platform TEXT DEFAULT '',
    source_username TEXT DEFAULT '',
    jv_split TEXT DEFAULT '50/50',

    -- Property
    address TEXT DEFAULT '',
    city TEXT DEFAULT '',
    state TEXT DEFAULT '',
    zip_code TEXT DEFAULT '',
    county TEXT DEFAULT '',
    property_type TEXT DEFAULT 'SFR',

    -- Deal
    contract_status TEXT DEFAULT 'NO_CONTRACT',
    asking_price REAL DEFAULT 0,
    contract_price REAL DEFAULT 0,
    arv REAL DEFAULT 0,
    arv_source TEXT DEFAULT '',
    estimated_repairs REAL DEFAULT 0,
    repair_source TEXT DEFAULT '',
    occupancy TEXT DEFAULT 'UNKNOWN',
    beds INT DEFAULT 0,
    baths REAL DEFAULT 0,
    sqft INT DEFAULT 0,
    lot_acres REAL DEFAULT 0,
    year_built INT DEFAULT 0,

    -- Timeline
    closing_date DATE,
    motivated_reason TEXT DEFAULT '',

    -- Media
    photos JSONB DEFAULT '[]',
    listing_url TEXT DEFAULT '',

    -- Assignment/JV
    assignment_fee REAL DEFAULT 0,
    seller_constraints TEXT DEFAULT '',

    -- Source Attribution
    campaign_id TEXT DEFAULT '',
    content_id TEXT DEFAULT '',
    post_id TEXT DEFAULT '',

    -- Scoring & Matching
    deal_score_id UUID,
    buyer_matches JSONB DEFAULT '[]',
    demand_signal TEXT DEFAULT 'UNKNOWN',

    -- Status
    status TEXT DEFAULT 'INTAKE',
    validation_errors JSONB DEFAULT '[]',
    validation_warnings JSONB DEFAULT '[]',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_deal_submissions_status ON deal_submissions (status);
CREATE INDEX IF NOT EXISTS idx_deal_submissions_city ON deal_submissions (city);
CREATE INDEX IF NOT EXISTS idx_deal_submissions_platform ON deal_submissions (source_platform);
CREATE INDEX IF NOT EXISTS idx_deal_submissions_created ON deal_submissions (created_at DESC);

-- ============================================================
-- SOCIAL INTERACTIONS
-- Social CTA routing records
-- ============================================================
CREATE TABLE IF NOT EXISTS social_interactions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    platform TEXT NOT NULL,
    username TEXT DEFAULT '',
    display_name TEXT DEFAULT '',
    message TEXT DEFAULT '',
    post_id TEXT DEFAULT '',
    campaign_id TEXT DEFAULT '',
    content_id TEXT DEFAULT '',
    content_type TEXT DEFAULT '',

    -- Extracted by router
    cta_keyword TEXT DEFAULT '',
    intent TEXT DEFAULT 'unknown',
    pipeline TEXT DEFAULT 'seller',
    priority TEXT DEFAULT 'NORMAL',

    -- Routing metadata
    routed_at TIMESTAMPTZ,
    lead_id UUID,
    first_response_at TIMESTAMPTZ,
    qualified_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_social_interactions_platform ON social_interactions (platform);
CREATE INDEX IF NOT EXISTS idx_social_interactions_intent ON social_interactions (intent);
CREATE INDEX IF NOT EXISTS idx_social_interactions_priority ON social_interactions (priority);
CREATE INDEX IF NOT EXISTS idx_social_interactions_campaign ON social_interactions (campaign_id);
CREATE INDEX IF NOT EXISTS idx_social_interactions_created ON social_interactions (created_at DESC);

-- ============================================================
-- NEXT BEST ACTIONS
-- Priority-based recommended actions
-- ============================================================
CREATE TABLE IF NOT EXISTS next_best_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    action TEXT NOT NULL,
    priority INT NOT NULL DEFAULT 3,
    reason TEXT DEFAULT '',
    deadline TIMESTAMPTZ,
    owner TEXT DEFAULT 'system',
    status TEXT DEFAULT 'PENDING',
    scheduled_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nba_entity ON next_best_actions (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_nba_priority ON next_best_actions (priority ASC, status);
CREATE INDEX IF NOT EXISTS idx_nba_deadline ON next_best_actions (deadline ASC) WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_nba_status ON next_best_actions (status);

-- ============================================================
-- FOLLOW-UPS
-- Scheduled follow-up tasks
-- ============================================================
CREATE TABLE IF NOT EXISTS follow_ups (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    reason TEXT DEFAULT '',
    priority INT DEFAULT 3,
    channel TEXT DEFAULT 'MANUAL',
    status TEXT DEFAULT 'PENDING',
    attempt_count INT DEFAULT 0,
    last_attempt TIMESTAMPTZ,
    next_attempt TIMESTAMPTZ,
    owner TEXT DEFAULT 'system',
    notes TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_follow_ups_entity ON follow_ups (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_follow_ups_status ON follow_ups (status, next_attempt ASC);
CREATE INDEX IF NOT EXISTS idx_follow_ups_owner ON follow_ups (owner, status);

-- ============================================================
-- DEMAND SIGNALS
-- Cached demand by market segment
-- ============================================================
CREATE TABLE IF NOT EXISTS demand_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    market TEXT NOT NULL,
    property_type TEXT NOT NULL,
    price_band TEXT NOT NULL,
    signal TEXT DEFAULT 'UNKNOWN',
    active_buyers INT DEFAULT 0,
    verified_buyers INT DEFAULT 0,
    recent_offers INT DEFAULT 0,
    recent_closes INT DEFAULT 0,
    avg_days_to_close REAL DEFAULT 0,
    avg_spread REAL DEFAULT 0,
    top_buyers JSONB DEFAULT '[]',
    trend TEXT DEFAULT 'STABLE',

    calculated_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_demand_signals_market ON demand_signals (market, property_type);
CREATE INDEX IF NOT EXISTS idx_demand_signals_signal ON demand_signals (signal);
CREATE INDEX IF NOT EXISTS idx_demand_signals_calculated ON demand_signals (calculated_at DESC);

-- ============================================================
-- REVENUE EVENTS
-- Immutable revenue attribution records
-- ============================================================
CREATE TABLE IF NOT EXISTS revenue_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transaction_id TEXT,
    deal_id TEXT,
    source_id TEXT,
    campaign_id TEXT,
    content_id TEXT,
    lead_id TEXT,
    buyer_id TEXT,

    revenue_type TEXT NOT NULL,
    gross_amount REAL DEFAULT 0,
    fees REAL DEFAULT 0,
    net_amount REAL DEFAULT 0,
    currency TEXT DEFAULT 'USD',
    status TEXT DEFAULT 'PENDING',

    -- Attribution chain
    attribution_model TEXT DEFAULT 'LAST_TOUCH',
    attribution_path JSONB DEFAULT '[]',

    occurred_at TIMESTAMPTZ DEFAULT NOW(),
    settled_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_revenue_deal ON revenue_events (deal_id);
CREATE INDEX IF NOT EXISTS idx_revenue_source ON revenue_events (source_id);
CREATE INDEX IF NOT EXISTS idx_revenue_campaign ON revenue_events (campaign_id);
CREATE INDEX IF NOT EXISTS idx_revenue_content ON revenue_events (content_id);
CREATE INDEX IF NOT EXISTS idx_revenue_type ON revenue_events (revenue_type);
CREATE INDEX IF NOT EXISTS idx_revenue_occurred ON revenue_events (occurred_at DESC);

-- ============================================================
-- AUDIT LOG ENTRIES
-- Structured event logging
-- ============================================================
CREATE TABLE IF NOT EXISTS audit_log_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,
    entity_id TEXT,
    entity_type TEXT,
    correlation_id TEXT,
    source TEXT DEFAULT 'system',
    result TEXT DEFAULT 'success',
    error TEXT,
    payload JSONB DEFAULT '{}',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log_entries (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log_entries (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_audit_correlation ON audit_log_entries (correlation_id);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log_entries (created_at DESC);

-- ============================================================
-- HARDENING: constraints, triggers, data integrity
-- ============================================================

-- demand_signals: composite unique (upsert target)
ALTER TABLE demand_signals
    ADD CONSTRAINT uq_demand_segment UNIQUE (market, property_type, price_band);

-- revenue_events: net_amount invariant + valid status
ALTER TABLE revenue_events
    ADD CONSTRAINT chk_revenue_net CHECK (net_amount = gross_amount - fees),
    ADD CONSTRAINT chk_revenue_status CHECK (status IN ('PENDING','SETTLED','VOID','REFUNDED')),
    ADD CONSTRAINT chk_revenue_amount CHECK (gross_amount >= 0 AND fees >= 0);

-- follow_ups: valid channel + valid status
ALTER TABLE follow_ups
    ADD CONSTRAINT chk_followup_channel CHECK (channel IN ('CALL','SMS','WHATSAPP','EMAIL','MANUAL','SYSTEM')),
    ADD CONSTRAINT chk_followup_status CHECK (status IN ('PENDING','IN_PROGRESS','COMPLETED','SKIPPED','FAILED'));

-- next_best_actions: valid status
ALTER TABLE next_best_actions
    ADD CONSTRAINT chk_nba_status CHECK (status IN ('PENDING','IN_PROGRESS','COMPLETED','SKIPPED','OVERDUE'));

-- deal_submissions: valid status
ALTER TABLE deal_submissions
    ADD CONSTRAINT chk_deal_status CHECK (status IN (
        'INTAKE','VALIDATING','UNDERWRITING','SCORED','MATCHING',
        'BUYER_FOUND','OUTREACH_SENT','UNDER_CONTRACT','ASSIGNED',
        'CLOSED','LOST','REJECTED'
    ));

-- ============================================================
-- AUTO-UPDATE updated_at TRIGGERS
-- ============================================================

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_buyer_buy_boxes_updated
    BEFORE UPDATE ON buyer_buy_boxes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_deal_submissions_updated
    BEFORE UPDATE ON deal_submissions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_next_best_actions_updated
    BEFORE UPDATE ON next_best_actions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_follow_ups_updated
    BEFORE UPDATE ON follow_ups
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- ============================================================
-- DISPOSITION OUTCOMES (Phase F)
-- Tracks call dispositions with full audit trail
-- ============================================================
CREATE TABLE IF NOT EXISTS disposition_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id TEXT NOT NULL,
    entity_type TEXT DEFAULT 'seller',
    entity_id TEXT DEFAULT '',

    -- Disposition
    outcome TEXT NOT NULL CHECK (outcome IN (
        'CONNECTED','NO_ANSWER','VOICEMAIL','WRONG_NUMBER','WRONG_PARTY',
        'INTERESTED','NOT_INTERESTED','CALLBACK','APPOINTMENT','DNC'
    )),
    channel TEXT DEFAULT 'CALL',
    notes TEXT DEFAULT '',
    transcript TEXT DEFAULT '',

    -- Context
    call_duration_seconds INT DEFAULT 0,
    follow_up_required BOOLEAN DEFAULT FALSE,
    follow_up_channel TEXT,
    follow_up_scheduled_at TIMESTAMPTZ,

    -- Source attribution
    campaign_id TEXT DEFAULT '',
    content_id TEXT DEFAULT '',
    source_platform TEXT DEFAULT '',

    -- DNC tracking (terminal state)
    is_dnc BOOLEAN DEFAULT FALSE,
    dnc_reason TEXT DEFAULT '',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_disposition_lead ON disposition_outcomes (lead_id);
CREATE INDEX IF NOT EXISTS idx_disposition_outcome ON disposition_outcomes (outcome);
CREATE INDEX IF NOT EXISTS idx_disposition_dnc ON disposition_outcomes (is_dnc) WHERE is_dnc = TRUE;
CREATE INDEX IF NOT EXISTS idx_disposition_created ON disposition_outcomes (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_disposition_entity ON disposition_outcomes (entity_type, entity_id);

-- ============================================================
-- CONTENT TOUCH EVENTS (Phase I)
-- Tracks content → lead attribution chain
-- ============================================================
CREATE TABLE IF NOT EXISTS content_touches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_id TEXT NOT NULL,
    campaign_id TEXT DEFAULT '',
    lead_id TEXT NOT NULL,
    touch_type TEXT DEFAULT 'first_touch' CHECK (touch_type IN ('first_touch','assist','last_touch')),
    platform TEXT DEFAULT '',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_content_touch_content ON content_touches (content_id);
CREATE INDEX IF NOT EXISTS idx_content_touch_lead ON content_touches (lead_id);
CREATE INDEX IF NOT EXISTS idx_content_touch_campaign ON content_touches (campaign_id);
CREATE INDEX IF NOT EXISTS idx_content_touch_type ON content_touches (touch_type);
