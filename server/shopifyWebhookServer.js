import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import crypto from 'node:crypto';
import express from 'express';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const PORT = process.env.SHOPIFY_WEBHOOK_PORT || 3005;
const REPO_ROOT = path.resolve(__dirname, '..');

// Optional Shopify webhook HMAC verification secret. Set SHOPIFY_WEBHOOK_SECRET in .env.
const SHOPIFY_WEBHOOK_SECRET = process.env.SHOPIFY_WEBHOOK_SECRET || '';
// Interpret all side-effects (fulfilment / recovery queueing) as writes unless dry-run enabled.
const DRY_RUN = process.env.SHOPIFY_DRY_RUN === 'true';
// Manual webhook registration endpoint is only exposed when a token is set.
const WEBHOOK_TOKEN = process.env.SHOPIFY_WEBHOOK_TOKEN || '';

const app = express();
// Capture raw body so Shopify's HMAC signature can be verified.
app.use(
  express.json({
    verify: (req, _res, buf) => {
      req.rawBody = buf;
    },
  })
);

const LOG_DIR = path.join(REPO_ROOT, 'MBM', 'Shopify', 'logs');
const WEBHOOK_LOG = path.join(LOG_DIR, 'webhook_log.json');
fs.mkdirSync(LOG_DIR, { recursive: true });

// ── helpers ────────────────────────────────────────────────────────────────

function logWebhook(topic, payload, result) {
  let entries = [];
  if (fs.existsSync(WEBHOOK_LOG)) {
    try {
      entries = JSON.parse(fs.readFileSync(WEBHOOK_LOG, 'utf-8'));
    } catch {
      entries = [];
    }
  }
  entries.push({
    topic,
    shop: payload?.shop_name || payload?.shop?.name || null,
    id: payload?.id || null,
    email: payload?.customer?.email || payload?.email || null,
    total_price: payload?.total_price || payload?.presentment_money?.amount || null,
    received_at: new Date().toISOString(),
    result,
  });
  fs.writeFileSync(WEBHOOK_LOG, JSON.stringify(entries.slice(-500), null, 2), 'utf-8');
}

function runPython(scriptRelPath, stdinData) {
  const script = path.join(REPO_ROOT, scriptRelPath);
  return new Promise((resolve) => {
    const child = spawn('python', [script], {
      cwd: REPO_ROOT,
      env: { ...process.env, SHOPIFY_DRY_RUN: DRY_RUN ? 'true' : '' },
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => (stdout += d.toString()));
    child.stderr.on('data', (d) => (stderr += d.toString()));
    if (stdinData !== undefined) {
      child.stdin.write(JSON.stringify(stdinData));
    }
    child.stdin.end();
    child.on('close', (code) => {
      resolve({ code: code ?? 0, stdout, stderr });
    });
    child.on('error', (err) => {
      resolve({ code: 1, stdout, stderr: stderr || err.message });
    });
  });
}

function verifyWebhook(req, _res) {
  if (!SHOPIFY_WEBHOOK_SECRET) return true; // verification disabled
  const suppliedHmac = req.get('X-Shopify-Hmac-Sha256') || '';
  if (!suppliedHmac) return false;
  const digest = crypto
    .createHmac('sha256', SHOPIFY_WEBHOOK_SECRET)
    .update(req.rawBody || Buffer.alloc(0))
    .digest('base64');
  return crypto.timingSafeEqual(Buffer.from(digest, 'utf-8'), Buffer.from(suppliedHmac, 'utf-8'));
}

// Translate a Shopify order/checkout payload into our canonical structure.
function extractOrderItems(body) {
  const lineItems = (body.line_items || []).map((li) => ({
    title: li.title || li.name || 'Product',
    quantity: li.quantity || 1,
    price: li.price !== undefined ? parseFloat(li.price) : null,
  }));
  return {
    id: body.id !== undefined ? String(body.id) : body.name || `shop_ord_${Date.now()}`,
    email: body.customer?.email || body.email || 'customer@contecai.com',
    total_price: parseFloat(body.total_price ?? body.current_total_price ?? 299),
    currency: body.currency || body.presentment_currency || 'USD',
    line_items: lineItems,
  };
}

function extractCheckout(body) {
  return {
    id: body.id !== undefined ? String(body.id) : body.token || `checkout_${Date.now()}`,
    email: body.email || '',
    total_price: parseFloat(body.total_price ?? body.subtotal_price ?? 299),
    product_title: body.line_items?.[0]?.title || body.title || 'Product',
    abandoned_hours_ago: 0,
    stage: 'stage_2_discount_15', // queue 15% SAVE15 recovery immediately
  };
}

function respond(res, success, data, extra = {}) {
  res.status(success ? 200 : 500).json({
    status: success ? 'success' : 'failure',
    inputs: extra.inputs || {},
    outputs: data,
    errors: extra.errors || [],
    next_action: 'continue',
    owner: 'system',
    timestamp: new Date().toISOString(),
  });
}

// ── routes ─────────────────────────────────────────────────────────────────

app.get('/', (_req, res) => {
  res.json({
    status: 'ok',
    service: 'shopify-webhook-server',
    port: PORT,
    topics: ['orders/create', 'orders/paid', 'checkouts/update'],
  });
});

// orders/create — intake a newly created order, issue digital license.
app.post('/webhook/orders/create', async (req, res) => {
  if (!verifyWebhook(req, res)) {
    return respond(res, false, {}, { inputs: { webhook: 'orders/create' }, errors: ['HMAC verification failed'] });
  }
  const order = extractOrderItems(req.body);
  const result = await runPython('MBM/Shopify/shopify_order_fulfillment.py', order);
  logWebhook('orders/create', req.body, simplify(result));
  respond(res, result.code === 0, { order, fulfillment: parseJsonOut(result.stdout) }, {
    inputs: { webhook: 'orders/create', order_id: order.id },
    errors: result.stderr ? [result.stderr.slice(0, 500)] : [],
  });
});

// orders/paid — payment captured, confirm fulfillment + record revenue.
app.post('/webhook/orders/paid', async (req, res) => {
  if (!verifyWebhook(req, res)) return;
  const order = extractOrderItems(req.body);
  const result = await runPython('MBM/Shopify/shopify_order_fulfillment.py', order);
  logWebhook('orders/paid', req.body, simplify(result));
  respond(res, result.code === 0, { stdout: result.stdout, id: order.id, paid: true }, {
    inputs: { webhook: 'orders/paid', order_id: order.id },
    errors: result.stderr ? [result.stderr.trim()] : [],
  });
});

// checkouts/update — abandoned checkout → queue SAVE15 recovery email.
app.post('/webhook/checkouts/update', async (req, res) => {
  if (!verifyWebhook(req, res)) return;
  const checkout = extractCheckout(req.body);
  if (!checkout.email) {
    return respond(res, true, { note: 'no customer email; ignored', checkout }, {
      inputs: { webhook: 'checkouts/update', id: checkout.id },
    });
  }
  const result = await runPython('MBM/Shopify/shopify_abandoned_cart_recovery.py', checkout);
  logWebhook('checkouts/update', req.body, simplify(result));
  respond(res, result.code === 0, { stdout: result.stdout, queued_save15: true, checkout }, {
    inputs: { webhook: 'checkouts/update', id: checkout.id },
    errors: result.stderr ? [result.stderr.trim()] : [],
  });
});

// Optional manual-trigger registration of webhook subscriptions against the
// Shopify Admin API (guarded by SHOPIFY_WEBHOOK_TOKEN).
app.post('/register', async (req, res) => {
  if (!WEBHOOK_TOKEN || req.get('Authorization') !== `Bearer ${WEBHOOK_TOKEN}`) {
    return res.status(401).json({ status: 'failure', errors: ['Unauthorized'] });
  }
  const { store_url, access_token, address } = req.body;
  if (!store_url || !access_token || !address) {
    return res.status(400).json({ error: 'store_url, access_token, address required' });
  }
  const topics = ['orders/create', 'orders/paid', 'checkouts/update'];
  const results = [];
  for (const topic of topics) {
    const body = { topic, address, format: 'json' };
    const url = `https://${store_url.replace(/^https?:\/\//, '').replace(/\/$/, '')}/admin/api/2026-01/webhooks.json`;
    const r = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Shopify-Access-Token': access_token },
      body: JSON.stringify(body),
    });
    results.push({ topic, status: r.status, ok: r.ok });
  }
  res.status(200).json({ status: 'ok', results });
});

function simplify(result) {
  return { code: result.code, stdout: (result.stdout || '').trim().slice(0, 300) };
}

// Best-effort parse of a JSON object embedded in a python stdout stream.
function parseJsonOut(stdout) {
  try {
    const text = (stdout || '').trim();
    const start = text.indexOf('{');
    if (start === -1) return null;
    return JSON.parse(text.slice(start));
  } catch {
    return null;
  }
}

app.listen(PORT, () => {
  console.log(`Shopify webhook server running on http://localhost:${PORT}`);
  console.log(`Topics: orders/create, orders/paid, checkouts/update`);
  console.log(`DRY_RUN=${DRY_RUN} HMAC_verification=${SHOPIFY_WEBHOOK_SECRET ? 'enabled' : 'disabled'}`);
});