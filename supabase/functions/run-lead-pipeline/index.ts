import { serve } from 'https://deno.land/std@0.224.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.45.6'

serve(async (req) => {
  const SUPABASE_URL = Deno.env.get('PROJECT_URL')!
  const SERVICE_ROLE_KEY = Deno.env.get('SERVICE_ROLE_KEY')!
  const BACKEND_WEBHOOK = Deno.env.get('BACKEND_WEBHOOK_URL') || ''

  let mode = 'all'
  try {
    const body = await req.json()
    mode = body.mode || 'all'
  } catch {
    // default to all
  }

  const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY)

  try {
    // Fetch pending lead campaigns from email_queue
    const { data: pendingEmails, error: emailError } = await supabase
      .from('email_queue')
      .select('id, recipient_email, subject, body')
      .eq('status', 'qued')
      .limit(100)

    if (emailError) throw new Error(`Email fetch failed: ${emailError.message}`)

    // Log pipeline run
    const { error: logError } = await supabase
      .from('lead_pipeline_logs')
      .insert({
        ran_at: new Date().toISOString(),
        mode,
        emails_queued: pendingEmails?.length || 0,
        status: 'completed',
      })

    if (logError) console.error('Log insert failed:', logError.message)

    // Notify backend for processing
    if (BACKEND_WEBHOOK) {
      try {
        await fetch(BACKEND_WEBHOOK, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event: 'lead_pipeline_run',
            mode,
            pending_emails: pendingEmails?.length || 0,
            timestamp: new Date().toISOString(),
          }),
        })
      } catch {
        // best-effort
      }
    }

    return new Response(JSON.stringify({
      success: true,
      mode,
      pending_emails: pendingEmails?.length || 0,
      emails_preview: (pendingEmails || []).slice(0, 5).map(e => ({
        id: e.id,
        to: e.recipient_email,
        subject: e.subject?.substring(0, 60),
      })),
      timestamp: new Date().toISOString(),
    }), {
      headers: { 'Content-Type': 'application/json' },
      status: 200,
    })
  } catch (err) {
    return new Response(JSON.stringify({
      success: false,
      error: err instanceof Error ? err.message : String(err),
    }), {
      headers: { 'Content-Type': 'application/json' },
      status: 500,
    })
  }
})
