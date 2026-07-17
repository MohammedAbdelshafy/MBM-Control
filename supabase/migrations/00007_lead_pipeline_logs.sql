-- Lead pipeline run logs for cloud-scheduled runs
CREATE TABLE IF NOT EXISTS lead_pipeline_logs (
    id BIGSERIAL PRIMARY KEY,
    ran_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    mode TEXT NOT NULL DEFAULT 'all',
    emails_queued INTEGER DEFAULT 0,
    emails_processed INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    error_message TEXT,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_lead_pipeline_logs_ran_at
    ON lead_pipeline_logs (ran_at DESC);

-- Enable RLS but allow service_role full access
ALTER TABLE lead_pipeline_logs ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_all_lead_pipeline_logs"
    ON lead_pipeline_logs
    USING (true)
    WITH CHECK (true);
