-- supabase/migrations/00016_email_queue_revenue_pipeline.sql

-- Expand status check constraint to support the deduplication script states
ALTER TABLE public.email_queue DROP CONSTRAINT IF EXISTS email_queue_status_check;
ALTER TABLE public.email_queue ADD CONSTRAINT email_queue_status_check 
  CHECK (status IN ('qued', 'queo', 'sent', 'failed', 'duplicate', 'skipped', 'suppressed', 'opt_out'));

-- Add lead_id to ensure Dial/Email collision tracking (Phase 11)
ALTER TABLE public.email_queue ADD COLUMN IF NOT EXISTS lead_id UUID;
CREATE INDEX IF NOT EXISTS idx_email_queue_lead_id ON public.email_queue(lead_id);

-- Add source/provenance to track where the lead came from (Phase 10)
ALTER TABLE public.email_queue ADD COLUMN IF NOT EXISTS source TEXT;

-- For deduplication: A single lead should only receive one email per campaign.
-- This ensures database-level protection against duplicates if the API fails to check.
CREATE UNIQUE INDEX IF NOT EXISTS uq_email_queue_recipient_campaign 
ON public.email_queue(recipient_email, COALESCE(campaign_id, 'DEFAULT')) 
WHERE status NOT IN ('failed', 'skipped', 'duplicate');
