-- supabase/migrations/00009_email_replies.sql
-- Reply tracking for the reply_detector.py engine.
-- NOTE: requires `supabase db push` against the remote project. The remote DB
-- is currently missing base migrations 00003 (client_orders), 00007
-- (lead_pipeline_logs), 00008 (voice_agents) — run the full migration set.

-- 1. Allow email_queue rows to be marked as replied (reply_detector dedup).
ALTER TABLE public.email_queue DROP CONSTRAINT IF EXISTS email_queue_status_check;
ALTER TABLE public.email_queue
  ADD CONSTRAINT email_queue_status_check
  CHECK (status IN ('qued', 'queo', 'sent', 'failed', 'replied'));

ALTER TABLE public.email_queue ADD COLUMN IF NOT EXISTS replied_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE public.email_queue ADD COLUMN IF NOT EXISTS disposition TEXT;

-- 2. Permanent log of every detected reply (survives fresh CI checkouts).
CREATE TABLE IF NOT EXISTS public.email_replies (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email_queue_id UUID,
  recipient_email TEXT,
  original_subject TEXT,
  reply_class TEXT,               -- interested | not_interested | out_of_office | undecided
  from_email TEXT,
  from_display TEXT,
  message_id TEXT,
  snippet TEXT,
  detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_replies_detected_at
  ON public.email_replies (detected_at DESC);

ALTER TABLE public.email_replies ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_email_replies"
  ON public.email_replies
  FOR ALL TO service_role USING (true) WITH CHECK (true);
