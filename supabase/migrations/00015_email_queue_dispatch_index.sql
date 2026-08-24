-- Phase 4: Supabase Performance & Email Queue Hardening
-- Adding campaign_id and deduplication columns

ALTER TABLE public.email_queue
ADD COLUMN IF NOT EXISTS campaign_id TEXT,
ADD COLUMN IF NOT EXISTS model_provider TEXT,
ADD COLUMN IF NOT EXISTS model_name TEXT,
ADD COLUMN IF NOT EXISTS cooldown_until TIMESTAMP WITH TIME ZONE,
ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMP WITH TIME ZONE;

-- Optimize the Node.js dispatcher loop
-- It fetches rows by `status = 'qued'` ORDER BY `created_at` ASC
CREATE INDEX IF NOT EXISTS idx_email_queue_dispatcher 
ON public.email_queue (status, created_at);

-- Optimize duplicate checking during insertion
CREATE INDEX IF NOT EXISTS idx_email_queue_recipient_email
ON public.email_queue (recipient_email);
