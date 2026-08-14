-- supabase/migrations/00011_email_queue_indexes.sql
-- Fixes reply_detector / emailSender statement timeouts (Supabase error 57014).
-- The email_queue table grows fast under hourly 400-batch drains; every scan
-- does `WHERE status = 'sent' ORDER BY created_at DESC LIMIT 1000`, which
-- without an index is a full table sort that trips the 10s statement timeout.
--
-- Indexes:
--   (status, created_at DESC)  -> the reply_detector + emailSender hot path
--   (status)                   -> queued-send fan-out in emailSender
--   (sent_at)                  -> reply detection window scans
--
-- NOTE: requires `supabase db push` against the remote project.

CREATE INDEX IF NOT EXISTS idx_email_queue_status_created_at
  ON public.email_queue (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_email_queue_status
  ON public.email_queue (status);

CREATE INDEX IF NOT EXISTS idx_email_queue_sent_at
  ON public.email_queue (sent_at);