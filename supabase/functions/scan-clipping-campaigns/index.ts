import { serve } from 'https://deno.land/std@0.224.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.45.6'

interface Campaign {
  id: string
  title: string
  brand_name?: string
  brand?: string
  url?: string
  campaign_url?: string
  requirements?: Record<string, unknown>
}

serve(async (req) => {
  const SUPABASE_URL = Deno.env.get('PROJECT_URL')!
  const SERVICE_ROLE_KEY = Deno.env.get('SERVICE_ROLE_KEY')!
  const CLIPPING_EMAIL = Deno.env.get('CLIPPING_EMAIL') || ''
  const CLIPPING_PASSWORD = Deno.env.get('CLIPPING_PASSWORD') || ''
  const BACKEND_WEBHOOK = Deno.env.get('BACKEND_WEBHOOK_URL') || ''

  const supabase = createClient(SUPABASE_URL, SERVICE_ROLE_KEY)

  try {
    // Try public clipping.com API
    let campaigns: Campaign[] = []

    const publicResp = await fetch('https://clipping.com/api/v1/campaigns?status=open', {
      headers: { 'User-Agent': 'Mozilla/5.0' },
    })
    if (publicResp.ok) {
      const data = await publicResp.json()
      campaigns = data.campaigns || data.data || []
    }

    // Fallback: authenticated scan if credentials provided
    if (campaigns.length === 0 && CLIPPING_EMAIL && CLIPPING_PASSWORD) {
      const loginResp = await fetch('https://clipping.com/api/v1/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0' },
        body: JSON.stringify({ email: CLIPPING_EMAIL, password: CLIPPING_PASSWORD }),
      })
      if (loginResp.ok) {
        const tokenData = await loginResp.json()
        const token = tokenData.token || tokenData.access_token || ''
        if (token) {
          const authResp = await fetch('https://clipping.com/api/v1/campaigns', {
            headers: { Authorization: `Bearer ${token}`, 'User-Agent': 'Mozilla/5.0' },
          })
          if (authResp.ok) {
            const data = await authResp.json()
            campaigns = data.campaigns || data.data || []
          }
        }
      }
    }

    // Store in Supabase
    let stored = 0
    for (const c of campaigns) {
      const campaignId = c.id || crypto.randomUUID()
      const { error } = await supabase.from('campaigns_scan_cache').upsert({
        id: campaignId,
        title: c.title || '',
        brand: c.brand_name || c.brand || '',
        url: c.url || c.campaign_url || '',
        requirements: c.requirements || {},
        raw_data: c,
        scanned_at: new Date().toISOString(),
        status: 'discovered',
      }, { onConflict: 'id' })
      if (!error) stored++
    }

    // Notify backend webhook
    if (BACKEND_WEBHOOK && campaigns.length > 0) {
      try {
        await fetch(BACKEND_WEBHOOK, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ campaigns, source: 'supabase_scan' }),
        })
      } catch {
        // webhook is best-effort
      }
    }

    return new Response(JSON.stringify({
      success: true,
      campaigns_found: campaigns.length,
      campaigns_stored: stored,
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
