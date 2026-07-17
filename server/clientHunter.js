import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });
import { createClient } from '@supabase/supabase-js';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const MBM = join(ROOT, 'MBM');

const TEMPLATES = {
  initial: (lead) => ({
    subject: `AI Automation for ${lead.company || 'Your Business'} — Free Demo & ROI Analysis`,
    body: `Hi${lead.name ? ' ' + lead.name : ''},

I've been analyzing how AI can transform operations for companies like ${lead.company || 'yours'} in the ${lead.market || 'real estate'} space.

${lead.pain ? `I noticed a key challenge: ${lead.pain}. ` : ''}Here's how MBM AI can help:
• Automated email outreach & follow-ups — save 20+ hrs/week
• AI lead qualification & scoring — stop manual filtering
• Smart deal matching — connect sellers to buyers instantly
• CRM pipeline automation — predictive analytics built in
${lead.solution ? `• ${lead.solution}\n` : ''}
Results my clients are seeing:
✓ 60% reduction in manual data entry
✓ 3x faster lead response times
✓ 40% lower operational costs
✓ 25% increase in closed deals

I put together a personalized demo page for ${lead.company || 'your business'}: ${ROOT}/demo?ref=${encodeURIComponent(lead.email || 'prospect')}

First week free + 30-day money-back guarantee. Setup in 48 hours.

Worth a 10-min call this week?

Best,
Mohammed Abdelshafy
+201040404118
abdelshafyclapps@gmail.com`,
  }),

  followup: (lead) => ({
    subject: `Quick question about ${lead.company || 'your operations'}`,
    body: `Hi${lead.name ? ' ' + lead.name : ''},

Just following up on my previous message about AI automation for ${lead.company || 'your business'}.

I know you're busy — I wanted to share a quick 2-min demo video showing exactly how this works:

See it here: ${ROOT}/demo?ref=${encodeURIComponent(lead.email || 'prospect')}

The short version:
→ We automate your lead gen, email outreach, and CRM
→ Average client saves 20+ hrs/week
→ First week free, 30-day guarantee

Would you be open to a brief call this week to see if this is a fit?

Best,
Mohammed Abdelshafy
+201040404118`,
  }),

  lead_pack: (lead) => ({
    subject: `Daily DFW Distressed & Wholesaler Leads — Special Pricing`,
    body: `Hi${lead.name ? ' ' + lead.name : ''},

I run a lead generation service focused on the DFW real estate market. We pull fresh, daily leads from public records:

• Dallas 311 code violations (distressed sellers)
• Verified wholesalers & active investors
• RealEstateBees, HouseCashin, KeyCrew directories

What you get every morning by 9 AM CT:
1. Seller Leads (300-600/day): Property addresses, owner names, distress signals, scores
2. Buyer/Wholesaler Leads (50-100/day): Company names, contacts, websites

SPECIAL LAUNCH PRICING:
• Single pack: $18/day (reg $25)
• Full pack: $30/day (reg $40)
• Monthly: $375/mo (reg $500)

Want a free sample pack to see the quality?

Best,
Mohammed Abdelshafy
+201040404118`,
  }),
};

function loadAllTargets() {
  const targets = [];
  const seen = new Set();

  function add(t, source) {
    const key = t.email || t.contact || `${t.company}_${t.phone}`;
    if (!key || seen.has(key)) return;
    seen.add(key);
    targets.push(t);
  }

  // MultiMarket targets (44 entries)
  const mmPath = join(MBM, 'MultiMarket', 'ALL_TARGETS_2026-07-07.json');
  if (existsSync(mmPath)) {
    const mm = JSON.parse(readFileSync(mmPath, 'utf8'));
    for (const r of mm) {
      add({
        company: r.company || '',
        email: r.email || '',
        pain: r.pain || '',
        deal: r.deal || '',
        market: r.market || '',
        name: '',
        phone: '',
        source: 'multi_market',
      }, 'multi_market');
    }
  }

  // NEW_TARGETS (22 entries)
  const ntPath = join(MBM, 'Targets', 'NEW_TARGETS_2026-07-07.json');
  if (existsSync(ntPath)) {
    const nt = JSON.parse(readFileSync(ntPath, 'utf8'));
    for (const r of nt) {
      add({
        company: r.company || '',
        email: r.contact || '',
        phone: r.phone || '',
        pain: r.pain || '',
        solution: r.solution || '',
        deal: r.deal_value || '',
        name: '',
        market: '',
        source: 'new_targets',
        status: r.status || 'active',
      }, 'new_targets');
    }
  }

  // Pipeline contacts
  const plPath = join(MBM, 'Pipeline', 'pipeline.csv');
  if (existsSync(plPath)) {
    const lines = readFileSync(plPath, 'utf8').replace(/^\uFEFF/, '').split('\n').filter(l => l.trim());
    if (lines.length > 1) {
      const headers = lines[0].split(',').map(h => h.trim());
      for (let i = 1; i < lines.length; i++) {
        const vals = lines[i].split(',').map(v => v.trim());
        const r = {};
        headers.forEach((h, j) => { r[h] = vals[j] || ''; });
        add({
          company: r.company || '',
          email: r.email || '',
          phone: r.phone || '',
          deal: r.deal_value || '',
          name: '',
          pain: '',
          market: '',
          source: 'pipeline',
          stage: r.stage || '',
        }, 'pipeline');
      }
    }
  }

  // Wholesaler contacts
  const wcPath = join(MBM, 'Contacts', 'wholesaler_targets.csv');
  if (existsSync(wcPath)) {
    const lines = readFileSync(wcPath, 'utf8').replace(/^\uFEFF/, '').split('\n').filter(l => l.trim());
    if (lines.length > 1) {
      const headers = lines[0].split(',').map(h => h.trim());
      for (let i = 1; i < lines.length; i++) {
        const vals = lines[i].split(',').map(v => v.trim());
        const r = {};
        headers.forEach((h, j) => { r[h] = vals[j] || ''; });
        add({
          company: r.company || '',
          email: r.email || '',
          phone: r.phone || '',
          name: '',
          pain: '',
          deal: '',
          market: '',
          source: 'contacts',
        }, 'contacts');
      }
    }
  }

  // Qualified buyers
  const qbPath = join(MBM, 'Artifacts', 'wholesalers_final_qualified.csv');
  if (existsSync(qbPath)) {
    const lines = readFileSync(qbPath, 'utf8').replace(/^\uFEFF/, '').split('\n').filter(l => l.trim());
    if (lines.length > 1) {
      const headers = lines[0].split(',').map(h => h.replace(/^"|"$/g, '').trim());
      for (let i = 1; i < lines.length; i++) {
        const vals = [];
        let inQ = false, cur = '';
        for (const ch of lines[i]) {
          if (ch === '"') { inQ = !inQ; continue; }
          if (ch === ',' && !inQ) { vals.push(cur.trim()); cur = ''; continue; }
          cur += ch;
        }
        vals.push(cur.trim());
        const r = {};
        headers.forEach((h, j) => { r[h] = vals[j] || ''; });
        add({
          company: r.Company || '',
          email: r.Email || '',
          phone: r.Phone || '',
          name: r.Contact_Name || '',
          pain: '',
          deal: '',
          market: r.City || '',
          source: 'qualified_buyers',
        }, 'qualified_buyers');
      }
    }
  }

  console.log(`[hunter] Loaded ${targets.length} total targets from all sources`);
  return targets;
}

function validEmail(e) {
  if (!e) return false;
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
}

function getTemplateForLead(lead) {
  if (lead.source === 'pipeline') {
    if (lead.stage === 'bounced') return 'followup';
    return 'initial';
  }
  if (lead.status === 'bounced') return 'followup';
  if (lead.pain?.toLowerCase().includes('lead') || lead.pain?.toLowerCase().includes('deal')) return 'lead_pack';
  return 'initial';
}

export async function hunt({ template, supabase, dryRun = false, limit = 0 } = {}) {
  const allTargets = loadAllTargets();
  const valid = allTargets.filter(t => validEmail(t.email) && t.source !== 'pipeline');

  const toSend = limit > 0 ? valid.slice(0, limit) : valid;
  console.log(`[hunter] Will process ${toSend.length} targets (${dryRun ? 'DRY RUN' : 'LIVE'})`);

  if (!supabase && !dryRun) {
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!key) throw new Error('SUPABASE_SERVICE_ROLE_KEY required');
    supabase = createClient(
      process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co',
      key,
    );
  }

  let queued = 0, skipped = 0, bounced = 0;
  const results = [];

  for (const lead of toSend) {
    const tplName = template || getTemplateForLead(lead);
    const tplFn = TEMPLATES[tplName];
    if (!tplFn) {
      console.log(`  [SKIP] ${lead.email}: unknown template "${tplName}"`);
      skipped++;
      continue;
    }

    const { subject, body } = tplFn(lead);

    if (dryRun) {
      results.push({
        email: lead.email,
        company: lead.company,
        template: tplName,
        subject,
        preview: body.slice(0, 100) + '...',
      });
      queued++;
      continue;
    }

    const { error } = await supabase.from('email_queue').insert({
      recipient_email: lead.email,
      subject,
      body,
      status: 'qued',
    });

    if (error) {
      if (error.message?.includes('bounce') || error.message?.includes('invalid')) {
        bounced++;
      } else {
        console.log(`  [SKIP] ${lead.email}: ${error.message}`);
        skipped++;
      }
    } else {
      queued++;
    }

    // Small delay between sends
    await new Promise(r => setTimeout(r, 50));
  }

  return { queued, skipped, bounced, total: allTargets.length, results };
}

export function generateHuntReport(results) {
  const date = new Date().toISOString().split('T')[0];
  const outputDir = join(MBM, 'Reports');
  mkdirSync(outputDir, { recursive: true });

  let md = `# Client Hunt Report — ${date}

## Summary
- Total targets loaded: ${results.total}
- Emails queued: ${results.queued}
- Skipped: ${results.skipped}
- Bounced: ${results.bounced}

## Targets Queued
| # | Company | Email | Template | Subject |
|---|---|---|---|---|
`;
  (results.results || []).forEach((r, i) => {
    md += `| ${i + 1} | ${r.company || 'N/A'} | ${r.email} | ${r.template} | ${r.subject} |\n`;
  });

  const reportPath = join(outputDir, `hunt_report_${date}.md`);
  writeFileSync(reportPath, md, 'utf8');
  console.log(`[hunter] Report saved: ${reportPath}`);
  return reportPath;
}

function getStats() {
  const targets = loadAllTargets();
  const withEmail = targets.filter(t => validEmail(t.email));
  const bySource = {};
  targets.forEach(t => {
    bySource[t.source] = (bySource[t.source] || 0) + 1;
  });
  return {
    total: targets.length,
    withEmail: withEmail.length,
    bySource,
  };
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--stats')) {
    const s = getStats();
    console.log('\n=== CLIENT HUNTER STATS ===');
    console.log(JSON.stringify(s, null, 2));
    return;
  }

  if (args.includes('--dry-run')) {
    const limitIdx = args.indexOf('--limit');
    const limit = limitIdx >= 0 ? parseInt(args[limitIdx + 1]) : 0;
    const result = await hunt({ dryRun: true, limit });
    console.log(`\n=== DRY RUN: ${result.queued} targets ready ===`);
    result.results.slice(0, 5).forEach(r => {
      console.log(`\n--- ${r.company} (${r.email}) ---`);
      console.log(`Template: ${r.template}`);
      console.log(`Subject: ${r.subject}`);
      console.log(`Preview: ${r.preview}`);
    });
    if (result.results.length > 5) {
      console.log(`\n... and ${result.results.length - 5} more`);
    }
    return;
  }

  if (args.includes('--send')) {
    const templateIdx = args.indexOf('--template');
    const template = templateIdx >= 0 ? args[templateIdx + 1] : null;
    const limitIdx = args.indexOf('--limit');
    const limit = limitIdx >= 0 ? parseInt(args[limitIdx + 1]) : 0;
    console.log('\n=== CLIENT HUNTER — LIVE SEND ===\n');
    const result = await hunt({ template, limit });
    console.log(`\nResults: ${JSON.stringify(result, null, 2)}`);
    if (result.queued > 0) {
      console.log('\nTriggering email send...');
      const { sendEmailQueue } = await import('./emailSender.js');
      const sendResult = await sendEmailQueue({ batchSize: 5000, continuous: false });
      console.log(`Send result: ${JSON.stringify(sendResult)}`);
    }
    return;
  }

  if (args.includes('--report')) {
    const result = await hunt({ dryRun: true });
    const path = generateHuntReport(result);
    console.log(`Report: ${path}`);
    return;
  }

  console.log(`
╔═══════════════════════════════════════════╗
║         MBM CLIENT HUNTER v1.0           ║
╚═══════════════════════════════════════════╝

USAGE:
  node server/clientHunter.js --stats     # Show target counts
  node server/clientHunter.js --dry-run   # Preview what would be sent
  node server/clientHunter.js --dry-run --limit 10
  node server/clientHunter.js --send      # Send outreach to ALL targets
  node server/clientHunter.js --send --template followup --limit 20
  node server/clientHunter.js --report    # Generate hunt report

TEMPLATES:
  initial    — First outreach, AI automation pitch
  followup   — Follow-up for bounced/no-reply targets
  lead_pack  — Lead generation service offer

SOURCES:
  MultiMarket | NEW_TARGETS | Pipeline | Contacts | Qualified Buyers
`);
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
