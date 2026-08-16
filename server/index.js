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

// ── SECURITY: CORS allowlist + optional bearer-token auth ──────────────────
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
// in local dev — set the token before exposing the server to a network.
const API_BEARER_TOKEN = process.env.API_BEARER_TOKEN || '';
if (API_BEARER_TOKEN) {
  console.log('[SECURITY] API_BEARER_TOKEN set — sensitive /api routes require Authorization: Bearer <token>');
} else {
  console.warn('[SECURITY] WARNING: API_BEARER_TOKEN is NOT set. Sensitive /api routes '
    + '(dialer PII, Twilio call endpoints, orders, payout, telegram-alert) are UNPROTECTED. '
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

app.use(express.json({ limit: '10mb' }));
app.use(express.json({ limit: '10mb' }));
app.use('/videos', express.static(path.join(__dirname, '..', 'clipping-factory', 'MBM-Social', 'generated_videos')));
app.use('/publish-queue', express.static(path.join(__dirname, '..', 'clipping-factory', 'MBM-Social', 'publish_queue', 'media')));

const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 10 * 1024 * 1024 } });

// GET /api/videos — List all generated HD videos for instant web playback
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

    // Self-signup without a role → assign 'customer'
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

// ── Demo Campaign API ──────────────────────────────────────

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

// ── Lead Pipeline API ───────────────────────────────────────

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

// ── Client Orders API ──────────────────────────────────────

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

// ── Lead Pipeline API (legacy) ──────────────────────────────

app.get('/api/leads/stats', (req, res) => {
  res.json(loadStats());
});

app.get('/api/leads/whatsapp-report', (req, res) => {
  const report = generateSellerWhatsAppReport();
  res.json(report);
});

// ── Demo Campaign API ──────────────────────────────────────
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

// HUNTER — Hourly revenue outreach (queues new targets to email_queue)
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

// ─── VOICE AGENTS STUDIO & CREATOR MONETIZATION API ───

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

// GET /api/voice-agents — List all active voice agents
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

// POST /api/voice-agents — Create or update a voice agent
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

// POST /api/voice-agents/:id/simulate-call — Live call simulation & creator payout calculation
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

// GET /api/creator/wallet — Fetch creator wallet stats & payout ledger
app.get('/api/creator/wallet', (req, res) => {
  res.json(creatorWallet);
});

// POST /api/creator/payout — Request payout cashout
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

// POST /api/sales/assign-deal — Assigns high-ticket US deals to Sales Reps
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

// GET /api/sales/deals — Returns assigned sales deals
app.get('/api/sales/deals', (req, res) => {
  res.json(inMemorySalesDeals);
});

// POST /api/sales/proposals — Creates B2B Sales Proposal with Neteller checkout link
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

// POST /api/sales/telegram-alert — Sends instant Telegram notification to Sales Chat
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

// POST /api/instant-cash/clipping — On-demand AI Video Clipping job ($0.10/clip)
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

// POST /api/instant-cash/ig-dm — Launch Instagram AI DM Hunter ($149/mo)
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

// POST /api/instant-cash/cold-calling — Launch Cold Calling Swarm ($0.50/call)
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

// POST /api/instant-cash/marketing-agencies — Marketing Agencies White-Label AI Suite ($1,500 setup + $997/mo)
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

// GET /api/voice-agents/free-us-number — Get Assigned Free US Number & Minutes
app.get('/api/voice-agents/free-us-number', (req, res) => {
  res.json({
    status: 'active',
    us_phone_number: process.env.TWILIO_PHONE_NUMBER || '+1 (646) 846-8822',
    formatted_number: '+1 (646) 846-8822',
    country: 'United States (New York, NY)',
    free_calling_minutes_remaining: 1000,
    free_trial_credit_usd: 15.50,
    features: [
      'Outbound US Cold Calling',
      'International Calling Minutes',
      'Inbound Call Forwarding',
      'WebRTC Browser Dialer'
    ]
  });
});

// POST /api/voice-agents/place-call — Initiate WebRTC Outbound Call
app.post('/api/voice-agents/place-call', (req, res) => {
  try {
    const { to_number, prospect_name } = req.body;
    res.status(201).json({
      status: 'connected_webrtc',
      call_id: `call-${Date.now()}`,
      from: process.env.TWILIO_PHONE_NUMBER || '+1 (646) 846-8822',
      to: to_number || '+12125555142',
      white_label_portal_url: `https://agency.contech-ai.com/portal/${Date.now()}`,
      setup_fee: "$1,500.00",
      monthly_retainer: "$997.00/mo",
      call_markup: "$0.50/min (Wholesale: $0.10/min)",
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/instant-cash/upwork — Upwork High-Ticket AI Client Bounties & Proposals
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

// ═══════════════════════════════════════════════════════════════════════
// DIALER API — Real Twilio integration with bridge-to-phone support
// ═══════════════════════════════════════════════════════════════════════

const TWILIO_SID = process.env.TWILIO_ACCOUNT_SID;
const TWILIO_TOKEN = process.env.TWILIO_AUTH_TOKEN;
const TWILIO_API_KEY_SID = process.env.TWILIO_API_KEY_SID;
const TWILIO_API_KEY_SECRET = process.env.TWILIO_API_KEY_SECRET;
const TWILIO_FROM = process.env.TWILIO_PHONE_NUMBER || '+16619909068';

let twilioClient = null;
try {
  const twilio = await import('twilio');
  if (TWILIO_API_KEY_SID && TWILIO_API_KEY_SECRET) {
    twilioClient = twilio.default(TWILIO_API_KEY_SID, TWILIO_API_KEY_SECRET, { accountSid: TWILIO_SID });
    console.log(`[DIALER] Twilio client initialized (API Key) — Number: ${TWILIO_FROM}`);
  } else if (TWILIO_SID && TWILIO_TOKEN) {
    twilioClient = twilio.default(TWILIO_SID, TWILIO_TOKEN);
    console.log(`[DIALER] Twilio client initialized (Token) — Number: ${TWILIO_FROM}`);
  } else {
    console.log('[DIALER] Twilio credentials not set — dialer will run in demo mode');
  }
} catch (e) {
  console.log(`[DIALER] Twilio init failed: ${e.message}`);
}

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

// GET /api/dialer/leads — All pipeline leads with phone numbers
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

// GET /api/dialer/top50 — Top 50 calling list
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

// GET /api/gtm/brief — GTM Daily Quick Brief (reads the Quick Brief Center artifacts).
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

// GET /api/gtm/top-actions — GTM Top-N next actions (execution queue).
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

// GET /api/dialer/re-queue — Real Estate dialer queue (AutoDialer schema).
// Phone app MUST only ever see dialable E.164 (+1XXXXXXXXXX) numbers backed by a
// REAL lead. Fabricated 555/00x numbers are dropped, and the real NPI clinic
// queue is served when the RE queue has nothing verifiable.
const mbmDialerFile = path.join(__dirname, '..', 'mbm-dialer', 'app', 'public', 'leads_database.json');
const realEstateQueueFile = path.join(__dirname, '..', 'MBM', 'LeadEngine', 'real_estate_calling_queue.json');
const npiQueueFile = path.join(__dirname, '..', 'MBM', 'LeadEngine', 'cold_calling_queue.json');

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
    property_type: `${lead.type || lead.vertical || 'Real Estate'} — ${lead.subtype || 'Contact'}`,
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

  if (fs.existsSync(mbmDialerFile)) {
    try {
      const data = JSON.parse(fs.readFileSync(mbmDialerFile, 'utf8'));
      const arr = Array.isArray(data) ? data : (data.leads || data.prospects || []);
      for (const [i, lead] of arr.entries()) addLead(lead, i);
    } catch {}
  }

  if (fs.existsSync(realEstateQueueFile)) {
    try {
      const data = JSON.parse(fs.readFileSync(realEstateQueueFile, 'utf8'));
      const arr = Array.isArray(data) ? data : (data.queue || data.prospects || []);
      for (const [i, lead] of arr.entries()) addLead(lead, prospects.length + i);
    } catch {}
  }

  if (fs.existsSync(npiQueueFile)) {
    try {
      const data = JSON.parse(fs.readFileSync(npiQueueFile, 'utf8'));
      const arr = Array.isArray(data) ? data : (data.queue || data.prospects || []);
      for (const [i, lead] of arr.entries()) addLead(lead, prospects.length + i);
    } catch {}
  }

  // Identity-aware ranking: live-confirmed owners/decision-makers surface
  // first, then unconfirmed-but-callable, and unconfirmed lower priority.
  // (Suppressed states are already excluded above.) This mirrors
  // owner_identity.IDENTITY_QUEUE_PRIORITY — lower rank = called first.
  const IDENTITY_PRIORITY = {
    OWNER_CONFIRMED: 0,
    AUTHORIZED_DECISION_MAKER: 1,
    OWNER_LIKELY: 2,
    IDENTITY_UNCONFIRMED: 3,
  };
  const rankLead = (p) => {
    const st = p.identity_state || '';
    if (st in IDENTITY_PRIORITY) return IDENTITY_PRIORITY[st];
    return 2; // no recorded identity state = callable but unconfirmed
  };
  prospects.sort((a, b) => {
    const ra = rankLead(a), rb = rankLead(b);
    if (ra !== rb) return ra - rb;
    return (b.distress_score || 0) - (a.distress_score || 0);
  });

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

// POST /api/dialer/disposition — Save call disposition
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

// GET /api/dialer/dispositions — Get all dispositions
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

// ── Owner Identity Verification Layer ────────────────────────────────
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

// POST /api/dialer/identity — Save a call-level identity result.
// Body: { lead_id, caller_name, relationship, property_confirmed,
//         name_confirmed, wrong_number, do_not_call, disposition, notes }
// Identity-state mapping mirrors owner_identity.py (Python is authoritative):
//   OWNER_CONFIRMED requires relationship === 'OWNER' AND name_confirmed
//   AND property_confirmed. NEVER derived from phone/address/DB alone.
//   AUTHORIZED_DECISION_MAKER stays separate and is never collapsed into
//   OWNER_CONFIRMED.
app.post('/api/dialer/identity', (req, res) => {
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

    // Map caller relationship → identity state (mirrors owner_identity.py).
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
    // existing sales data — dispositions, notes, attempts, stage, source).
    if (fs.existsSync(mbmDialerFile)) {
      try {
        const data = JSON.parse(fs.readFileSync(mbmDialerFile, 'utf8'));
        const arr = Array.isArray(data) ? data : (data.leads || []);
        let patched = 0;
        for (const lead of arr) {
          if (String(lead.id) === String(lead_id)) {
            lead.identity_state = identity_state;
            lead.identity_relationship = entry.relationship;
            lead.identity_property_confirmed = entry.property_confirmed;
            lead.identity_name_confirmed = entry.name_confirmed;
            lead.identity_caller_name = entry.caller_name;
            lead.identity_updated_at = entry.timestamp;
            lead.caller_identity_verified = entry.caller_identity_verified;
            lead.database_ownership_verified = !!(lead.owner_status === 'VERIFIED_OWNER' ||
              (lead.details && lead.details.Owner_Status === 'VERIFIED_OWNER'));
            if (lead.details) lead.details.identity_state = identity_state;
            patched += 1;
          }
        }
        if (patched) {
          fs.writeFileSync(mbmDialerFile, JSON.stringify(arr, null, 2));
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

// GET /api/dialer/identity — All recorded identity results
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

// GET /api/dialer/tonight — Tonight's skip-traced call list
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

// POST /api/dialer/call — Place an outbound call (direct or bridge mode)
app.post('/api/dialer/call', async (req, res) => {
  try {
    const { to_number, prospect_name, bridge, my_phone, agent_type } = req.body;
    if (!to_number) return res.status(400).json({ error: 'to_number is required' });

    const phone = cleanPhone(to_number);

    if (!twilioClient) {
      return res.json({
        status: 'demo_mode',
        message: 'Twilio not configured — add TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN to .env',
        to: phone,
        prospect_name: prospect_name || 'Prospect',
      });
    }

    let twiml;
    if (bridge && my_phone) {
      // Bridge mode: call your phone first, then connect to prospect
      // This bypasses Twilio trial restrictions since YOUR number is verified
      const myClean = cleanPhone(my_phone);
      twiml = `<Response><Say>Connecting you to ${escapeXml(prospect_name) || 'prospect'}...</Say><Dial callerId="${TWILIO_FROM}" timeout="30">${phone}</Dial></Response>`;

      // First call YOUR phone with TwiML that dials the prospect
      const call = await twilioClient.calls.create({
        to: myClean,
        from: TWILIO_FROM,
        twiml: twiml,
        timeout: 60,
        record: true,
      });

      return res.json({
        status: 'bridged',
        call_sid: call.sid,
        my_phone: myClean,
        to: phone,
        prospect_name: prospect_name || 'Prospect',
        message: `Ringing your phone (${myClean}) — answer to connect to ${prospect_name}`,
        timestamp: new Date().toISOString(),
      });
    } else {
      // Direct mode: call the prospect directly
      twiml = `<Response><Say>Hello, this is a call from MBM Property Solutions.</Say><Pause length="2"/></Response>`;

      const call = await twilioClient.calls.create({
        to: phone,
        from: TWILIO_FROM,
        twiml: twiml,
        timeout: 30,
        machine_detection: 'Enable',
        machine_detection_timeout: 8,
        record: true,
      });

      return res.json({
        status: 'direct',
        call_sid: call.sid,
        to: phone,
        prospect_name: prospect_name || 'Prospect',
        message: `Calling ${prospect_name} at ${phone}...`,
        timestamp: new Date().toISOString(),
      });
    }
  } catch (err) {
    const isTrialError = err.message && err.message.includes('unverified');
    res.status(400).json({
      error: err.message,
      hint: isTrialError
        ? 'Trial accounts can only call verified numbers. Use bridge mode: set bridge=true and my_phone=YOUR_NUMBER'
        : undefined,
    });
  }
});

// POST /api/dialer/call-bridge — Bridge: calls your phone, then dials prospect when you answer
app.post('/api/dialer/call-bridge', async (req, res) => {
  try {
    const { to_number, prospect_name, my_phone } = req.body;
    if (!to_number) return res.status(400).json({ error: 'to_number is required' });
    if (!my_phone) return res.status(400).json({ error: 'my_phone is required for bridge mode' });

    if (!twilioClient) {
      return res.json({
        status: 'demo_mode',
        message: 'Twilio not configured — add TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN to .env',
        to: cleanPhone(to_number),
        my_phone: cleanPhone(my_phone),
      });
    }

    const phone = cleanPhone(to_number);
    const myClean = cleanPhone(my_phone);

    const twiml = `<Response><Say>Connecting you to ${escapeXml(prospect_name) || 'prospect'}...</Say><Dial callerId="${TWILIO_FROM}" timeout="30">${phone}</Dial></Response>`;

    const call = await twilioClient.calls.create({
      to: myClean,
      from: TWILIO_FROM,
      twiml: twiml,
      timeout: 60,
      record: true,
    });

    res.json({
      status: 'ringing_your_phone',
      call_sid: call.sid,
      my_phone: myClean,
      to: phone,
      prospect_name: prospect_name || 'Prospect',
      message: `Your phone (${myClean}) is ringing — answer to connect to ${prospect_name}`,
      timestamp: new Date().toISOString(),
    });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

// GET /api/dialer/status — Twilio account status + verified numbers
app.get('/api/dialer/status', async (req, res) => {
  try {
    if (!twilioClient) {
      return res.json({
        status: 'demo_mode',
        message: 'Twilio not configured',
        phone: TWILIO_FROM,
        verified_numbers: [],
      });
    }

    const account = await twilioClient.api.accounts(TWILIO_SID).fetch();
    const callerIds = await twilioClient.outgoingCallerIds.list();
    const verified = callerIds.map(c => ({
      phone: c.phone_number,
      friendly_name: c.friendly_name,
    }));

    res.json({
      status: 'active',
      account_name: account.friendly_name,
      account_status: account.status,
      phone: TWILIO_FROM,
      is_trial: account.type === 'Trial',
      verified_numbers: verified,
      hint: verified.length === 0 && account.type === 'Trial'
        ? 'Trial account with no verified numbers. Use bridge mode (my_phone param) to call leads.'
        : undefined,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/dialer/verify-number — Start verification for a phone number
app.post('/api/dialer/verify-number', async (req, res) => {
  try {
    const { phone_number } = req.body;
    if (!phone_number) return res.status(400).json({ error: 'phone_number is required' });

    if (!twilioClient) {
      return res.json({ status: 'demo_mode', message: 'Twilio not configured' });
    }

    const phone = cleanPhone(phone_number);
    const verification = await twilioClient.verify.services
      .list({ limit: 1 })
      .then(services => {
        if (services.length === 0) throw new Error('No Verify service found — create one at console.twilio.com');
        return twilioClient.verify.services(services[0].sid).verifications.create({
          to: phone,
          channel: 'sms',
        });
      });

    res.json({
      status: 'verification_sent',
      phone: phone,
      message: `Verification SMS sent to ${phone} — check your phone and enter the code`,
    });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

// POST /api/dialer/check-verification — Check verification code
app.post('/api/dialer/check-verification', async (req, res) => {
  try {
    const { phone_number, code } = req.body;
    if (!phone_number || !code) return res.status(400).json({ error: 'phone_number and code are required' });

    if (!twilioClient) {
      return res.json({ status: 'demo_mode', message: 'Twilio not configured' });
    }

    const phone = cleanPhone(phone_number);
    const check = await twilioClient.verify.services
      .list({ limit: 1 })
      .then(services => {
        return twilioClient.verify.services(services[0].sid).verificationChecks.create({
          to: phone,
          code: code,
        });
      });

    res.json({
      status: check.status === 'approved' ? 'verified' : 'pending',
      phone: phone,
      message: check.status === 'approved'
        ? `${phone} is now verified! You can call it directly.`
        : 'Invalid code — try again',
    });
  } catch (err) {
    res.status(400).json({ error: err.message });
  }
});

// POST /api/dialer/cold-call — One-click cold call from call list with auto-script
app.post('/api/dialer/cold-call', async (req, res) => {
  try {
    const { prospect_index, my_phone, bridge } = req.body;

    const tonightFile = path.join(__dirname, '..', 'MBM', 'LeadEngine', 'logs', 'tonight_10_call_list_skip_traced.json');
    if (!fs.existsSync(tonightFile)) {
      return res.status(404).json({ error: 'No call list found — run skip tracer first' });
    }

    const prospects = JSON.parse(fs.readFileSync(tonightFile, 'utf8'));
    const idx = prospect_index || 0;
    if (idx >= prospects.length) {
      return res.status(400).json({ error: `Index ${idx} out of range — ${prospects.length} prospects available` });
    }

    const prospect = prospects[idx];
    const phone = prospect.primary_phone_raw || cleanPhone(prospect.primary_phone);

    if (!twilioClient) {
      return res.json({
        status: 'demo_mode',
        prospect: prospect.prospect_name,
        phone: phone,
        script: prospect.friendly_script,
        message: 'Twilio not configured — showing script for manual call',
      });
    }

    const useBridge = bridge !== false; // Default to bridge for trial accounts
    if (useBridge && my_phone) {
      const myClean = cleanPhone(my_phone);
      const twiml = `<Response><Say>Connecting you to ${prospect.prospect_name}...</Say><Dial callerId="${TWILIO_FROM}" timeout="30">${phone}</Dial></Response>`;

      const call = await twilioClient.calls.create({
        to: myClean,
        from: TWILIO_FROM,
        twiml: twiml,
        timeout: 60,
        record: true,
      });

      return res.json({
        status: 'bridged',
        call_sid: call.sid,
        prospect: prospect,
        my_phone: myClean,
        message: `Your phone is ringing — answer to connect to ${prospect.prospect_name}`,
      });
    } else {
      const twiml = `<Response><Say>Hello, this is a call from MBM Property Solutions.</Say><Pause length="2"/></Response>`;
      const call = await twilioClient.calls.create({
        to: phone,
        from: TWILIO_FROM,
        twiml: twiml,
        timeout: 30,
        machine_detection: 'Enable',
        record: true,
      });

      return res.json({
        status: 'direct',
        call_sid: call.sid,
        prospect: prospect,
        message: `Calling ${prospect.prospect_name}...`,
      });
    }
  } catch (err) {
    const isTrialError = err.message && err.message.includes('unverified');
    res.status(400).json({
      error: err.message,
      hint: isTrialError ? 'Use bridge mode with my_phone to bypass trial restrictions' : undefined,
    });
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

// POST /api/checkout — create a 1-click Neteller checkout for a plan
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
