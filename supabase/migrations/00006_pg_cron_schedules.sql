-- pg_cron Scheduling for Cloud Automation
-- Run this in Supabase Dashboard SQL Editor once.
-- Requires pg_cron extension to be enabled.
-- These jobs run on Supabase's servers 24/7 regardless of local machine.

-- Enable pg_cron extension (requires superuser — works in Supabase)
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Schedule: hourly email queue processing at :00
-- Calls the send-email-queue Edge Function via HTTP
SELECT cron.schedule(
    'send-email-queue-hourly',
    '0 * * * *',
    $$SELECT net.http_post(
        url := current_setting('app.settings.edge_function_base_url') || '/send-email-queue',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || current_setting('app.settings.service_role_key'),
            'Content-Type', 'application/json'
        ),
        body := '{"batchSize": 50}'
    )::text$$
);

-- Schedule: hourly lead pipeline trigger at :05
SELECT cron.schedule(
    'lead-pipeline-hourly',
    '5 * * * *',
    $$SELECT net.http_post(
        url := current_setting('app.settings.edge_function_base_url') || '/run-lead-pipeline',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || current_setting('app.settings.service_role_key'),
            'Content-Type', 'application/json'
        ),
        body := '{"mode": "all"}'
    )::text$$
);

-- Schedule: hourly clipping campaign scan at :10
SELECT cron.schedule(
    'clipping-scan-hourly',
    '10 * * * *',
    $$SELECT net.http_post(
        url := current_setting('app.settings.edge_function_base_url') || '/scan-clipping-campaigns',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || current_setting('app.settings.service_role_key'),
            'Content-Type', 'application/json'
        ),
        body := '{}'
    )::text$$
);

-- Schedule: daily campaign cache cleanup at 03:00 UTC
SELECT cron.schedule(
    'cleanup-old-scans-daily',
    '0 3 * * *',
    $$DELETE FROM campaigns_scan_cache WHERE scanned_at < now() - interval '7 days'$$
);

-- Create the scan cache table if it doesn't exist
CREATE TABLE IF NOT EXISTS campaigns_scan_cache (
    id TEXT PRIMARY KEY,
    title TEXT,
    brand TEXT,
    url TEXT,
    requirements JSONB DEFAULT '{}',
    raw_data JSONB DEFAULT '{}',
    scanned_at TIMESTAMPTZ DEFAULT now(),
    status TEXT DEFAULT 'discovered',
    picked_up_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Create email_queue index for cron performance
CREATE INDEX IF NOT EXISTS idx_email_queue_status_created
    ON email_queue (status, created_at)
    WHERE status = 'qued';

-- View: cron job status check
CREATE OR REPLACE VIEW cron_job_status AS
SELECT
    jobid,
    schedule,
    command,
    nodename,
    nodeport,
    database,
    username,
    active,
    jobname,
    last_run,
    next_run
FROM cron.job;

COMMENT ON VIEW cron_job_status IS 'Check active pg_cron jobs and their next run times';
