-- supabase/migrations/00010_notifications.sql
-- Durable log of every alert the control plane fires (Telegram + dashboards).
-- Survives fresh CI checkouts; queryable for audits and the revenue dashboard.
-- NOTE: requires `supabase db push` against the remote project (see 00009).

CREATE TABLE IF NOT EXISTS public.notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  event TEXT NOT NULL,                    -- ci:hourly-failure | revenue:stall | reply:new | ...
  channel TEXT NOT NULL DEFAULT 'telegram',
  message TEXT,
  status TEXT NOT NULL DEFAULT 'sent',    -- sent | failed | skipped
  repo TEXT,
  workflow TEXT,
  run_id TEXT,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notifications_created_at
  ON public.notifications (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_event
  ON public.notifications (event);

-- Ops-internal table: service_role only (CI inserts with the service key).
ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_notifications"
  ON public.notifications
  FOR ALL TO service_role USING (true) WITH CHECK (true);
