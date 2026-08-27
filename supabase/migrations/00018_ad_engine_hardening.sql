-- Migration: AD Engine Hardening — DNC, Follow-up Safety, Concurrency, Realtime
-- Date: 2026-08-27
-- Strategy: Additive only. No existing tables modified.
-- Depends on: 00017_ad_engine_tables.sql

-- ============================================================
-- 1. REVISION COLUMNS (Optimistic Concurrency)
-- ============================================================
ALTER TABLE disposition_outcomes ADD COLUMN IF NOT EXISTS revision INT DEFAULT 1;
ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS revision INT DEFAULT 1;
ALTER TABLE deal_submissions ADD COLUMN IF NOT EXISTS revision INT DEFAULT 1;

-- ============================================================
-- 2. FOLLOW-UP SAFETY COLUMNS
-- ============================================================
ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS max_attempts INT DEFAULT 3;
ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS cooldown_hours INT DEFAULT 1;
ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS provider_status TEXT DEFAULT '';
ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS last_error TEXT DEFAULT '';
ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS idempotency_key TEXT DEFAULT '';
ALTER TABLE follow_ups ADD COLUMN IF NOT EXISTS terminal_reason TEXT DEFAULT '';

-- Index for idempotency lookups
CREATE UNIQUE INDEX IF NOT EXISTS idx_follow_ups_idempotency
    ON follow_ups (idempotency_key) WHERE idempotency_key != '';

-- ============================================================
-- 3. DNC ENFORCEMENT TRIGGER — blocks non-DNC → DNC reversal
-- ============================================================
CREATE OR REPLACE FUNCTION fn_dnc_enforce_terminal()
RETURNS TRIGGER AS $$
BEGIN
    -- If existing record is DNC, block any update that changes outcome
    IF OLD.is_dnc = TRUE AND NEW.outcome != OLD.outcome THEN
        RAISE EXCEPTION 'DNC is terminal: lead % cannot transition from DNC to %',
            NEW.lead_id, NEW.outcome;
    END IF;
    -- Increment revision on every update
    NEW.revision = COALESCE(OLD.revision, 1) + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dnc_enforce_terminal ON disposition_outcomes;
CREATE TRIGGER trg_dnc_enforce_terminal
    BEFORE UPDATE ON disposition_outcomes
    FOR EACH ROW EXECUTE FUNCTION fn_dnc_enforce_terminal();

-- ============================================================
-- 4. DNC FOLLOW-UP CANCELLATION TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION fn_dnc_cancel_followups()
RETURNS TRIGGER AS $$
BEGIN
    -- When a DNC disposition is inserted, cancel all pending follow-ups for that lead
    IF NEW.is_dnc = TRUE THEN
        UPDATE follow_ups
        SET status = 'SKIPPED',
            terminal_reason = 'DNC',
            updated_at = NOW()
        WHERE entity_id = NEW.lead_id
          AND entity_type = COALESCE(NEW.entity_type, 'seller')
          AND status = 'PENDING';

        -- Also cancel IN_PROGRESS follow-ups
        UPDATE follow_ups
        SET status = 'SKIPPED',
            terminal_reason = 'DNC',
            updated_at = NOW()
        WHERE entity_id = NEW.lead_id
          AND entity_type = COALESCE(NEW.entity_type, 'seller')
          AND status = 'IN_PROGRESS';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dnc_cancel_followups ON disposition_outcomes;
CREATE TRIGGER trg_dnc_cancel_followups
    AFTER INSERT ON disposition_outcomes
    FOR EACH ROW EXECUTE FUNCTION fn_dnc_cancel_followups();

-- ============================================================
-- 5. FOLLOW-UP CREATION BLOCK FOR DNC LEADS
-- ============================================================
CREATE OR REPLACE FUNCTION fn_block_followup_for_dnc()
RETURNS TRIGGER AS $$
DECLARE
    is_dnc BOOLEAN;
BEGIN
    SELECT EXISTS(
        SELECT 1 FROM disposition_outcomes
        WHERE lead_id = NEW.entity_id
          AND is_dnc = TRUE
        LIMIT 1
    ) INTO is_dnc;

    IF is_dnc THEN
        RAISE EXCEPTION 'Cannot create follow-up for DNC lead %', NEW.entity_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_block_followup_for_dnc ON follow_ups;
CREATE TRIGGER trg_block_followup_for_dnc
    BEFORE INSERT ON follow_ups
    FOR EACH ROW EXECUTE FUNCTION fn_block_followup_for_dnc();

-- ============================================================
-- 6. FOLLOW-UP RETRY SAFETY TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION fn_followup_retry_safety()
RETURNS TRIGGER AS $$
BEGIN
    -- Block retry after exhaustion
    IF OLD.status = 'FAILED'
       AND OLD.attempt_count >= COALESCE(OLD.max_attempts, 3)
       AND NEW.status = 'PENDING' THEN
        RAISE EXCEPTION 'Follow-up % exhausted after % attempts — cannot retry',
            OLD.id, OLD.attempt_count;
    END IF;

    -- Block retry after DNC terminal reason
    IF OLD.terminal_reason = 'DNC' AND NEW.status = 'PENDING' THEN
        RAISE EXCEPTION 'Follow-up % has DNC terminal reason — cannot retry', OLD.id;
    END IF;

    -- Block retry after COMPLETED
    IF OLD.status = 'COMPLETED' AND NEW.status = 'PENDING' THEN
        RAISE EXCEPTION 'Follow-up % already completed — cannot retry', OLD.id;
    END IF;

    -- Increment revision
    NEW.revision = COALESCE(OLD.revision, 1) + 1;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_followup_retry_safety ON follow_ups;
CREATE TRIGGER trg_followup_retry_safety
    BEFORE UPDATE ON follow_ups
    FOR EACH ROW EXECUTE FUNCTION fn_followup_retry_safety();

-- ============================================================
-- 7. DNC AUDIT TRIGGER
-- ============================================================
CREATE OR REPLACE FUNCTION fn_dnc_audit_event()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.is_dnc = TRUE AND (OLD IS NULL OR OLD.is_dnc != TRUE) THEN
        INSERT INTO audit_log_entries (
            event_type, entity_id, entity_type, source, result, payload, created_at
        ) VALUES (
            'dnc_transition',
            NEW.lead_id,
            COALESCE(NEW.entity_type, 'seller'),
            'dnc_trigger',
            'success',
            jsonb_build_object(
                'disposition_id', NEW.id,
                'outcome', NEW.outcome,
                'dnc_reason', NEW.dnc_reason,
                'previous_outcome', CASE WHEN OLD IS NOT NULL THEN OLD.outcome ELSE NULL END
            ),
            NOW()
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_dnc_audit_event ON disposition_outcomes;
CREATE TRIGGER trg_dnc_audit_event
    AFTER INSERT ON disposition_outcomes
    FOR EACH ROW EXECUTE FUNCTION fn_dnc_audit_event();

-- ============================================================
-- 8. REVISION CHECK FUNCTION (Optimistic Concurrency)
-- ============================================================
CREATE OR REPLACE FUNCTION fn_check_revision()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.revision IS NOT NULL AND NEW.revision IS NOT NULL THEN
        IF NEW.revision != OLD.revision THEN
            RAISE EXCEPTION 'Stale write: expected revision %, got % for % %',
                OLD.revision, NEW.revision, TG_TABLE_NAME, OLD.id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply revision check to key tables
DROP TRIGGER IF EXISTS trg_disposition_revision ON disposition_outcomes;
CREATE TRIGGER trg_disposition_revision
    BEFORE UPDATE ON disposition_outcomes
    FOR EACH ROW EXECUTE FUNCTION fn_check_revision();

DROP TRIGGER IF EXISTS trg_followup_revision ON follow_ups;
CREATE TRIGGER trg_followup_revision
    BEFORE UPDATE ON follow_ups
    FOR EACH ROW EXECUTE FUNCTION fn_check_revision();

DROP TRIGGER IF EXISTS trg_deal_revision ON deal_submissions;
CREATE TRIGGER trg_deal_revision
    BEFORE UPDATE ON deal_submissions
    FOR EACH ROW EXECUTE FUNCTION fn_check_revision();

-- ============================================================
-- 9. REALTIME PUBLICATIONS
-- ============================================================
-- Enable Realtime for disposition_outcomes and follow_ups
ALTER PUBLICATION supabase_realtime ADD TABLE disposition_outcomes;
ALTER PUBLICATION supabase_realtime ADD TABLE follow_ups;
ALTER PUBLICATION supabase_realtime ADD TABLE deal_submissions;

-- ============================================================
-- 10. OUTBOX TABLE (Transactional Event Delivery)
-- ============================================================
CREATE TABLE IF NOT EXISTS outbox_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type TEXT NOT NULL,
    aggregate_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB DEFAULT '{}',
    published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    published_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_outbox_unpublished ON outbox_events (created_at ASC)
    WHERE published = FALSE;
CREATE INDEX IF NOT EXISTS idx_outbox_aggregate ON outbox_events (aggregate_type, aggregate_id);
