import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });
import { createClient } from '@supabase/supabase-js';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const MBM = join(ROOT, 'MBM');

function normalizeEmail(raw) {
  if (!raw) return null;
  return raw.trim().toLowerCase();
}
function validEmail(e) {
  if (!e) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
}
function parseCsv(path) {
  if (!existsSync(path)) return [];
  const text = readFileSync(path, 'utf8').replace(/^\uFEFF/, '');
  const lines = text.split('\n').filter(l => l.trim());
  if (lines.length < 2) return [];
  const headers = lines[0].split(',').map(h => h.replace(/^"|"$/g, '').trim());
  return lines.slice(1).map(line => {
    const vals = [];
    let inQ = false, cur = '';
    for (const ch of line) {
      if (ch === '"') { inQ = !inQ; continue; }
      if (ch === ',' && !inQ) { vals.push(cur.trim()); cur = ''; continue; }
      cur += ch;
    }
    vals.push(cur.trim());
    const obj = {};
    headers.forEach((h, i) => { obj[h] = vals[i] || ''; });
    return obj;
  });
}

function loadBuyers() {
  const buyers = [];

  // 1. wholesalers_final_qualified.csv (40 verified buyers with emails)
  const qualified = parseCsv(join(MBM, 'Artifacts', 'wholesalers_final_qualified.csv'));
  for (const r of qualified) {
    const e = normalizeEmail(r.Email);
    if (validEmail(e)) {
      buyers.push({
        company: r.Company || '',
        name: r.Contact_Name || '',
        email: e,
        phone: r.Phone || '',
        website: r.Website || '',
        city: r.City || '',
        confidence: parseInt(r.Confidence) || 0,
        source: r.Lead_Source || r.Lead_Source || 'qualified_csv',
        category: 'buyer',
      });
    }
  }

  // 2. Pipeline contacts
  const pipeline = parseCsv(join(MBM, 'Pipeline', 'pipeline.csv'));
  for (const r of pipeline) {
    const e = normalizeEmail(r.email);
    if (validEmail(e) && !buyers.some(b => b.email === e)) {
      buyers.push({
        company: r.company || '',
        name: r.contact || '',
        email: e,
        phone: r.phone || '',
        website: '',
        city: '',
        confidence: 80,
        source: 'pipeline',
        category: 'buyer',
        deal_value: r.deal_value || '',
        stage: r.stage || '',
      });
    }
  }

  // 3. Active outreach targets
  const contacts = parseCsv(join(MBM, 'Contacts', 'wholesaler_targets.csv'));
  for (const r of contacts) {
    const e = normalizeEmail(r.email);
    if (validEmail(e) && !buyers.some(b => b.email === e)) {
      buyers.push({
        company: r.company || '',
        name: '',
        email: e,
        phone: r.phone || '',
        website: '',
        city: '',
        confidence: 80,
        source: 'contacts',
        category: 'buyer',
      });
    }
  }

  return buyers;
}

function loadSellers() {
  const sellers = [];

  // 1. Scored leads with phones (highest priority)
  const scored = parseCsv(join(MBM, 'Artifacts', 'scored_leads_20260707_0200.csv'));
  for (const r of scored) {
    const phone = (r.Owner_Phone || '').trim();
    if (phone) {
      sellers.push({
        owner: r.Owner_Name || '',
        phone,
        address: r.Property_Address || '',
        city: r.City || '',
        distress: r.Distress_Signal || '',
        signal_date: r.Signal_Date || '',
        priority: r.Priority || 'MEDIUM',
        score: parseInt(r.Score) || 0,
        email: normalizeEmail(r.Owner_Email || ''),
        source: 'scored_leads',
        category: 'seller',
      });
    }
  }

  // 2. Distressed sellers from daily pack — no phones/emails, need skip-trace
  const sellersCsv = parseCsv(join(MBM, 'LeadPacks', 'Pack_2026-07-07', 'DISTRESSED_SELLERS_2026-07-07.csv'));
  for (const r of sellersCsv) {
    const addr = r.Property_Address || '';
    if (!addr) continue;
    const existing = sellers.some(s => s.address === addr);
    if (existing) continue;
    sellers.push({
      owner: r.Owner_Name || '',
      phone: r.Phone || '',
      address: addr,
      city: r.City || '',
      distress: r.Distress_Signal || '',
      signal_date: r.Signal_Date || '',
      priority: 'LOW',
      score: 0,
      email: normalizeEmail(r.Email || ''),
      source: 'distressed_pack_0707',
      category: 'seller',
      needs_skiptrace: !r.Phone && !r.Email,
    });
  }

  return sellers;
}

function loadAIProspects() {
  const prospects = [];

  // 1. Multi-market targets (44 entries with emails)
  const mmPath = join(MBM, 'MultiMarket', 'ALL_TARGETS_2026-07-07.json');
  if (existsSync(mmPath)) {
    const mm = JSON.parse(readFileSync(mmPath, 'utf8'));
    for (const r of mm) {
      const e = normalizeEmail(r.email);
      if (validEmail(e) && !prospects.some(p => p.email === e)) {
        prospects.push({
          company: r.company || '',
          email: e,
          pain: r.pain || '',
          deal_value: r.deal || '',
          market: r.market || '',
          source: 'multi_market',
          category: 'ai_prospect',
        });
      }
    }
  }

  // 2. New targets (22 with emails)
  const ntPath = join(MBM, 'Targets', 'NEW_TARGETS_2026-07-07.json');
  if (existsSync(ntPath)) {
    const nt = JSON.parse(readFileSync(ntPath, 'utf8'));
    for (const r of nt) {
      const e = normalizeEmail(r.contact || '');
      if (validEmail(e) && r.status !== 'bounced' && !prospects.some(p => p.email === e)) {
        prospects.push({
          company: r.company || '',
          email: e,
          phone: r.phone || '',
          website: r.website || '',
          pain: r.pain || '',
          solution: r.solution || '',
          deal_value: r.deal_value || '',
          source: 'new_targets',
          category: 'ai_prospect',
        });
      }
    }
  }

  return prospects;
}

const BUYER_TEMPLATE = (lead, pricing) => ({
  subject: `Daily DFW Distressed Seller & Wholesaler Leads — Special 25% Off`,
  body: `Hi${lead.name ? ' ' + lead.name : ''},

I run a lead generation service focused on the DFW real estate market. We pull fresh, daily leads from public records including:

- Dallas 311 code violations (distressed sellers)
- OpenStreetMap verified wholesalers
- RealEstateBees, HouseCashin, KeyCrew directories
- BiggerPockets active investors

What we deliver every morning by 9 AM CT:

1. Seller Leads (300-600/day): Property addresses, owner names, distress signals, confidence scores
2. Buyer/Wholesaler Leads (50-100/day): Company names, contacts, websites, verified sources

I'd love to send you a free sample pack so you can see the quality. No strings attached.

SPECIAL LAUNCH PRICING — 25% OFF:
- Single pack (seller OR buyer): $${pricing.single_day}/day (reg $25)
- Full pack (both): $${pricing.full_day}/day (reg $40)
- Monthly subscription: $${pricing.monthly}/month (reg $500)

Are you open to a quick 5-minute call this week? I can walk you through the data and send over a sample.

Best,
Mohammed Abdelshafy
+201040404118
abdelshafyclapps@gmail.com`,
});

const SELLER_TEMPLATE = (lead) => ({
  subject: `We want to buy your property at ${lead.address.split(',')[0] || lead.address} — Cash Offer`,
  body: `Hi ${lead.owner || 'Property Owner'},

We noticed your property at ${lead.address} has some code concerns that we can help with.

We buy houses AS-IS. No repairs, no cleaning, no realtor fees. You don't need to fix anything.

OUR OFFER: 25% above other cash buyer quotes — we pay more than the competition.
Cash payment, close in as fast as 7 days, you choose the closing date.

If you're interested in a no-obligation cash offer, reply to this email or call/text +201040404118.

Best,
Mohammed Abdelshafy
+201040404118`,
});

const AI_TEMPLATE = (lead) => ({
  subject: `AI Automation for ${lead.company || 'Your Business'} — Cut Costs, Boost Profits`,
  body: `Hi${lead.company ? ' ' + lead.company.split(' ')[0] : ' there'},

I noticed ${lead.company || 'your company'} could benefit from AI-powered automation.

What I can do for you:
• Automate email outreach and lead follow-ups (save 20+ hrs/week)
• AI lead qualification and scoring (no more manual filtering)
• Automated deal matching — connect sellers to buyers instantly
• Smart CRM pipeline management with predictive analytics
${lead.pain ? `• Address your specific challenge: ${lead.pain}` : ''}

Results my clients are seeing:
- 60% reduction in manual data entry
- 3x faster lead response times
- 40% lower operational costs
- 25% increase in closed deals

First week free setup + 30-day money-back guarantee.

Want to see a 5-min demo of what this would look like for ${lead.company || 'your business'}?

Best,
Mohammed Abdelshafy
+201040404118
abdelshafyclapps@gmail.com`,
});

export async function queueBuyerCampaign({ supabase, pricing = { single_day: 18, full_day: 30, monthly: 375 } } = {}) {
  const buyers = loadBuyers();
  console.log(`[buyer-campaign] Loaded ${buyers.length} buyer leads`);

  if (!supabase) {
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!key) throw new Error('SUPABASE_SERVICE_ROLE_KEY required');
    supabase = createClient(
      process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co',
      key,
    );
  }

  let queued = 0, skipped = 0;
  for (const lead of buyers) {
    const { subject, body } = BUYER_TEMPLATE(lead, pricing);
    const { error } = await supabase.from('email_queue').insert({
      recipient_email: lead.email,
      subject,
      body,
      status: 'qued',
    });
    if (error) {
      console.log(`  [SKIP] ${lead.email}: ${error.message}`);
      skipped++;
    } else {
      queued++;
    }
  }

  console.log(`[buyer-campaign] Queued ${queued}, skipped ${skipped}`);
  return { queued, skipped, total: buyers.length };
}

export async function queueAICampaign({ supabase } = {}) {
  const prospects = loadAIProspects();
  console.log(`[ai-campaign] Loaded ${prospects.length} AI prospects`);

  if (!supabase) {
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!key) throw new Error('SUPABASE_SERVICE_ROLE_KEY required');
    supabase = createClient(
      process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co',
      key,
    );
  }

  let queued = 0, skipped = 0;
  for (const lead of prospects) {
    const { subject, body } = AI_TEMPLATE(lead);
    const { error } = await supabase.from('email_queue').insert({
      recipient_email: lead.email,
      subject,
      body,
      status: 'qued',
    });
    if (error) {
      console.log(`  [SKIP] ${lead.email}: ${error.message}`);
      skipped++;
    } else {
      queued++;
    }
  }

  console.log(`[ai-campaign] Queued ${queued}, skipped ${skipped}`);
  return { queued, skipped, total: prospects.length };
}

export function generateSellerWhatsAppReport() {
  const sellers = loadSellers();
  const outputDir = join(ROOT, 'reports');
  mkdirSync(outputDir, { recursive: true });

  const withPhone = sellers.filter(s => s.phone).sort((a, b) => b.score - a.score);
  const needsSkiptrace = sellers.filter(s => s.needs_skiptrace || (!s.phone && !s.email));

  let md = `# Seller Outreach Report — ${new Date().toISOString().split('T')[0]}

## Summary
- Total seller leads: ${sellers.length}
- With phone numbers (WhatsApp-ready): ${withPhone.length}
- Need skip-trace (no phone/email): ${needsSkiptrace.length}

---

## WhatsApp Outreach (${withPhone.length} leads)
Send WhatsApp messages to +201040404118 with these offers:

| # | Owner | Phone | Address | Distress | Priority | Offer Message |
|---|---|---|---|---|---|---|
`;
  withPhone.forEach((s, i) => {
    const msg = `Hi ${s.owner || 'there'}, we buy houses AS-IS at ${s.address.split(',')[0] || s.address}. Cash offer, close in 7 days. Reply for a free quote!`;
    md += `| ${i + 1} | ${s.owner || 'N/A'} | ${s.phone} | ${s.address} | ${s.distress} | ${s.priority} | ${msg} |\n`;
  });

  md += `
---

## Skip-Trace Candidates (${needsSkiptrace.length} leads)
These leads have property addresses but no phone/email. Use skip-tracing to find contact info:

| # | Address | City | Distress |
|---|---|---|---|
`;
  needsSkiptrace.forEach((s, i) => {
    md += `| ${i + 1} | ${s.address} | ${s.city} | ${s.distress} |\n`;
  });

  const reportPath = join(outputDir, `seller_whatsapp_${new Date().toISOString().split('T')[0]}.md`);
  writeFileSync(reportPath, md, 'utf8');
  console.log(`[seller-report] Generated: ${reportPath} (${withPhone.length} whatsapp-ready, ${needsSkiptrace.length} need skip-trace)`);

  return { reportPath, whatsappReady: withPhone.length, needsSkiptrace: needsSkiptrace.length, total: sellers.length };
}

export async function queueSellerCampaign({ supabase } = {}) {
  const sellers = loadSellers();

  if (!supabase) {
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!key) throw new Error('SUPABASE_SERVICE_ROLE_KEY required');
    supabase = createClient(
      process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co',
      key,
    );
  }

  const withEmail = sellers.filter(s => validEmail(s.email));

  let queued = 0;
  for (const lead of withEmail) {
    const { subject, body } = SELLER_TEMPLATE(lead);
    const { error } = await supabase.from('email_queue').insert({
      recipient_email: lead.email,
      subject,
      body,
      status: 'qued',
    });
    if (!error) queued++;
  }

  const report = generateSellerWhatsAppReport();

  console.log(`[seller-campaign] Emails queued: ${queued}, WhatsApp-ready: ${report.whatsappReady}, Skip-trace needed: ${report.needsSkiptrace}`);
  return { queued, ...report };
}

export function loadStats() {
  const buyers = loadBuyers();
  const sellers = loadSellers();
  const aiProspects = loadAIProspects();
  return {
    buyers: { total: buyers.length, withEmail: buyers.filter(b => validEmail(b.email)).length },
    sellers: { total: sellers.length, withPhone: sellers.filter(s => s.phone).length, withEmail: sellers.filter(s => validEmail(s.email)).length, needsSkiptrace: sellers.filter(s => s.needs_skiptrace || (!s.phone && !s.email)).length },
    aiProspects: { total: aiProspects.length, withEmail: aiProspects.filter(p => validEmail(p.email)).length },
  };
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--stats')) {
    const stats = loadStats();
    console.log(JSON.stringify(stats, null, 2));
    return;
  }

  if (args.includes('--buyers')) {
    const r = await queueBuyerCampaign();
    console.log('RESULT:', JSON.stringify(r));
  }

  if (args.includes('--sellers')) {
    const r = await queueSellerCampaign();
    console.log('RESULT:', JSON.stringify(r));
  }

  if (args.includes('--ai')) {
    const r = await queueAICampaign();
    console.log('RESULT:', JSON.stringify(r));
  }

  if (args.includes('--all') || args.length === 0) {
    console.log('\n=== LEAD PIPELINE — FULL RUN ===\n');
    const stats = loadStats();
    console.log('LEAD STATS:', JSON.stringify(stats, null, 2));

    const buyerR = await queueBuyerCampaign();
    console.log('\n---');

    const sellerR = await queueSellerCampaign();
    console.log('\n---');

    const aiR = await queueAICampaign();
    console.log('\n---');

    console.log('\n=== PIPELINE COMPLETE ===');
    console.log('Buyers queued:', buyerR.queued);
    console.log('Seller emails queued:', sellerR.queued);
    console.log('Seller WhatsApp report:', sellerR.reportPath);
    console.log('AI prospects queued:', aiR.queued);
    console.log(`Total queued: ${buyerR.queued + sellerR.queued + aiR.queued}`);
  }

  if (!args.length || args.includes('--help')) {
    console.log(`
Usage:
  node server/leadPipeline.js --stats    # Show lead counts
  node server/leadPipeline.js --buyers   # Queue lead pack offers to buyers
  node server/leadPipeline.js --sellers  # Queue house offers + generate WhatsApp report
  node server/leadPipeline.js --ai       # Queue AI automation offers
  node server/leadPipeline.js --all      # Run full pipeline
    `);
  }
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
