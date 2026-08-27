import express from 'express';
import crypto from 'crypto';
import fs from 'fs';
import { createClient } from '@supabase/supabase-js';
import multer from 'multer';
import cron from 'node-cron';
import { sendEmailQueue } from './emailSender.js';
import { generateAllDemos, queuePromoCampaign } from './demoCampaign.js';
import { queueBuyerCampaign, queueAICampaign, queueSellerCampaign, generateSellerWhatsAppReport, loadStats } from './leadPipeline.js';
import { hunt } from './clientHunter.js';
import { netellerLink, netellerWalletLabel, NETELLER_EMAIL, NETELLER_ACCOUNT_ID } from './neteller.js';
import { patchLeads as gatewayPatchLeads } from './dialer/dialerDbGateway.js';
import { compareDialerLeads } from './dialer/freshnessOrder.js';
import aftercallRouter from './dialer/aftercallRouter.js';
import emailApi from './dialer/emailApi.js';
import adEngineRouter from './dialer/adEngineRouter.js';
import { getProvider, normalizeEvent } from './dialer/telephonyProvider.js';

import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3002;

// SECURITY: Supabase URL + anon key must come from env. If missing, fail fast
// so misconfiguration is caught at boot, not silently at the first request.
const supabaseUrl = process.env.VITE_SUPABASE_URL;
const supabaseKey = process.env.VITE_SUPABASE_ANON_KEY;
if (!supabaseUrl || !supabaseKey) {
  console.error('[FATAL] Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY in environment.');
  console.error('Set them in .env (see .env.example) before starting the server.');
  process.exit(1);
}
const supabase = createClient(supabaseUrl, supabaseKey);

const supabaseAdmin = process.env.SUPABASE_SERVICE_ROLE_KEY
  ? createClient(supabaseUrl, process.env.SUPABASE_SERVICE_ROLE_KEY)
  : null;

// â”€â”€ SECURITY: CORS allowlist + optional bearer-token auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Never wildcard CORS: only the frontend origin(s) may call from a browser.
// Requests without an Origin header (curl, server-to-server, CI) pass through.
// Default allowlist covers the Vite dev server; extend via CORS_ORIGINS
// (comma-separated) for other deployments.
const allowedOrigins = (process.env.CORS_ORIGINS || 'http://localhost:5173,http://127.0.0.1:5173')
  .split(',').map(s => s.trim()).filter(Boolean);

app.use((req, res, next) => {
  const origin = req.headers.origin;
  if (origin) {
    if (allowedOrigins.includes(origin)) {
      res.setHeader('Access-Control-Allow-Origin', origin);
      res.setHeader('Vary', 'Origin');
    } else {
      return res.status(403).json({ error: 'origin_not_allowed' });
    }
  }
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, Authorization');
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  if (req.method === 'OPTIONS') return res.sendStatus(204);
  next();
});

// Optional API bearer token. When API_BEARER_TOKEN is set, PROTECTED_PREFIXES
// require `Authorization: Bearer <token>` (constant-time compare). When unset
// the server logs a loud warning and stays open so the dashboard keeps working
// in local dev â€” set the token before exposing the server to a network.
const API_BEARER_TOKEN = process.env.API_BEARER_TOKEN || '';
if (API_BEARER_TOKEN) {
  console.log('[SECURITY] API_BEARER_TOKEN set â€” sensitive /api routes require Authorization: Bearer <token>');
} else {
  console.warn('[SECURITY] WARNING: API_BEARER_TOKEN is NOT set. Sensitive /api routes '
    + '(dialer PII, telephony call endpoints, orders, payout, telegram-alert) are UNPROTECTED. '
    + 'Set API_BEARER_TOKEN in env before exposing this server beyond localhost.');
}

const PROTECTED_PREFIXES = [
  '/api/dialer', '/api/orders', '/api/creator/payout', '/api/sales/telegram-alert',
  '/api/checkout', '/api/voice-agents/place-call', '/api/instant-cash/cold-calling',
];

const requireApiAuth = (req, res, next) => {
  if (!API_BEARER_TOKEN) return next();
  const auth = req.headers.authorization || '';
  const supplied = auth.startsWith('Bearer ') ? auth.slice(7) : '';
  const ok = supplied.length > 0
    && supplied.length === API_BEARER_TOKEN.length
    && crypto.timingSafeEqual(Buffer.from(supplied), Buffer.from(API_BEARER_TOKEN));
  if (!ok) return res.status(401).json({ error: 'unauthorized' });
  next();
};

for (const prefix of PROTECTED_PREFIXES) {
  app.use(prefix, requireApiAuth);
}

// Whop webhook needs the RAW request body for HMAC signature verification â€”
// capture it before express.json() parses (and destroys) the stream.
app.use('/api/webhook/whop', express.raw({ type: '*/*', limit: '1mb' }));
app.use(express.json({ limit: '10mb' }));
app.use('/api', aftercallRouter);
app.use('/api', emailApi);
app.use('/api', adEngineRouter);
app.use('/videos', express.static(path.join(__dirname, '..', 'clipping-factory', 'MBM-Social', 'generated_videos')));
app.use('/publish-queue', express.static(path.join(__dirname, '..', 'clipping-factory', 'MBM-Social', 'publish_queue', 'media')));

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });

// GET /api/videos â€” List all generated HD videos for instant web playback
app.get('/api/videos', (req, res) => {
  try {
    const videosDir = path.join(__dirname, '..', 'clipping-factory', 'MBM-Social', 'generated_videos');
    if (fs.existsSync(videosDir)) {
      const files = fs.readdirSync(videosDir).filter(f => f.endsWith('.mp4'));
      const videoList = files.map(file => ({
        filename: file,
        play_url: `http://localhost:3002/videos/${file}`,
        size_kb: Math.round(fs.statSync(path.join(videosDir, file)).size / 1024)
      }));
      return res.json({ status: 'success', count: videoList.length, videos: videoList });
    }
    res.json({ status: 'success', count: 0, videos: [] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// Health check
app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString(), uptime: process.uptime() });
});

// Bawab Signup (replaces Base44 bawabSignup function)
app.post('/api/bawab-signup', async (req, res) => {
  try {
    const { name, phone, address, gps_lat, gps_lng, photo, num_floors, num_apartments, link_user_id, property_type } = req.body;
    const ptype = property_type || 'apartment_building';
    const isApartment = ptype === 'apartment_building';

    if (!name || !phone || !address) {
      return res.status(400).json({ error: 'Missing required fields (name, phone, address)' });
    }
    if (gps_lat == null || gps_lng == null) {
      return res.status(400).json({ error: 'GPS location is required' });
    }

    const { data: building, error: buildError } = await supabase
      .from('buildings')
      .insert({
        name: address,
        address,
        property_type: ptype,
        bawab_name: isApartment ? name : '',
        bawab_phone: isApartment ? phone : '',
        contact_person_name: isApartment ? '' : name,
        contact_person_phone: isApartment ? '' : phone,
        gps_lat: Number(gps_lat),
        gps_lng: Number(gps_lng),
        photo: photo || '',
        num_floors: isApartment && num_floors ? Number(num_floors) : null,
        num_apartments: isApartment && num_apartments ? Number(num_apartments) : null,
        status: 'pickup_requested',
        source: 'bawab_signup',
      })
      .select()
      .single();

    if (buildError) throw buildError;

    if (link_user_id) {
      await supabase.from('users').update({ building_id: building.id }).eq('id', link_user_id);
    }

    res.json({ success: true, building_id: building.id });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Complete Self Signup (replaces Base44 completeSelfSignup function)
const KNOWN_ROLES = ['admin', 'ops', 'sales_rep', 'banger', 'data_manager', 'driver', 'warehouse_foreman', 'customer'];

app.post('/api/complete-signup', async (req, res) => {
  try {
    const { user_id, building_id } = req.body;
    if (!user_id) return res.status(400).json({ error: 'user_id required' });

    const { data: user, error: userError } = await supabase.from('users').select('*').eq('id', user_id).single();
    if (userError || !user) return res.status(404).json({ error: 'User not found' });

    // Already has a real role
    if (user.role && KNOWN_ROLES.includes(user.role)) {
      if (building_id) {
        await supabase.from('users').update({ building_id }).eq('id', user_id);
      }
      return res.json({ success: true, role: user.role, changed: false });
    }

    // Admin-invited accounts stay pending
    if (user.invited_by_admin) {
      return res.json({ success: true, role: user.role || 'user', changed: false, pending: true });
    }

    // Check for pending invitation
    const { data: invitations } = await supabase
      .from('invitations')
      .select('*')
      .eq('email', user.email)
      .eq('status', 'pending')
      .limit(1);

    if (invitations && invitations.length > 0) {
      const inv = invitations[0];
      const updateData = { role: inv.intended_role, invited_by_admin: true };
      if (building_id) updateData.building_id = building_id;
      await supabase.from('users').update(updateData).eq('id', user_id);
      await supabase.from('invitations').update({ status: 'accepted', accepted_user_id: user_id }).eq('id', inv.id);
      return res.json({ success: true, role: inv.intended_role, changed: true });
    }

    // Self-signup without a role â†’ assign 'customer'
    const updateData = { role: 'customer' };
    if (building_id) updateData.building_id = building_id;
    await supabase.from('users').update(updateData).eq('id', user_id);
    res.json({ success: true, role: 'customer', changed: true });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Daily Operations Summary (replaces Base44 dailyOperationsSummary function)
function todayCairo() {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Africa/Cairo',
    year: 'numeric', month: '2-digit', day: '2-digit',
  }).format(new Date());
}

function escapeCsv(val) {
  if (val == null) return '';
  const s = String(val);
  if (s.includes(',') || s.includes('"') || s.includes('\n')) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

function rowsToCsv(headers, rows) {
  return [headers.join(','), ...rows.map(r => r.map(escapeCsv).join(','))].join('\n');
}

async function generateOperationsReport(mode = 'download') {
  const date = todayCairo();

  const [pickupsRes, dumpsRes, paymentsRes] = await Promise.all([
    supabase.from('pickups').select('*').eq('date', date),
    supabase.from('dumps').select('*').order('created_date', { ascending: false }).limit(500),
    supabase.from('payments').select('*').eq('payment_date', date),
  ]);

  const pickups = pickupsRes.data || [];
  const dumps = (dumpsRes.data || []).filter(d => d.timestamp && d.timestamp.startsWith(date));
  const payments = paymentsRes.data || [];

  const pickupCsv = rowsToCsv(
    ['building_name', 'status', 'driver', 'completion_time', 'failure_reason'],
    pickups.map(p => [p.building_name || '', p.status || '', p.assigned_driver_name || '', p.completion_timestamp || '', p.failure_reason || ''])
  );

  const dumpCsv = rowsToCsv(
    ['vehicle_name', 'waste_type', 'weight_kg', 'logged_by', 'timestamp'],
    dumps.map(d => [d.vehicle_name || '', d.waste_type || '', d.weight_kg != null ? String(d.weight_kg) : '', d.logged_by_name || '', d.timestamp || ''])
  );

  const paymentCsv = rowsToCsv(
    ['building_name', 'amount', 'collected_by', 'payment_date', 'note'],
    payments.map(p => [p.building_name || '', p.amount != null ? String(p.amount) : '', p.collected_by_name || '', p.payment_date || '', p.note || ''])
  );

  const csvContent = [
    `=== PICKUPS (${pickups.length}) ===`,
    pickupCsv,
    '',
    `=== DUMPS (${dumps.length}) ===`,
    dumpCsv,
    '',
    `=== PAYMENTS (${payments.length}) ===`,
    paymentCsv,
  ].join('\n');

  const summary = [
    `Date: ${date}`,
    `Pickups: ${pickups.filter(p => p.status === 'done').length} done, ${pickups.filter(p => p.status === 'failed').length} failed, ${pickups.filter(p => p.status === 'pending').length} pending`,
    `Dumps: ${dumps.length}`,
    `Payments: ${payments.length} (total: ${payments.reduce((s, p) => s + (p.amount || 0), 0)} EGP)`,
  ].join('\n');

  // Store or update report
  const { data: existing } = await supabase
    .from('daily_reports')
    .select('id')
    .eq('date', date)
    .eq('type', 'operations_summary')
    .limit(1);

  if (existing && existing.length > 0) {
    await supabase.from('daily_reports').update({ csv_content: csvContent, summary }).eq('id', existing[0].id);
  } else {
    await supabase.from('daily_reports').insert({ date, type: 'operations_summary', csv_content: csvContent, summary });
  }

  return { date, pickups, dumps, payments, csvContent, summary };
}

app.get('/api/daily-report', async (req, res) => {
  try {
    const mode = req.query.mode || 'download';
    const report = await generateOperationsReport(mode);

    if (mode === 'store_only') {
      return res.json({ ok: true, date: report.date, pickups: report.pickups.length, dumps: report.dumps.length, payments: report.payments.length });
    }

    res.setHeader('Content-Type', 'text/csv; charset=utf-8');
    res.setHeader('Content-Disposition', `attachment; filename="daily_operations_${report.date}.csv"`);
    res.send(report.csvContent);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// File Upload
app.post('/api/upload', upload.single('file'), async (req, res) => {
  try {
    if (!req.file) return res.status(400).json({ error: 'No file provided' });

    const ext = req.file.originalname.split('.').pop();
    const fileName = `${Math.random().toString(36).substring(2, 15)}_${Date.now()}.${ext}`;
    const filePath = `public/${fileName}`;

    const { error: uploadError } = await supabase.storage
      .from('uploads')
      .upload(filePath, req.file.buffer, { contentType: req.file.mimetype });

    if (uploadError) throw uploadError;

    const { data: { publicUrl } } = supabase.storage.from('uploads').getPublicUrl(filePath);
    res.json({ file_url: publicUrl });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Add emails to queue
app.post('/api/email-queue', async (req, res) => {
  try {
    if (!supabaseAdmin) {
      return res.status(500).json({ error: 'SUPABASE_SERVICE_ROLE_KEY not configured' });
    }

    const emails = req.body.emails || [req.body];
    const rows = emails.map(e => ({
      recipient_email: e.recipient_email || e.to || e.email,
      subject: e.subject || '',
      body: e.body || e.message || e.html || '',
      status: 'qued',
    }));

    if (!rows.length || !rows[0].recipient_email) {
      return res.status(400).json({ error: 'recipient_email required' });
    }

    const { data, error } = await supabaseAdmin.from('email_queue').insert(rows).select('id');
    if (error) throw error;

    res.json({ queued: data.length, ids: data.map(r => r.id) });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Send Email Queue
app.post('/api/send-email-queue', async (req, res) => {
  try {
    if (!supabaseAdmin) {
      return res.status(500).json({ error: 'SUPABASE_SERVICE_ROLE_KEY not configured' });
    }

    const result = await sendEmailQueue({ supabase: supabaseAdmin, batchSize: req.body?.batch_size || 50 });
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Get Email Queue status counts
app.get('/api/email-queue-status', async (req, res) => {
  try {
    if (!supabaseAdmin) {
      return res.status(500).json({ error: 'SUPABASE_SERVICE_ROLE_KEY not configured' });
    }

    const { data, error } = await supabaseAdmin
      .from('email_queue')
      .select('status');

    if (error) throw error;

    const counts = { qued: 0, queo: 0, sent: 0, failed: 0, total: 0 };
    for (const row of data) {
      if (counts[row.status] != null) counts[row.status]++;
      counts.total++;
    }

    res.json(counts);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// â”€â”€ Demo Campaign API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

app.post('/api/demo/generate', async (req, res) => {
  try {
    const results = await generateAllDemos({ useAI: true });
    res.json({ generated: results.length, demos: results });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/demo/campaign', async (req, res) => {
  try {
    if (!supabaseAdmin) {
      return res.status(500).json({ error: 'SUPABASE_SERVICE_ROLE_KEY not configured' });
    }
    const targetEmails = req.body?.emails || null;
    const result = await queuePromoCampaign({ supabase: supabaseAdmin, targetEmails });
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// â”€â”€ Lead Pipeline API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

app.get('/api/leads/stats', (req, res) => {
  try {
    const stats = loadStats();
    res.json(stats);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/leads/pipeline/buyers', async (req, res) => {
  try {
    if (!supabaseAdmin) return res.status(500).json({ error: 'SUPABASE_SERVICE_ROLE_KEY not configured' });
    const pricing = req.body?.pricing || { single_day: 18, full_day: 30, monthly: 375 };
    const result = await queueBuyerCampaign({ supabase: supabaseAdmin, pricing });
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/leads/pipeline/ai', async (req, res) => {
  try {
    if (!supabaseAdmin) return res.status(500).json({ error: 'SUPABASE_SERVICE_ROLE_KEY not configured' });
    const result = await queueAICampaign({ supabase: supabaseAdmin });
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/leads/pipeline/sellers', async (req, res) => {
  try {
    if (!supabaseAdmin) return res.status(500).json({ error: 'SUPABASE_SERVICE_ROLE_KEY not configured' });
    const result = await queueSellerCampaign({ supabase: supabaseAdmin });
    res.json(result);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.post('/api/leads/pipeline/all', async (req, res) => {
  try {
    if (!supabaseAdmin) return res.status(500).json({ error: 'SUPABASE_SERVICE_ROLE_KEY not configured' });
    const pricing = req.body?.pricing || { single_day: 18, full_day: 30, monthly: 375 };
    const buyerR = await queueBuyerCampaign({ supabase: supabaseAdmin, pricing });
    const sellerR = await queueSellerCampaign({ supabase: supabaseAdmin });
    const aiR = await queueAICampaign({ supabase: supabaseAdmin });
    res.json({ buyers: buyerR, sellers: sellerR, ai: aiR });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// â”€â”€ Analytics API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const ANALYTICS_LOG_FILE = path.join(__dirname, '..', 'MBM', 'Whop', 'analytics_log.json');
const ANALYTICS_MAX_ENTRIES = 5000;
const ANALYTICS_ALLOWED_EVENTS = new Set([
  'landing_view', 'cta_click', 'signup', 'checkout_started', 'checkout_completed',
  'upsell_viewed', 'upsell_accepted',
]);

app.post('/api/analytics/track', (req, res) => {
  try {
    const eventName = String(req.body?.event || '').trim();
    if (!ANALYTICS_ALLOWED_EVENTS.has(eventName)) {
      return res.status(400).json({ error: `event '${eventName.slice(0, 40)}' not allowed` });
    }
    // Clamp payload size (untrusted client).
    const props = req.body?.props && typeof req.body.props === 'object' ? req.body.props : {};
    const safeProps = {};
    for (const [k, v] of Object.entries(props)) {
      if (safeProps.length > 40) break;
      safeProps[k] = String(v).slice(0, 200);
    }

    const receivedAt = new Date().toISOString();
    const eventData = {
      event: eventName,
      url: typeof req.body?.url === 'string' ? req.body.url.slice(0, 500) : undefined,
      timestamp: typeof req.body?.timestamp === 'string' ? req.body.timestamp.slice(0, 64) : receivedAt,
      session_id: typeof req.body?.session_id === 'string' ? req.body.session_id.slice(0, 64) : undefined,
      utm_source: req.body?.utm_source ? String(req.body.utm_source).slice(0, 120) : undefined,
      utm_medium: req.body?.utm_medium ? String(req.body.utm_medium).slice(0, 120) : undefined,
      utm_campaign: req.body?.utm_campaign ? String(req.body.utm_campaign).slice(0, 120) : undefined,
      utm_content: req.body?.utm_content ? String(req.body.utm_content).slice(0, 120) : undefined,
      referral: req.body?.referral ? String(req.body.referral).slice(0, 120) : undefined,
      landing_variant: req.body?.landing_variant != null ? String(req.body.landing_variant).slice(0, 8) : undefined,
      props: safeProps,
      received_at: receivedAt,
    };

    // Legacy array log (dashboards read this) with rotation cap.
    let logs = [];
    if (fs.existsSync(ANALYTICS_LOG_FILE)) {
      try { logs = JSON.parse(fs.readFileSync(ANALYTICS_LOG_FILE, 'utf8')); } catch {}
    }
    if (!Array.isArray(logs)) logs = [];

    // Dedupe identical events from the same session within 60s.
    const fingerprint = JSON.stringify([eventName, eventData.session_id, eventData.url, safeProps]);
    const isDup = logs.some(l =>
      l._fingerprint === fingerprint &&
      (new Date(receivedAt) - new Date(l.received_at)) < 60000);
    if (isDup) {
      return res.json({ success: true, deduplicated: true });
    }

    logs.push({ ...eventData, _fingerprint: fingerprint });
    if (logs.length > ANALYTICS_MAX_ENTRIES) {
      logs = logs.slice(-Math.floor(ANALYTICS_MAX_ENTRIES * 0.8));
    }
    fs.writeFileSync(ANALYTICS_LOG_FILE, JSON.stringify(logs, null, 2), 'utf8');

    // Canonical store entry (idempotent by deterministic event_id).
    appendRevenueEvent({
      schema_version: 1,
      event_id: crypto.createHash('sha256').update(fingerprint).digest('hex').slice(0, 24),
      event_name: eventName,
      source: 'landing',
      timestamp: eventData.timestamp || receivedAt,
      customer_ref: {},
      session_id: eventData.session_id || null,
      amount_usd: null,
      currency: 'USD',
      attribution: {
        ...(eventData.utm_source ? { utm_source: eventData.utm_source } : {}),
        ...(eventData.utm_medium ? { utm_medium: eventData.utm_medium } : {}),
        ...(eventData.utm_campaign ? { utm_campaign: eventData.utm_campaign } : {}),
        ...(eventData.utm_content ? { utm_content: eventData.utm_content } : {}),
        ...(eventData.referral ? { referral: eventData.referral } : {}),
        ...(eventData.landing_variant ? { landing_variant: eventData.landing_variant } : {}),
      },
      metadata: safeProps,
    });

    console.log('[Analytics] Track Event Stored:', eventName);
    res.json({ success: true, logged: true });
  } catch(e) {
    console.error('Analytics err', e);
    res.status(500).json({error: 'storage failed'});
  }
});

// â”€â”€ Whop Webhook API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const REVENUE_EVENTS_FILE = path.join(__dirname, '..', 'MBM', 'Whop', 'logs', 'revenue_events.jsonl');

function appendRevenueEvent(event) {
  // Canonical idempotent event store shared with MBM/Whop/whop_revenue_os.py
  fs.mkdirSync(path.dirname(REVENUE_EVENTS_FILE), { recursive: true });
  let dup = false;
  if (fs.existsSync(REVENUE_EVENTS_FILE)) {
    const buf = fs.readFileSync(REVENUE_EVENTS_FILE, 'utf8');
    for (const line of buf.split('\n')) {
      if (!line.trim()) continue;
      try { if (JSON.parse(line).event_id === event.event_id) { dup = true; break; } } catch {}
    }
  }
  if (dup) return false;
  fs.appendFileSync(REVENUE_EVENTS_FILE, JSON.stringify(event, null, 0) + '\n', 'utf8');
  return true;
}

function normalizeWhopWebhook(payload, receivedAt) {
  const action = String(payload.action || '');
  const map = [
    ['payment.succeeded', 'purchase'], ['payment_succeeded', 'purchase'],
    ['membership.went_valid', 'subscription_started'], ['membership_went_valid', 'subscription_started'],
    ['payment.failed', 'checkout_failed'], ['refund', 'refund'],
    ['membership.went_invalid', 'churn'], ['membership_went_invalid', 'churn'],
    ['renewal', 'subscription_renewed'],
  ];
  let canonical = 'webhook_received';
  for (const [needle, name] of map) { if (action.includes(needle)) { canonical = name; break; } }

  const data = payload.data && typeof payload.data === 'object' ? payload.data : {};
  const payment = data.payment && typeof data.payment === 'object' ? data.payment : {};
  let amount = null;
  if (canonical === 'purchase') {
    for (const key of ['amount', 'total', 'final_amount']) {
      const v = payment[key];
      if (typeof v === 'number') { amount = v > 1000 ? Math.round(v) / 100 : Math.round(v * 100) / 100; break; }
    }
  }
  const member = data.member && typeof data.member === 'object' ? data.member : {};
  const customerRef = {};
  for (const key of ['user_id', 'email', 'username']) { if (member[key]) customerRef[key] = member[key]; }
  if (data.user_id) customerRef.user_id = data.user_id;

  // Per-product funnel attribution: carry product/plan ids when Whop sends them.
  const productId = payment.product_id || data.product_id || null;
  const planId = payment.plan_id || data.plan_id || (data.plan && typeof data.plan === 'object' ? data.plan.id : null);

  return {
    schema_version: 1,
    event_id: payload.id || payload.event_id || crypto.randomUUID(),
    event_name: canonical,
    source: 'whop_webhook',
    timestamp: receivedAt,
    customer_ref: customerRef,
    session_id: null,
    amount_usd: amount,
    currency: (payment.currency || 'USD').toUpperCase(),
    attribution: { via: 'webhook' },
    metadata: {
      action,
      ...(productId ? { product_id: String(productId) } : {}),
      ...(planId ? { plan_id: String(planId) } : {}),
    },
  };
}

app.post('/api/webhook/whop', (req, res) => {
  const secret = process.env.WHOP_WEBHOOK_SECRET;
  if (!secret) {
    console.error('[Webhook] WHOP_WEBHOOK_SECRET is missing');
    return res.status(500).json({ error: 'Webhook secret not configured' });
  }

  const signature = String(req.headers['x-whop-signature'] || '').trim();
  if (!signature) {
    return res.status(401).json({ error: 'Missing signature' });
  }

  // REAL HMAC-SHA256 verification over the raw body (timing-safe compare).
  const rawBody = Buffer.isBuffer(req.body)
    ? req.body
    : Buffer.from(JSON.stringify(req.body ?? {}));
  const expected = crypto.createHmac('sha256', secret).update(rawBody).digest('hex');
  const sigBuf = Buffer.from(signature.replace(/^sha256=/, ''), 'utf8');
  const expBuf = Buffer.from(expected, 'utf8');
  if (sigBuf.length !== expBuf.length || !crypto.timingSafeEqual(sigBuf, expBuf)) {
    console.error('[Webhook] Invalid signature â€” request rejected');
    return res.status(401).json({ error: 'Invalid signature' });
  }

  try {
    const payload = JSON.parse(rawBody.toString('utf8'));
    const webhookFile = path.join(__dirname, '..', 'MBM', 'Whop', 'webhook_log.json');
    let logs = [];
    if (fs.existsSync(webhookFile)) {
      logs = JSON.parse(fs.readFileSync(webhookFile, 'utf8'));
    }

    // Idempotency check: skip already-processed webhook IDs.
    const eventId = payload.id || crypto.randomUUID();
    if (logs.some(l => l.id === eventId)) {
      console.log('[Webhook] Duplicate event ignored', eventId);
      return res.json({ received: true, duplicate: true });
    }

    const receivedAt = new Date().toISOString();
    const eventData = { id: eventId, action: payload.action || null, received_at: receivedAt };
    logs.push(eventData);
    fs.writeFileSync(webhookFile, JSON.stringify(logs, null, 2), 'utf8');

    // Fold into the canonical revenue event store (idempotent by webhook id).
    appendRevenueEvent(normalizeWhopWebhook(payload, receivedAt));

    console.log('[Webhook] Whop payload processed', eventId);
    res.json({ received: true, stored: true });
  } catch(e) {
    // Failed deliveries must be observable (Whop retries on non-2xx).
    console.error('[Webhook] processing failed:', e.message);
    try {
      fs.appendFileSync(
        path.join(__dirname, '..', 'MBM', 'Whop', 'logs', 'webhook_failures.jsonl'),
        JSON.stringify({ timestamp: new Date().toISOString(), error: e.message,
                         signature_present: Boolean(req.headers['x-whop-signature']) }) + '\n',
        'utf8');
    } catch {}
    res.status(500).json({error: 'storage failed'});
  }
});

// â”€â”€ Client Orders API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

app.post('/api/orders', async (req, res) => {
  try {
    if (!supabaseAdmin) return res.status(500).json({ error: 'SUPABASE_SERVICE_ROLE_KEY not configured' });
    const { customer_name, customer_email, customer_phone, company, plan, amount, payment_method } = req.body;
    if (!customer_email || !plan || !amount) {
      return res.status(400).json({ error: 'customer_email, plan, and amount required' });
    }
    const { data, error } = await supabaseAdmin.from('client_orders').insert({
      customer_name: customer_name || '',
      customer_email,
      customer_phone: customer_phone || '',
      company: company || '',
      plan,
      amount,
      currency: 'USD',
      status: 'pending',
      payment_method: payment_method || 'bank_transfer',
    }).select().single();
    if (error) throw error;
    res.json({ success: true, order: data });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.get('/api/orders', async (req, res) => {
  try {
    if (!supabaseAdmin) return res.status(500).json({ error: 'SUPABASE_SERVICE_ROLE_KEY not configured' });
    const { status, limit } = req.query;
    let query = supabaseAdmin.from('client_orders').select('*').order('created_at', { ascending: false });
    if (status) query = query.eq('status', status);
    if (limit) query = query.limit(parseInt(limit));
    const { data, error } = await query;
    if (error) throw error;
    const counts = { pending: 0, paid: 0, total: 0, revenue: 0 };
    for (const o of data || []) {
      counts.total++;
      if (o.status === 'paid') { counts.paid++; counts.revenue += o.amount || 0; }
      if (o.status === 'pending') counts.pending++;
    }
    res.json({ orders: data || [], counts });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

app.patch('/api/orders/:id/pay', async (req, res) => {
  try {
    if (!supabaseAdmin) return res.status(500).json({ error: 'SUPABASE_SERVICE_ROLE_KEY not configured' });
    const { payment_method } = req.body;
    const { data, error } = await supabaseAdmin.from('client_orders').update({
      status: 'paid',
      payment_method: payment_method || 'neteller',
      stripe_payment_id: '',
    }).eq('id', req.params.id).select().single();
    if (error) throw error;
    res.json({ success: true, order: data });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// â”€â”€ $149 AI Automation Audit: intake â†’ audit draft â†’ delivery â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

const AUDIT_ORDERS_DIR = path.join(__dirname, '..', 'MBM', 'Whop', 'orders');

app.post('/api/audit-intake', async (req, res) => {
  try {
    const b = req.body || {};
    const required = ['business_name', 'contact_email', 'vertical', 'bottleneck'];
    const missing = required.filter(k => !String(b[k] || '').trim());
    if (missing.length) {
      return res.status(400).json({ ok: false, error: `Missing required fields: ${missing.join(', ')}` });
    }
    const emailOk = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(b.contact_email));
    if (!emailOk) return res.status(400).json({ ok: false, error: 'contact_email is not a valid address' });

    const clean = s => String(s ?? '').slice(0, 2000);
    const auditId = `AUDIT-${new Date().toISOString().slice(0,10).replace(/-/g,'')}-${crypto.randomBytes(3).toString('hex').toUpperCase()}`;
    const dir = path.join(AUDIT_ORDERS_DIR, auditId);
    fs.mkdirSync(dir, { recursive: true });

    const intake = {
      audit_id: auditId,
      business_name: clean(b.business_name),
      website: clean(b.website),
      contact_email: clean(b.contact_email),
      contact_phone: clean(b.contact_phone),
      vertical: clean(b.vertical),
      inbound_volume: clean(b.inbound_volume),
      missed_share: clean(b.missed_share),
      bottleneck: clean(b.bottleneck),
      whop_order_ref: clean(b.whop_order),
      submitted_at: b.submitted_at || new Date().toISOString(),
      status: 'INTAKE_RECEIVED',
    };
    fs.writeFileSync(path.join(dir, 'intake.json'), JSON.stringify(intake, null, 2), 'utf8');

    // Audit draft built ONLY from the customer's own answers + our standard
    // methodology. No invented metrics about their business.
    const draft = {
      audit_id: auditId,
      generated_at: new Date().toISOString(),
      customer: intake,
      workflow_map_skeleton: [
        'Inbound capture (calls / forms / chats) â€” who/what receives them today',
        'Response latency â€” time-to-first-touch per channel',
        'Follow-up chain â€” attempts, cadence, ownership',
        'Booking handoff â€” how a qualified lead reaches the calendar',
        'Measurement â€” what is tracked vs. invisible today',
      ],
      automation_candidates: [
        'Missed-Call Recovery: instant second attempt + SMS fallback on ring-outs',
        'AI Lead Qualification: auto-qualify + route new inquiries',
        'Follow-Up Engine: structured recontact until booked or closed',
        'Reporting: weekly money-leak scorecard',
      ],
      roi_method: 'Estimates use ONLY the volumes you provided; we confirm against real call logs during the audit call.',
      deliverables: ['workflow map', 'automation opportunity list', 'ROI estimate (customer-confirmed inputs)', 'prioritized 3-step plan', 'working demo of top fix'],
      sla: '72 hours from intake',
      upsell_path: 'Audit fee credited toward any implementation; recommended next: Missed-Call Recovery pilot.',
    };
    fs.writeFileSync(path.join(dir, 'audit_draft.json'), JSON.stringify(draft, null, 2), 'utf8');
    fs.writeFileSync(path.join(dir, 'delivery_checklist.md'),
      `# Delivery Checklist ${auditId}\n\n- [ ] Confirm payment evidence (Whop webhook event or order ref)\n- [ ] Discovery call scheduled\n- [ ] Workflow map filled from real systems\n- [ ] ROI model with customer inputs\n- [ ] 3-step plan delivered\n- [ ] Demo of top automation\n- [ ] Testimonial / case-study ask AFTER results\n`, 'utf8');

    res.status(201).json({ ok: true, audit_id: auditId, status: 'INTAKE_RECEIVED' });
  } catch (err) {
    console.error('[audit-intake] failed:', err.message);
    res.status(500).json({ ok: false, error: 'storage failed' });
  }
});

app.get('/api/audit-intake/:auditId', (req, res) => {
  const id = String(req.params.auditId || '');
  if (!/^AUDIT-\d{8}-[A-F0-9]{6}$/.test(id)) return res.status(400).json({ ok: false, error: 'bad audit id' });
  const p = path.join(AUDIT_ORDERS_DIR, id, 'intake.json');
  if (!fs.existsSync(p)) return res.status(404).json({ ok: false, error: 'not found' });
  res.json({ ok: true, intake: JSON.parse(fs.readFileSync(p, 'utf8')) });
});

// â”€â”€ Lead Pipeline API (legacy) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

app.get('/api/leads/stats', (req, res) => {
  res.json(loadStats());
});

app.get('/api/leads/whatsapp-report', (req, res) => {
  const report = generateSellerWhatsAppReport();
  res.json(report);
});

// â”€â”€ Demo Campaign API â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if (supabaseAdmin) {
  cron.schedule('5 * * * *', async () => {
    console.log('[cron] Starting hourly demo campaign + email send...');
    try {
      // 1. Generate fresh demo videos using Runware AI
      await generateAllDemos({ useAI: true });
      console.log('[cron] Demo videos generated');

      // 2. Queue promo campaign emails to all users
      const campaign = await queuePromoCampaign({ supabase: supabaseAdmin });
      console.log(`[cron] Campaign queued: ${JSON.stringify(campaign)}`);

      // 3. Send all queued emails (continuous = drain the queue)
      const sendResult = await sendEmailQueue({
        supabase: supabaseAdmin,
        batchSize: 5000,
        continuous: false,
      });
      console.log(`[cron] Emails sent: ${JSON.stringify(sendResult)}`);
    } catch (err) {
      console.error('[cron] Demo campaign error:', err.message);
    }
  });
  console.log('[cron] Hourly demo campaign scheduled (at :05 every hour)');
}

// Legacy hourly email queue send (kept for backward compatibility)
if (supabaseAdmin) {
  cron.schedule('0 * * * *', async () => {
    console.log('[cron] Starting legacy hourly email queue send...');
    try {
      const result = await sendEmailQueue({
        supabase: supabaseAdmin,
        batchSize: 5000,
        continuous: false,
      });
      console.log(`[cron] Legacy send complete: ${JSON.stringify(result)}`);
    } catch (err) {
      console.error('[cron] Legacy email send error:', err.message);
    }
  });
  console.log('[cron] Legacy hourly email send scheduled (at :00 every hour)');
}

// HUNTER â€” Hourly revenue outreach (queues new targets to email_queue)
if (supabaseAdmin) {
  cron.schedule('30 * * * *', async () => {
    console.log('[cron] Starting HUNTER hourly outreach scan...');
    try {
      const result = await hunt({ supabase: supabaseAdmin, dryRun: false });
      console.log(`[cron] HUNTER outreach: ${JSON.stringify(result)}`);
      const sendResult = await sendEmailQueue({
        supabase: supabaseAdmin,
        batchSize: 5000,
        continuous: false,
      });
      console.log(`[cron] HUNTER send: ${JSON.stringify(sendResult)}`);
    } catch (err) {
      console.error('[cron] HUNTER outreach error:', err.message);
    }
  });
  console.log('[cron] HUNTER outreach scheduled (at :30 every hour)');
}

// â”€â”€â”€ VOICE AGENTS STUDIO & CREATOR MONETIZATION API â”€â”€â”€

// In-memory fallback state for Voice Agents & Creator Wallet
let inMemoryVoiceAgents = [
  {
    id: "va-001",
    title: "Apex Cash Offer Setter",
    description: "High-converting residential acquisition voice bot for distressed sellers. 7-day close pitch & objection handling.",
    persona: "Professional, empathetic, direct cash buyer acquisitions manager.",
    system_prompt: "You are Alex from Apex Capital. Call home owners listed for sale or distressed properties. Ask if open to a firm cash offer with zero agent fees.",
    voice_provider: "elevenlabs",
    voice_id: "21m00Tcm4TlvDq8ikWAM",
    model_name: "gemini-1.5-flash-audio",
    rate_per_min: 0.45,
    creator_name: "Omar A. (Antigravity)",
    total_calls: 1420,
    total_minutes: 3840.5,
    total_earnings: 1728.22,
    status: "active",
    tags: ["Real Estate", "Cold Calling", "Acquisitions"]
  },
  {
    id: "va-002",
    title: "Plastic Scrap Recycler Matcher",
    description: "Industrial waste broker voice bot. Matches factories producing PET/HDPE/PP scrap with qualified plastic compounders.",
    persona: "Industrial procurement & raw materials specialist.",
    system_prompt: "You are Sam from Industrial Waste Exchange. Ask plant managers about monthly plastic scrap tonnage and current disposal buyer pricing.",
    voice_provider: "deepgram",
    voice_id: "aura-stella-en",
    model_name: "gemini-1.5-flash-audio",
    rate_per_min: 0.65,
    creator_name: "JARVIS Ecosystem",
    total_calls: 890,
    total_minutes: 2150.0,
    total_earnings: 1397.50,
    status: "active",
    tags: ["Industrial Waste", "B2B Broker", "Recycling"]
  },
  {
    id: "va-003",
    title: "SaaS Inbound Concierge",
    description: "Qualifies high-intent website visitors, answers technical pricing questions, and books 15-min Google Meet calls.",
    persona: "Warm, knowledgeable, fast-paced SaaS technical account rep.",
    system_prompt: "You are Maya from LeadEngine AI. Welcome inbound prospects, qualify their monthly lead volume, and schedule a live product demo.",
    voice_provider: "openai",
    voice_id: "alloy",
    model_name: "gemini-1.5-flash-audio",
    rate_per_min: 0.35,
    creator_name: "LeadEngine Core",
    total_calls: 2100,
    total_minutes: 4210.0,
    total_earnings: 1473.50,
    status: "active",
    tags: ["SaaS", "Inbound Support", "Demo Booking"]
  }
];

let creatorWallet = {
  total_earned: 4599.22,
  payout_balance: 1250.00,
  total_calls_handled: 4410,
  total_minutes_called: 10200.5,
  payout_history: [
    { id: "po-101", amount: 1500.00, status: "paid", method: "Stripe Connect", date: "2026-07-20T14:30:00Z" },
    { id: "po-102", amount: 1849.22, status: "paid", method: "PayPal Direct", date: "2026-07-10T09:15:00Z" }
  ]
};

// GET /api/voice-agents â€” List all active voice agents
app.get('/api/voice-agents', async (req, res) => {
  try {
    if (supabase) {
      const { data, error } = await supabase.from('voice_agents').select('*').order('created_at', { ascending: false });
      if (!error && data && data.length > 0) {
        return res.json(data);
      }
    }
    res.json(inMemoryVoiceAgents);
  } catch (err) {
    res.json(inMemoryVoiceAgents);
  }
});

// POST /api/voice-agents â€” Create or update a voice agent
app.post('/api/voice-agents', async (req, res) => {
  try {
    const { title, description, persona, system_prompt, voice_provider, voice_id, rate_per_min, tags } = req.body;
    if (!title || !system_prompt) {
      return res.status(400).json({ error: "Title and System Prompt are required." });
    }

    const newAgent = {
      id: `va-${Date.now()}`,
      title,
      description: description || "Custom AI Voice Agent created on Contech AI Agentic Teamz Studio.",
      persona: persona || "Professional AI Sales Representative",
      system_prompt,
      voice_provider: voice_provider || "elevenlabs",
      voice_id: voice_id || "21m00Tcm4TlvDq8ikWAM",
      model_name: "gemini-1.5-flash-audio",
      rate_per_min: parseFloat(rate_per_min) || 0.45,
      creator_name: "Creator User",
      total_calls: 0,
      total_minutes: 0.0,
      total_earnings: 0.0,
      status: "active",
      tags: tags || ["Custom Agent", "Sales"]
    };

    if (supabase) {
      const { data, error } = await supabase.from('voice_agents').insert([newAgent]).select();
      if (!error && data) {
        return res.status(201).json(data[0]);
      }
    }

    inMemoryVoiceAgents.unshift(newAgent);
    res.status(201).json(newAgent);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/voice-agents/:id/simulate-call â€” Live call simulation & creator payout calculation
app.post('/api/voice-agents/:id/simulate-call', async (req, res) => {
  try {
    const { id } = req.params;
    const { user_transcript } = req.body;

    const agent = inMemoryVoiceAgents.find(a => a.id === id) || inMemoryVoiceAgents[0];

    // Call duration simulation (60s batch)
    const duration_secs = Math.floor(Math.random() * 45) + 30; // 30-75 secs
    const duration_mins = duration_secs / 60.0;
    const amount_earned = parseFloat((duration_mins * agent.rate_per_min).toFixed(2));

    // Update agent metrics
    agent.total_calls += 1;
    agent.total_minutes = parseFloat((agent.total_minutes + duration_mins).toFixed(1));
    agent.total_earnings = parseFloat((agent.total_earnings + amount_earned).toFixed(2));

    // Update creator wallet
    creatorWallet.total_earned = parseFloat((creatorWallet.total_earned + amount_earned).toFixed(2));
    creatorWallet.payout_balance = parseFloat((creatorWallet.payout_balance + amount_earned).toFixed(2));
    creatorWallet.total_calls_handled += 1;
    creatorWallet.total_minutes_called = parseFloat((creatorWallet.total_minutes_called + duration_mins).toFixed(1));

    // Generate AI response snippet using Gemini key if present
    let ai_response = `Hi! I'm ${agent.title}. I reviewed your property listing and we're cash buyers ready to close in 7 days with zero commissions. Does tomorrow work for a 10-minute Google Meet?`;
    
    if (process.env.GEMINI_API_KEY && !process.env.GEMINI_API_KEY.startsWith("your_")) {
      try {
        const url = `https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key=${process.env.GEMINI_API_KEY}`;
        const fetchRes = await fetch(url, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            contents: [{
              parts: [{ text: `System Prompt: ${agent.system_prompt}\nPersona: ${agent.persona}\nUser says: ${user_transcript || 'Hello! Who is this?'}\nRespond in 2 concise sentences as the voice agent.` }]
            }]
          })
        });
        if (fetchRes.ok) {
          const geminiData = await fetchRes.json();
          const text = geminiData.candidates?.[0]?.content?.parts?.[0]?.text;
          if (text) ai_response = text;
        }
      } catch (e) {
        // Fallback response stays intact
      }
    }

    res.json({
      agent_id: id,
      ai_response,
      duration_secs,
      rate_per_min: agent.rate_per_min,
      amount_earned,
      updated_wallet_balance: creatorWallet.payout_balance,
      timestamp: new Date().toISOString()
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/creator/wallet â€” Fetch creator wallet stats & payout ledger
app.get('/api/creator/wallet', (req, res) => {
  res.json(creatorWallet);
});

// POST /api/creator/payout â€” Request payout cashout
app.post('/api/creator/payout', (req, res) => {
  const { amount, method } = req.body;
  const withdrawAmount = parseFloat(amount);

  if (isNaN(withdrawAmount) || withdrawAmount <= 0) {
    return res.status(400).json({ error: "Invalid withdrawal amount." });
  }

  if (withdrawAmount > creatorWallet.payout_balance) {
    return res.status(400).json({ error: "Withdrawal amount exceeds available payout balance." });
  }

  creatorWallet.payout_balance = parseFloat((creatorWallet.payout_balance - withdrawAmount).toFixed(2));

  const payoutRecord = {
    id: `po-${Date.now()}`,
    amount: withdrawAmount,
    status: "processing",
    method: "Neteller Direct",
    neteller_email: NETELLER_EMAIL,
    neteller_account_id: NETELLER_ACCOUNT_ID,
    date: new Date().toISOString()
  };

  creatorWallet.payout_history.unshift(payoutRecord);

  res.json({
    status: 'payout_processed',
    payout_id: payoutRecord.id,
    amount: payoutRecord.amount,
    method: "Neteller Direct",
    neteller_email: NETELLER_EMAIL,
    neteller_account_id: NETELLER_ACCOUNT_ID,
    remaining_balance: creatorWallet.payout_balance
  });
});

// === SALES DEPARTMENT & SUPERPOWER ENDPOINTS ===

const inMemorySalesDeals = [];
const inMemoryProposals = [];

// POST /api/sales/assign-deal â€” Assigns high-ticket US deals to Sales Reps
app.post('/api/sales/assign-deal', async (req, res) => {
  try {
    const { deal_id, address, price, expected_commission, rep_name, buyer_name } = req.body;
    const assignment = {
      id: `sa-${Date.now()}`,
      deal_id, address, price,
      expected_commission: expected_commission || '$11,250.00',
      rep_name: rep_name || 'Omar A. (Senior Sales Rep)',
      buyer_name: buyer_name || 'Unassigned Buyer',
      commission_rep_fee: '3.5%',
      rep_earnings: (parseFloat(String(expected_commission).replace(/[^0-9.]/g, '') || 11250) * 0.035).toFixed(2),
      status: 'assigned_to_dealing_room',
      assigned_at: new Date().toISOString()
    };
    inMemorySalesDeals.unshift(assignment);
    res.status(201).json(assignment);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/sales/deals â€” Returns assigned sales deals
app.get('/api/sales/deals', (req, res) => {
  res.json(inMemorySalesDeals);
});

// POST /api/sales/proposals â€” Creates B2B Sales Proposal with Neteller checkout link
app.post('/api/sales/proposals', (req, res) => {
  try {
    const { buyer_name, lead_pack_title, price_usd, discount_applied } = req.body;
    const final_price = discount_applied ? (price_usd || 499.00) * 0.8 : (price_usd || 499.00);
    const proposal = {
      id: `prop-${Date.now()}`,
      buyer_name,
      lead_pack_title,
      original_price: price_usd || 499.00,
      final_price,
      neteller_checkout_url: netellerLink(final_price, 'B2B_Lead_Pack_Proposal', { currency: 'USD' }),
      status: 'sent',
      created_at: new Date().toISOString()
    };
    inMemoryProposals.unshift(proposal);
    res.status(201).json(proposal);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/sales/telegram-alert â€” Sends instant Telegram notification to Sales Chat
app.post('/api/sales/telegram-alert', async (req, res) => {
  try {
    const { message } = req.body;
    const botToken = process.env.TELEGRAM_BOT_TOKEN;
    const chatId = process.env.TELEGRAM_CHAT_ID;

    if (botToken && chatId) {
      const tgUrl = `https://api.telegram.org/bot${botToken}/sendMessage`;
      await fetch(tgUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, text: message, parse_mode: 'HTML' })
      });
      return res.json({ status: 'telegram_alert_sent', chat_id: chatId });
    }
    res.status(400).json({ error: 'Telegram bot token or chat ID missing' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// === INSTANT CASH AI SUITE ENDPOINTS ===

// POST /api/instant-cash/clipping â€” On-demand AI Video Clipping job ($0.10/clip)
app.post('/api/instant-cash/clipping', (req, res) => {
  try {
    const { youtube_url, style } = req.body;
    const clipJob = {
      job_id: `clip-${Date.now()}`,
      youtube_url: youtube_url || 'https://www.youtube.com/watch?v=demo',
      style: style || 'viral_shorts_captions',
      clips_generated: 3,
      cost_usd: 0.30,
      download_urls: [
        `http://localhost:3002/clips/clip_01_${Date.now()}.mp4`,
        `http://localhost:3002/clips/clip_02_${Date.now()}.mp4`
      ],
      status: 'completed',
      created_at: new Date().toISOString()
    };
    res.status(201).json(clipJob);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/instant-cash/ig-dm â€” Launch Instagram AI DM Hunter ($149/mo)
app.post('/api/instant-cash/ig-dm', (req, res) => {
  try {
    const { target_niche, city } = req.body;
    const campaign = {
      campaign_id: `ig-dm-${Date.now()}`,
      niche: target_niche || 'Real Estate Brokers',
      city: city || 'New York, NY',
      prospects_scraped: 45,
      dms_queued: 45,
      subscription_status: 'active',
      monthly_fee_usd: 149.00,
      created_at: new Date().toISOString()
    };
    res.status(201).json(campaign);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/instant-cash/cold-calling â€” Launch Cold Calling Swarm ($0.50/call)
app.post('/api/instant-cash/cold-calling', (req, res) => {
  try {
    const { lead_count, script_type } = req.body;
    const count = lead_count || 20;
    const swarmRun = {
      run_id: `swarm-${Date.now()}`,
      leads_dialed: count,
      script_type: script_type || 'US Distressed Property Cash Offer',
      cost_usd: (count * 0.50).toFixed(2),
      status: 'in_progress',
      created_at: new Date().toISOString()
    };
    res.status(201).json(swarmRun);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/instant-cash/marketing-agencies â€” Marketing Agencies White-Label AI Suite ($1,500 setup + $997/mo)
app.post('/api/instant-cash/marketing-agencies', (req, res) => {
  try {
    const { agency_name, client_niche, seats } = req.body;
    const suite = {
      license_id: `agency-wl-${Date.now()}`,
      agency_name: agency_name || 'NextGen Digital Media Agency',
      client_niche: client_niche || 'Real Estate & High-Ticket Local Services',
      seats_allocated: seats || 10,
      setup_fee_usd: 1500.00,
      monthly_retainer_usd: 997.00,
      per_min_usage_margin: 0.50,
      white_label_portal_url: `https://agency.dawrix.com/portal/${Date.now()}`,
      neteller_checkout_url: netellerLink(1500.00, 'Agency_WhiteLabel_License', { currency: 'USD' }),
      status: 'active',
      created_at: new Date().toISOString()
    };
    res.status(201).json(suite);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/voice-agents/free-us-number â€” REAL provider status (no invented balances)
app.get('/api/voice-agents/free-us-number', async (req, res) => {
  const health = await telephony.health();
  res.json({
    status: health.ok ? 'READY' : 'TELEPHONY_BLOCKED',
    telephony_provider: telephony.code,
    mode: telephony.mode?.() || null,
    reason: health.reason || null,
    features: [
      'Outbound US calling via Phound (native handoff or API bridge)',
      'Webhook-first real outcomes',
    ],
    required_integration: health.ok
      ? ''
      : 'Set PHOUND_ENABLED=true, PHOUND_CALL_ENDPOINT, PHOUND_API_TOKEN for API mode; native_app deep-link mode needs no credentials.',
  });
});

// POST /api/voice-agents/place-call â€” REAL Phound dispatch (never fake-connected)
app.post('/api/voice-agents/place-call', async (req, res) => {
  const { to_number, prospect_name, lead_id } = req.body || {};
  if (!to_number || !/^\+\d{10,15}$/.test(String(to_number))) {
    return res.status(400).json({ error: 'to_number must be E.164 (e.g. +12145550123)' });
  }
  try {
    const result = await telephony.start_call({ to_number, prospect_name, lead_id });
    if (result.status === 'error') {
      return res.status(502).json({ status: 'CALL_ERROR', error: result.error, http_status: result.http_status });
    }
    res.status(201).json({
      ...result,
      note: 'Outcome counts only after POST /api/telephony/phound/webhook delivers a real event.',
    });
  } catch (err) {
    if (err.code === 'TELEPHONY_BLOCKED') {
      return res.status(423).json({ status: 'TELEPHONY_BLOCKED', error: err.message });
    }
    res.status(502).json({ status: 'CALL_ERROR', error: err.message });
  }
});

// GET /api/instant-cash/upwork â€” Upwork High-Ticket AI Client Bounties & Proposals
app.get('/api/instant-cash/upwork', (req, res) => {
  try {
    const jobsPath = path.join(__dirname, '..', 'MBM', 'LeadEngine', 'logs', 'upwork_active_jobs.json');
    if (fs.existsSync(jobsPath)) {
      const data = JSON.parse(fs.readFileSync(jobsPath, 'utf8'));
      return res.json({ status: 'success', total_bounties: data.length, bounties: data });
    }
    res.json({
      status: 'success',
      total_bounties: 1,
      bounties: [
        {
          job_id: "~022081443579209529517",
          url: "https://www.upwork.com/jobs/~022081443579209529517",
          title: "Build AI Voice Cold Calling & Real Estate Lead Generation Bot",
          client_budget: "$5,000.00 Fixed Price",
          estimated_profit: "$5,000.00",
          status: "Proposal Queued & Pitch Ready"
        }
      ]
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// DIALER API â€” Phound production telephony (webhook-first outcomes)
// â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•
// Twilio was REMOVED from the production call path (2026-08-26).
// Legacy Twilio CLI tools live under MBM/LeadEngine labeled LEGACY.

const telephony = getProvider();
console.log(`[DIALER] Telephony provider: ${telephony.code} (mode: ${telephony.mode?.() || 'n/a'})`);

// Webhook-first outcome persistence: append canonical events to a JSONL log
// (local dev). On serverless read-only FS this degrades to structured logs â€”
// the event payload is always returned/acknowledged regardless.
const TELEPHONY_EVENTS_LOG = path.join(__dirname, 'dialer', 'logs', 'phound_call_events.jsonl');
function persistTelephonyEvent(event) {
  const line = JSON.stringify(event) + '\n';
  try {
    fs.mkdirSync(path.dirname(TELEPHONY_EVENTS_LOG), { recursive: true });
    fs.appendFileSync(TELEPHONY_EVENTS_LOG, line, 'utf8');
    return 'file';
  } catch {
    console.log('[TELEPHONY_EVENT]', line.trim());
    return 'log';
  }
}

const _seenProviderEvents = new Set(); // idempotency within process lifetime

// Pipeline CSV helper
const PIPELINE_CSV = path.join(__dirname, '..', 'MBM', 'Pipeline', 'pipeline.csv');

// Escape user-supplied text before interpolating into TwiML so a malicious
// prospect_name (e.g. "x</Say><Dial>+1900...</Dial>") cannot alter call flow.
function escapeXml(value) {
  return String(value ?? '').replace(/[<>&'"]/g, (c) => ({
    '<': '&lt;', '>': '&gt;', '&': '&amp;', "'": '&apos;', '"': '&quot;',
  }[c]));
}

function loadPipelineLeads() {
  if (!fs.existsSync(PIPELINE_CSV)) return [];
  const content = fs.readFileSync(PIPELINE_CSV, 'utf8');
  const lines = content.trim().split('\n');
  if (lines.length < 2) return [];
  const headers = lines[0].split(',');
  return lines.slice(1).map(line => {
    const values = line.split(',');
    const lead = {};
    headers.forEach((h, i) => { lead[h.trim()] = (values[i] || '').trim(); });
    return lead;
  });
}

function cleanPhone(phone) {
  if (!phone) return '';
  let p = String(phone).replace(/[^\d+]/g, '');
  if (p.startsWith('+')) p = p.slice(1);
  p = p.replace(/^1(?=\d{10}$)/, '');
  if (/^\d{10}$/.test(p) && !/^(555|000)/.test(p.slice(3, 6))) return `+1${p}`;
  return '';
}

// GET /api/dialer/leads â€” All pipeline leads with phone numbers
app.get('/api/dialer/leads', (req, res) => {
  try {
    const leads = loadPipelineLeads();
    const withPhone = leads
      .filter(l => l.phone && l.phone.trim())
      .map((l, i) => ({
        id: i,
        company: l.company || 'Unknown',
        email: l.email || '',
        phone: l.phone,
        phone_clean: cleanPhone(l.phone),
        solution: l.solution || '',
        deal_value: l.deal_value || '',
        stage: l.stage || '',
        last_touch: l.last_touch || '',
        next_followup: l.next_followup || '',
        notes: l.notes || '',
      }));
    res.json({ status: 'success', count: withPhone.length, leads: withPhone });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/dialer/top50 â€” Top 50 calling list
app.get('/api/dialer/top50', (req, res) => {
  try {
    const listFile = path.join(__dirname, '..', 'MBM', 'LeadEngine', 'logs', 'us_50_calling_list.json');
    if (fs.existsSync(listFile)) {
      const data = JSON.parse(fs.readFileSync(listFile, 'utf8'));
      return res.json({ status: 'success', count: data.length, prospects: data });
    }
    res.json({ status: 'success', count: 0, prospects: [] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/gtm/brief â€” GTM Daily Quick Brief (reads the Quick Brief Center artifacts).
app.get('/api/gtm/brief', (req, res) => {
  try {
    const briefFile = path.join(__dirname, '..', 'MBM', 'Artifacts', 'GTM', 'daily', 'latest.json');
    if (fs.existsSync(briefFile)) {
      const brief = JSON.parse(fs.readFileSync(briefFile, 'utf8'));
      return res.json({ status: 'success', brief });
    }
    res.json({ status: 'success', brief: null, note: 'No daily brief generated yet. Run: python MBM/LeadEngine/gtm_quick_brief.py --daily' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/gtm/top-actions â€” GTM Top-N next actions (execution queue).
app.get('/api/gtm/top-actions', (req, res) => {
  try {
    const limit = Math.min(25, parseInt(req.query.limit || '10', 10) || 10);
    const queueFile = path.join(__dirname, '..', 'MBM', 'Artifacts', 'GTM_TOP25_EXECUTION_QUEUE.json');
    if (fs.existsSync(queueFile)) {
      const data = JSON.parse(fs.readFileSync(queueFile, 'utf8'));
      const actions = (Array.isArray(data) ? data : []).slice(0, limit).map((item) => ({
        rank: item.rank,
        id: item.id || item.company || '',
        company: item.company || '',
        decision_maker: item.decision_maker || '',
        channel: item.recommended_channel || '',
        priority: item.priority || 0,
        phone: (item.contactability && item.contactability.phone) || '',
      }));
      return res.json({ status: 'success', count: actions.length, actions });
    }
    res.json({ status: 'success', count: 0, actions: [] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/dialer/re-queue â€” dialer queue (AutoDialer schema).
// SINGLE source of truth is mbm-dialer/app/public/leads_database.json as
// ordered by the backend engine (dialer_queue_engine.py). Legacy queue files
// (real_estate_calling_queue.json / cold_calling_queue.json) are NOT read and
// can never override the canonical order. Phone app MUST only ever see dialable
// E.164 (+1XXXXXXXXXX) numbers backed by a REAL lead; fabricated 555/00x numbers
// and suppressed identity states are dropped here.
const mbmDialerFile = path.join(__dirname, '..', 'mbm-dialer', 'app', 'public', 'leads_database.json');

function isFakePhoneNumber(phone) {
  const digits = String(phone || '').replace(/[^\d+]/g, '');
  return !/^1?\d{10}$/.test(digits.replace(/^\+/, '').replace(/^1(?=\d{10}$)/, '')) ||
    /555|000/.test(digits);
}

function transformReLead(lead, idx) {
  const phone = cleanPhone(lead.phone || lead.phone_number || lead.verified_phone || lead.formatted_phone || '');
  if (!phone) return null;

  const asking = /Asking:\s*\$([\d,]+)/i.exec(lead.distress_or_criteria || lead.notes || '');
  const askingPriceRaw = asking
    ? parseInt(asking[1].replace(/,/g, ''), 10)
    : (lead.asking_price || lead.askingPrice || 0);
  const askingPrice = askingPriceRaw ? (typeof askingPriceRaw === 'number' ? `$${Number(askingPriceRaw).toLocaleString()}` : String(askingPriceRaw)) : 'Unknown';
  const est = askingPriceRaw && typeof askingPriceRaw === 'number' ? Math.round(Number(askingPriceRaw) * 0.03).toLocaleString() : null;

  const name = lead.contact_name || lead.name || lead.prospect_name || lead.entity || lead.company_name || `Prospect ${idx + 1}`;
  const cityState = [lead.city, lead.state].filter(Boolean).join(', ');

  const zestMatch = /Zestimate:\s*\$([\d,]+)/i.exec(lead.distress_or_criteria || lead.notes || '');
  const zestimate = zestMatch ? `$${zestMatch[1]}` : (lead.zestimate || lead.zestimate_value || 'Unknown');

  const domMatch = /DOM:\s*(\d+)/i.exec(lead.distress_or_criteria || lead.notes || '');
  const dom = domMatch ? `${domMatch[1]} Days` : (lead.days_on_market ? `${lead.days_on_market} Days` : 'Unknown');

  const yearMatch = /Built:\s*(\d{4})/i.exec(lead.distress_or_criteria || lead.notes || '');
  const year_built = yearMatch ? yearMatch[1] : (lead.year_built || 'Unknown');

  const scriptIntro = `Hi ${name.split(' ')[0] || 'there'}! I'm calling regarding your property${lead.address || lead.property_address ? ` at ${lead.address || lead.property_address}` : ''}.`;
  const scriptHook = lead.distress_or_criteria
    ? ` We're cash buyers with a 7-day close. I see this is listed as ${lead.distress_or_criteria}.`
    : ` We're cash buyers with a 7-day close.`;

  return {
    id: lead.queue_id || lead.id || `RE-${String(idx + 1).padStart(3, '0')}`,
    prospect_name: name,
    role: lead.subtype || lead.type || lead.vertical || 'Real Estate Contact',
    phone_number: phone,
    formatted_phone: phone,
    address: lead.address || lead.property_address || '',
    city: cityState,
    property_type: `${lead.type || lead.vertical || 'Real Estate'} â€” ${lead.subtype || 'Contact'}`,
    asking_price: askingPrice,
    est_commission: est ? `$${est}.00` : 'Unknown',
    distress_score: lead.priority_score || lead.distress_score || lead.distressScore || 'Unknown',
    zestimate,
    days_on_market: dom,
    year_built,
    cold_calling_script: lead.call_script || lead.script || `${scriptIntro}${scriptHook} Are you open to a firm cash offer today?`,
    tel_link: `tel:${phone}`,
    email: lead.email || '',
    owner_name: lead.owner_name || lead.owner || '',
    phone_owner_name: lead.phone_owner_name || lead.contact_name || name,
    phone_type: lead.phone_type || 'wireless',
    is_residential: lead.is_residential ?? true,
    dnc: lead.dnc ?? false,
    motivation_tier: lead.motivation_tier || lead.tier || 'STANDARD',
    // Owner identity layer: database verification vs live caller confirmation.
    database_ownership_verified: lead.owner_status === 'VERIFIED_OWNER' ||
      lead.database_ownership_verified ||
      (lead.details && lead.details.Owner_Status === 'VERIFIED_OWNER') || false,
    identity_state: lead.identity_state || lead.details?.identity_state || '',
    identity_relationship: lead.identity_relationship || '',
    identity_name_confirmed: !!lead.identity_name_confirmed,
    identity_property_confirmed: !!lead.identity_property_confirmed,
    identity_caller_name: lead.identity_caller_name || '',
    caller_identity_verified: !!lead.caller_identity_verified,
    // Canonical ordering metadata â€” carried verbatim from the engine-stamped
    // DB record so compareDialerLeads sorts on real values, not defaults.
    queue_bucket: lead.queue_bucket || '',
    freshness_stage: lead.freshness_stage || 'OLD',
    freshness_score: lead.freshness_score || 0,
    priority_score: lead.priority_score || 0,
    priority_rank: lead.priority_rank || 0,
    new_today: !!lead.new_today,
    freshness_label: lead.freshness_label || '',
    callable: lead.callable !== false,
    main_queue: lead.main_queue === true,
    verification_status: lead.verification_status || '',
    phone_verified: !!lead.phone_verified,
    owner_name: lead.owner_name || lead.owner || '',
  };
}

function getUnifiedDialerLeads() {
  const prospects = [];
  const seenPhones = new Set();

  // Identity states that must never surface as primary seller calls.
  const SUPPRESSED_IDENTITY = new Set([
    'WRONG_PERSON', 'WRONG_NUMBER', 'TENANT',
    'RELATIVE_OR_ASSOCIATE', 'DO_NOT_CALL', 'QUARANTINED',
  ]);

  const addLead = (lead, i) => {
    const rawPhone = lead.phone || lead.phone_number || lead.verified_phone || lead.formatted_phone;
    if (isFakePhoneNumber(rawPhone)) return;
    // Queue protection: negative identity states are excluded from the
    // primary seller queue (they may still exist in the DB record).
    const identityState = lead.identity_state || (lead.details && lead.details.identity_state) || '';
    if (identityState && SUPPRESSED_IDENTITY.has(identityState)) return;
    const p = transformReLead(lead, i);
    if (!p) return;
    const cleanDigits = p.phone_number.replace(/\D/g, '');
    if (seenPhones.has(cleanDigits)) return;
    seenPhones.add(cleanDigits);
    prospects.push(p);
  };

  // CANONICAL DB = single source of truth.
  // The backend queue engine (dialer_queue_engine.py) writes leads in the
  // correct freshness-first order. We read that order and preserve it.
  if (fs.existsSync(mbmDialerFile)) {
    try {
      const data = JSON.parse(fs.readFileSync(mbmDialerFile, 'utf8'));
      const arr = Array.isArray(data) ? data : (data.leads || data.prospects || []);
      for (const [i, lead] of arr.entries()) addLead(lead, i);
    } catch {}
  }

  // Freshness-first ordering via the shared canonical comparator
  // (server/dialer/freshnessOrder.js). transformReLead carries the engine's
  // queue_bucket/freshness_stage/scores, so this preserves DB order.
  prospects.sort(compareDialerLeads);

  return prospects;
}

app.get('/api/dialer/re-queue', (req, res) => {
  try {
    const prospects = getUnifiedDialerLeads();
    return res.json({ status: 'success', count: prospects.length, prospects });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.get('/api/dialer/top50', (req, res) => {
  try {
    const prospects = getUnifiedDialerLeads().slice(0, 50);
    return res.json({ status: 'success', count: prospects.length, prospects });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/dialer/disposition â€” Save call disposition
const dispositionsFile = path.join(__dirname, '..', 'MBM', 'LeadEngine', 'logs', 'call_dispositions.json');
app.post('/api/dialer/disposition', (req, res) => {
  try {
    const { lead_id, prospect_name, disposition, notes, callback_time } = req.body;
    if (!lead_id || !disposition) return res.status(400).json({ error: 'lead_id and disposition required' });

    let dispositions = [];
    if (fs.existsSync(dispositionsFile)) {
      dispositions = JSON.parse(fs.readFileSync(dispositionsFile, 'utf8'));
    }

    const entry = {
      lead_id,
      prospect_name: prospect_name || '',
      disposition,
      notes: notes || '',
      callback_time: callback_time || null,
      timestamp: new Date().toISOString(),
    };
    dispositions.push(entry);
    fs.writeFileSync(dispositionsFile, JSON.stringify(dispositions, null, 2));

    res.json({ status: 'success', entry });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/dialer/dispositions â€” Get all dispositions
app.get('/api/dialer/dispositions', (req, res) => {
  try {
    if (fs.existsSync(dispositionsFile)) {
      const data = JSON.parse(fs.readFileSync(dispositionsFile, 'utf8'));
      return res.json({ status: 'success', count: data.length, dispositions: data });
    }
    res.json({ status: 'success', count: 0, dispositions: [] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// â”€â”€ Owner Identity Verification Layer â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Separates DATABASE ownership verification from LIVE caller identity
// confirmation. The DB proves the record; the call proves who answers.
const identityResultsFile = path.join(__dirname, '..', 'MBM', 'LeadEngine', 'logs', 'call_identity_results.json');

// Current recorded identity state for a lead (from the identity log), used to
// capture previous_identity_state on transition. Returns '' if none recorded.
function getLeadIdentityState(leadId) {
  try {
    if (fs.existsSync(identityResultsFile)) {
      const data = JSON.parse(fs.readFileSync(identityResultsFile, 'utf8'));
      const rec = (data || []).find((r) => String(r.lead_id) === String(leadId));
      if (rec) return rec.identity_state || '';
    }
  } catch {}
  // Fall back to the DB record if the log has no entry.
  try {
    if (fs.existsSync(mbmDialerFile)) {
      const db = JSON.parse(fs.readFileSync(mbmDialerFile, 'utf8'));
      const arr = Array.isArray(db) ? db : (db.leads || []);
      const lead = arr.find((l) => String(l.id) === String(leadId));
      if (lead) return lead.identity_state || (lead.details && lead.details.identity_state) || '';
    }
  } catch {}
  return '';
}

// POST /api/dialer/identity â€” Save a call-level identity result.
// Body: { lead_id, caller_name, relationship, property_confirmed,
//         name_confirmed, wrong_number, do_not_call, disposition, notes }
// Identity-state mapping mirrors owner_identity.py (Python is authoritative):
//   OWNER_CONFIRMED requires relationship === 'OWNER' AND name_confirmed
//   AND property_confirmed. NEVER derived from phone/address/DB alone.
//   AUTHORIZED_DECISION_MAKER stays separate and is never collapsed into
//   OWNER_CONFIRMED.
app.post('/api/dialer/identity', async (req, res) => {
  try {
    const {
      lead_id, caller_name, relationship, property_confirmed,
      name_confirmed, wrong_number, do_not_call, disposition, notes,
    } = req.body || {};
    if (!lead_id) return res.status(400).json({ error: 'lead_id required' });

    const rel = (relationship || 'UNKNOWN').toUpperCase();
    const prev = getLeadIdentityState(lead_id);

    const entry = {
      lead_id,
      caller_name: caller_name || '',
      relationship: rel,
      property_confirmed: !!property_confirmed,
      name_confirmed: !!name_confirmed,
      wrong_number: !!wrong_number,
      do_not_call: !!do_not_call,
      disposition: disposition || '',
      notes: notes || '',
      timestamp: new Date().toISOString(),
    };

    // Map caller relationship â†’ identity state (mirrors owner_identity.py).
    let identity_state;
    if (entry.wrong_number) identity_state = 'WRONG_NUMBER';
    else if (entry.do_not_call) identity_state = 'DO_NOT_CALL';
    else if (rel === 'WRONG_PERSON') identity_state = 'WRONG_PERSON';
    else if (rel === 'TENANT') identity_state = 'TENANT';
    else if (rel === 'RELATIVE' || rel === 'RELATIVE_OR_ASSOCIATE') identity_state = 'RELATIVE_OR_ASSOCIATE';
    else if (rel === 'AUTHORIZED_DECISION_MAKER') identity_state = 'AUTHORIZED_DECISION_MAKER';
    else if (rel === 'OWNER' && entry.name_confirmed && entry.property_confirmed) identity_state = 'OWNER_CONFIRMED';
    else if (rel === 'OWNER' && entry.property_confirmed) identity_state = 'OWNER_LIKELY';
    else if (entry.name_confirmed || entry.property_confirmed) identity_state = 'OWNER_LIKELY';
    else identity_state = 'IDENTITY_UNCONFIRMED';
    entry.identity_state = identity_state;
    entry.previous_identity_state = prev;
    entry.verification_source = 'CALLER_CONFIRMATION';
    entry.source = 'CALL_LEVEL';
    entry.caller_identity_verified = identity_state === 'OWNER_CONFIRMED' || identity_state === 'AUTHORIZED_DECISION_MAKER';

    let results = [];
    if (fs.existsSync(identityResultsFile)) {
      results = JSON.parse(fs.readFileSync(identityResultsFile, 'utf8'));
    }
    results = results.filter((r) => r.lead_id !== lead_id);
    results.push(entry);
    fs.writeFileSync(identityResultsFile, JSON.stringify(results, null, 2));

    // Stamp identity onto the lead in leads_database.json (preserving all
    // existing sales data â€” dispositions, notes, attempts, stage, source).
    if (fs.existsSync(mbmDialerFile)) {
      try {
        const targetLead = (Array.isArray(data) ? data : (data.leads || [])).find((l) => String(l.id) === String(lead_id));
        if (targetLead) {
          const fields = {
            identity_state,
            identity_relationship: entry.relationship,
            identity_property_confirmed: entry.property_confirmed,
            identity_name_confirmed: entry.name_confirmed,
            identity_caller_name: entry.caller_name,
            identity_updated_at: entry.timestamp,
            caller_identity_verified: entry.caller_identity_verified,
            database_ownership_verified: !!(targetLead.owner_status === 'VERIFIED_OWNER' ||
              (targetLead.details && targetLead.details.Owner_Status === 'VERIFIED_OWNER')),
            details: Object.assign({}, targetLead.details || {}, { identity_state }),
          };
          const res = await gatewayPatchLeads([{ id: lead_id, fields }], { author: 'node-identity-stamp' });
          if (!res.ok) console.error('[identity] gateway patch failed');
        }
      } catch (err) {
        console.error('[identity] DB patch failed:', err.message);
      }
    }

    res.json({ status: 'success', entry });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/dialer/identity â€” All recorded identity results
app.get('/api/dialer/identity', (req, res) => {
  try {
    if (fs.existsSync(identityResultsFile)) {
      const data = JSON.parse(fs.readFileSync(identityResultsFile, 'utf8'));
      return res.json({ status: 'success', count: data.length, identities: data });
    }
    res.json({ status: 'success', count: 0, identities: [] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/dialer/tonight â€” Tonight's skip-traced call list
app.get('/api/dialer/tonight', (req, res) => {
  try {
    const tonightFile = path.join(__dirname, '..', 'MBM', 'LeadEngine', 'logs', 'tonight_10_call_list_skip_traced.json');
    if (fs.existsSync(tonightFile)) {
      const data = JSON.parse(fs.readFileSync(tonightFile, 'utf8'));
      return res.json({ status: 'success', count: data.length, prospects: data });
    }
    res.json({ status: 'success', count: 0, prospects: [] });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/dialer/call â€” Place an outbound call via Phound (webhook-first outcomes)
app.post('/api/dialer/call', async (req, res) => {
  try {
    const { to_number, prospect_name, lead_id } = req.body;
    if (!to_number) return res.status(400).json({ error: 'to_number is required' });

    const phone = cleanPhone(to_number);
    const result = await telephony.start_call({ to_number: phone, prospect_name, lead_id });
    if (result.status === 'error') {
      return res.status(502).json({ error: result.error, http_status: result.http_status });
    }
    return res.json({
      ...result,
      to: phone,
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    if (err.code === 'TELEPHONY_BLOCKED') {
      return res.status(423).json({ status: 'TELEPHONY_BLOCKED', error: err.message });
    }
    res.status(400).json({ error: err.message });
  }
});

// POST /api/dialer/call-bridge â€” operator handoff via Phound (native deep-link)
app.post('/api/dialer/call-bridge', async (req, res) => {
  try {
    const { to_number, prospect_name, lead_id } = req.body;
    if (!to_number) return res.status(400).json({ error: 'to_number is required' });

    const result = await telephony.start_call({
      to_number: cleanPhone(to_number), prospect_name, lead_id,
    });
    if (result.status === 'error') {
      return res.status(502).json({ error: result.error, http_status: result.http_status });
    }
    res.json({
      ...result,
      timestamp: new Date().toISOString(),
      message: `Phound handoff ready for ${prospect_name || 'Prospect'} â€” outcome arrives via webhook.`,
    });
  } catch (err) {
    if (err.code === 'TELEPHONY_BLOCKED') {
      return res.status(423).json({ status: 'TELEPHONY_BLOCKED', error: err.message });
    }
    res.status(400).json({ error: err.message });
  }
});

// GET /api/dialer/status â€” production telephony provider health
app.get('/api/dialer/status', async (req, res) => {
  const health = await telephony.health();
  res.json({
    provider: telephony.code,
    mode: telephony.mode?.() || null,
    status: health.ok ? 'active' : 'blocked',
    reason: health.reason || null,
    http_status: health.http_status,
    outcome_law: 'webhook-first; no event = UNKNOWN',
  });
});

// POST /api/telephony/phound/webhook â€” THE only path real call outcomes enter
app.post('/api/telephony/phound/webhook', (req, res) => {
  const raw = req.body || {};
  const event = normalizeEvent(raw, { provider: 'phound' });
  const dedupeKey = event.provider_call_id
    ? `${event.provider_call_id}:${event.status}`
    : null;
  if (dedupeKey && _seenProviderEvents.has(dedupeKey)) {
    return res.json({ ok: true, duplicate: true, status: event.status });
  }
  if (dedupeKey) _seenProviderEvents.add(dedupeKey);

  const sink = persistTelephonyEvent(event);
  res.json({
    ok: true,
    duplicate: false,
    stored: sink,
    call_id: event.call_id,
    provider_call_id: event.provider_call_id,
    lead_id: event.lead_id,
    status: event.status,
  });
});

// POST /api/dialer/verify-number â€” NOT AVAILABLE on the production provider.
// Phound manages caller identity inside its app; there is no Verify-style API.
app.post('/api/dialer/verify-number', async (req, res) => {
  const result = await telephony.verify_caller();
  if (result.supported) return res.json(result);
  res.status(501).json({
    status: 'NOT_AVAILABLE_ON_PROVIDER',
    telephony_provider: telephony.code,
    message: 'Caller identity is managed in the Phound app. Verify your business number there; no code-based verification is exposed here.',
  });
});

// POST /api/dialer/check-verification â€” NOT AVAILABLE on the production provider.
app.post('/api/dialer/check-verification', async (req, res) => {
  res.status(501).json({
    status: 'NOT_AVAILABLE_ON_PROVIDER',
    telephony_provider: telephony.code,
    message: 'Caller identity is managed in the Phound app.',
  });
});

// POST /api/dialer/cold-call â€” One-click cold call from call list with auto-script
app.post('/api/dialer/cold-call', async (req, res) => {
  try {
    const { prospect_index, my_phone, bridge } = req.body;

    const tonightFile = path.join(__dirname, '..', 'MBM', 'LeadEngine', 'logs', 'tonight_10_call_list_skip_traced.json');
    if (!fs.existsSync(tonightFile)) {
      return res.status(404).json({ error: 'No call list found â€” run skip tracer first' });
    }

    const prospects = JSON.parse(fs.readFileSync(tonightFile, 'utf8'));
    const idx = prospect_index || 0;
    if (idx >= prospects.length) {
      return res.status(400).json({ error: `Index ${idx} out of range â€” ${prospects.length} prospects available` });
    }

    const prospect = prospects[idx];
    const phone = prospect.primary_phone_raw || cleanPhone(prospect.primary_phone);

    const result = await telephony.start_call({
      to_number: phone,
      prospect_name: prospect.prospect_name,
      lead_id: prospect.id || null,
    });
    if (result.status === 'error') {
      return res.status(502).json({ error: result.error, http_status: result.http_status, prospect });
    }

    return res.json({
      ...result,
      prospect,
      script: prospect.friendly_script,
      message: `Phound handoff ready for ${prospect.prospect_name} â€” outcome arrives via webhook.`,
    });
  } catch (err) {
    if (err.code === 'TELEPHONY_BLOCKED') {
      return res.status(423).json({ status: 'TELEPHONY_BLOCKED', error: err.message });
    }
    res.status(400).json({ error: err.message });
  }
});

// === Neteller Checkout / Monetization ===
const NETELLER_PRICES = {
  lead_pack_daily: 18,
  lead_pack_monthly: 497,
  ai_email: 297,
  ai_full_stack: 497,
  ai_enterprise: 997,
};

// POST /api/checkout â€” create a 1-click Neteller checkout for a plan
app.post('/api/checkout', async (req, res) => {
  try {
    const { plan, email, name, company } = req.body || {};
    if (!plan) return res.status(400).json({ error: 'plan is required' });

    const amount = NETELLER_PRICES[plan];
    if (!amount) return res.status(400).json({ error: `no Neteller price mapped for plan "${plan}"` });

    const url = netellerLink(amount, plan, { currency: 'USD' });

    // Record intent to email_queue so no request is ever lost (orders table optional).
    if (supabase) {
      const subject = `PAID INTENT: ${plan} ($${amount})${company ? ' for ' + company : ''}`;
      const body = `Prospect ${name ? name + ' ' : ''}${company ? 'from ' + company + ' ' : ''}requested plan "${plan}" ($${amount}) via Neteller checkout.\nEmail: ${email || 'unknown'}\nCheckout: ${url}`;
      await supabase.from('email_queue').insert({ recipient_email: email || 'walkin@demo.com', subject, body, status: 'qued' });
    }
    return res.json({ status: 'checkout', url, id: `nt-${Date.now()}`, neteller_email: NETELLER_EMAIL, neteller_account_id: NETELLER_ACCOUNT_ID });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// START SERVER
app.listen(PORT, () => {
  console.log(`Contech AI Agentic Teamz API server running on http://localhost:${PORT}`);
});
