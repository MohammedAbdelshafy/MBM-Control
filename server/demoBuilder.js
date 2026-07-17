/**
 * Demo Builder — generates personalized demo pages for specific companies.
 *
 * Takes a company name, pain points, and solution, then generates
 * a custom HTML landing page that can be hosted or emailed directly.
 *
 * Usage:
 *   node server/demoBuilder.js --company "PipHouse LLC" --email PipHousellc@gmail.com
 *   node server/demoBuilder.js --company "New Western" --pain "Scaling matching" --solution "AI Pipeline Automation" --email sales@newwestern.com
 *   node server/demoBuilder.js --batch    # Generate for all targets
 */

import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });
import { createClient } from '@supabase/supabase-js';
import { readFileSync, writeFileSync, existsSync, mkdirSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const OUTPUT_DIR = join(ROOT, 'public', 'demo-pages');
mkdirSync(OUTPUT_DIR, { recursive: true });

const SOLUTIONS = {
  'AI Email Automation': {
    tagline: 'Draft, schedule & send — on autopilot',
    description: 'Personalized email sequences that nurture leads, follow up automatically, and close deals while you sleep.',
    savings: '20+ hrs/week',
    icon: '✉️',
  },
  'AI Lead Generation': {
    tagline: 'Fresh leads every morning',
    description: 'Daily distressed seller & qualified buyer lists from public records. Delivered to your inbox by 9 AM.',
    savings: '15+ hrs/week',
    icon: '🎯',
  },
  'AI CRM Automation': {
    tagline: 'Never drop a deal again',
    description: 'Automated deal matching, pipeline tracking, predictive analytics. Connect sellers to buyers instantly.',
    savings: '10+ hrs/week',
    icon: '📊',
  },
  'AI Chatbot': {
    tagline: '24/7 answering, zero overhead',
    description: 'Website chatbot that answers questions, books showings, screens tenants, and qualifies leads around the clock.',
    savings: '30+ hrs/week',
    icon: '🤖',
  },
  'AI Content Factory': {
    tagline: 'Viral videos, auto-published',
    description: 'Autonomous video clipping engine. Finds viral moments, adds captions, publishes everywhere.',
    savings: '25+ hrs/week',
    icon: '🎬',
  },
  'AI Deal Analysis': {
    tagline: 'Underwrite in seconds, not hours',
    description: 'Automated deal analysis with ARV, repair costs, ROI projections. Make smarter offers faster.',
    savings: '8+ hrs/week',
    icon: '📈',
  },
};

function slug(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function buildDemoPage({ company, name, pain, solution, email, dealValue }) {
  const solutionInfo = SOLUTIONS[solution] || {
    tagline: 'AI-Powered Automation',
    description: 'Automate your operations — lead gen, email, CRM, and more.',
    savings: '20+ hrs/week',
    icon: '⚡',
  };

  const page = `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${company} — Personalized Demo | MBM AI</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    * { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
    .gradient-text { background: linear-gradient(135deg, #a855f7, #ec4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .gradient-bg { background: linear-gradient(135deg, #1a1a2e, #16213e); }
  </style>
</head>
<body class="bg-[#0a0a1a] text-white min-h-screen">
  <!-- Nav -->
  <nav class="border-b border-white/5 px-4 py-3">
    <div class="max-w-4xl mx-auto flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="text-purple-400 text-lg">⚡</span>
        <span class="font-bold text-sm">MBM <span class="text-purple-400">AI</span></span>
      </div>
      <a href="mailto:abdelshafyclapps@gmail.com?subject=Demo%20for%20${encodeURIComponent(company)}" class="text-xs text-gray-400 hover:text-white">Contact</a>
    </div>
  </nav>

  <!-- Hero -->
  <section class="max-w-4xl mx-auto px-4 pt-16 pb-12 text-center">
    <div class="inline-flex items-center gap-1.5 bg-purple-500/10 border border-purple-500/20 rounded-full px-3 py-1 mb-6">
      <span class="text-[10px] text-purple-300 font-medium">Personalized Demo for ${company}</span>
    </div>

    <h1 class="text-3xl md:text-5xl font-bold leading-tight mb-4">
      Here's How AI Can Transform<br/>
      <span class="gradient-text">${company}</span>
    </h1>

    <p class="text-sm md:text-base text-gray-400 max-w-2xl mx-auto mb-8 leading-relaxed">
      Hi${name ? ' ' + name : ''}, we analyzed how ${company} operates and built a custom AI solution to address your specific challenges.
    </p>

    <img src="https://placehold.co/800x450/1a1a2e/a855f7?text=${encodeURIComponent(company + ' - Demo')}" alt="${company} Demo" class="w-full max-w-2xl mx-auto rounded-2xl border border-white/10 shadow-2xl" />
  </section>

  <!-- Pain Point -->
  <section class="border-y border-white/5 bg-[#111125]/50 py-12">
    <div class="max-w-4xl mx-auto px-4">
      <div class="grid md:grid-cols-2 gap-8 items-center">
        <div>
          <span class="text-[10px] text-purple-400 font-semibold uppercase tracking-wider">Our Analysis</span>
          <h2 class="text-xl md:text-2xl font-bold mt-2 mb-3">We Identified Your Key Challenge</h2>
          <div class="bg-red-500/10 border border-red-500/20 rounded-xl p-4">
            <p class="text-sm text-red-300">${pain || 'Manual processes eating up time and slowing growth'}</p>
          </div>
          <div class="mt-4 space-y-2">
            <div class="flex items-start gap-2 text-xs text-gray-400">
              <span class="text-green-400 mt-0.5">✓</span>
              <span>This is costing your team <strong class="text-white">15-25 hours per week</strong> in manual work</span>
            </div>
            <div class="flex items-start gap-2 text-xs text-gray-400">
              <span class="text-green-400 mt-0.5">✓</span>
              <span>Delaying response times and <strong class="text-white">losing deals</strong> to faster competitors</span>
            </div>
            <div class="flex items-start gap-2 text-xs text-gray-400">
              <span class="text-green-400 mt-0.5">✓</span>
              <span>Preventing you from <strong class="text-white">scaling operations</strong> without adding headcount</span>
            </div>
          </div>
        </div>
        <div class="bg-[#0a0a1a] border border-white/5 rounded-2xl p-6">
          <div class="text-center mb-4">
            <span class="text-3xl mb-2 block">${solutionInfo.icon}</span>
            <h3 class="text-sm font-bold">Recommended Solution</h3>
          </div>
          <h4 class="text-lg font-bold text-purple-400 mb-1">${solution}</h4>
          <p class="text-xs text-gray-400 mb-1">${solutionInfo.tagline}</p>
          <p class="text-xs text-gray-500 leading-relaxed mb-4">${solutionInfo.description}</p>
          <div class="bg-green-500/10 text-green-400 text-xs px-3 py-1.5 rounded-lg inline-block font-medium">
            Saves ${solutionInfo.savings}
          </div>
        </div>
      </div>
    </div>
  </section>

  <!-- ROI Calculator -->
  <section class="max-w-4xl mx-auto px-4 py-12">
    <h2 class="text-xl md:text-2xl font-bold text-center mb-6">Your Estimated ROI</h2>
    <div class="grid md:grid-cols-3 gap-4">
      <div class="bg-[#111125]/80 border border-white/5 rounded-xl p-5 text-center">
        <p class="text-2xl font-bold text-green-400">${solutionInfo.savings}</p>
        <p class="text-[10px] text-gray-500 mt-1">Time Saved Per Week</p>
      </div>
      <div class="bg-[#111125]/80 border border-white/5 rounded-xl p-5 text-center">
        <p class="text-2xl font-bold text-purple-400">${dealValue || '$4,000-6,000'}</p>
        <p class="text-[10px] text-gray-500 mt-1">Estimated Annual Savings</p>
      </div>
      <div class="bg-[#111125]/80 border border-white/5 rounded-xl p-5 text-center">
        <p class="text-2xl font-bold text-blue-400">30 Days</p>
        <p class="text-[10px] text-gray-500 mt-1">Free Trial + Setup</p>
      </div>
    </div>
  </section>

  <!-- CTA -->
  <section class="max-w-2xl mx-auto px-4 pb-16">
    <div class="bg-gradient-to-br from-purple-900/30 to-pink-900/20 border border-purple-500/20 rounded-2xl p-6 md:p-8 text-center">
      <h2 class="text-lg font-bold mb-2">Ready to See This in Action?</h2>
      <p class="text-sm text-gray-400 mb-6">
        Let's set up a 15-minute call to walk through exactly how this works for ${company}.
      </p>
      <a href="mailto:abdelshafyclapps@gmail.com?subject=Demo%20Call%20-%20${encodeURIComponent(company)}&body=Hi%20Mohammed%2C%0A%0AI'd%20like%20to%20schedule%20a%20demo%20call%20for%20${encodeURIComponent(company)}.%0A%0ABest%2C%0A${name ? encodeURIComponent(name) : ''}"
         class="bg-purple-600 hover:bg-purple-500 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-all inline-flex items-center gap-2">
        📞 Book Your Demo Call
      </a>
      <p class="text-[10px] text-gray-600 mt-3">First week free · 30-day guarantee · Setup in 48 hours</p>
    </div>
  </section>

  <!-- Footer -->
  <footer class="border-t border-white/5 py-6">
    <div class="max-w-4xl mx-auto px-4 text-center text-[10px] text-gray-600">
      <p>Powered by MBM AI · abdelshafyclapps@gmail.com · +201040404118</p>
    </div>
  </footer>
</body>
</html>`;

  return page;
}

function loadAllTargets() {
  const MBM = join(ROOT, 'MBM');
  const targets = [];
  const seen = new Set();

  // MultiMarket targets
  const mmPath = join(MBM, 'MultiMarket', 'ALL_TARGETS_2026-07-07.json');
  if (existsSync(mmPath)) {
    const mm = JSON.parse(readFileSync(mmPath, 'utf8'));
    for (const r of mm) {
      const key = r.email;
      if (!key || seen.has(key)) continue;
      seen.add(key);
      targets.push({ company: r.company, email: r.email, pain: r.pain, deal: r.deal, market: r.market, solution: 'AI Email Automation' });
    }
  }

  // NEW_TARGETS
  const ntPath = join(MBM, 'Targets', 'NEW_TARGETS_2026-07-07.json');
  if (existsSync(ntPath)) {
    const nt = JSON.parse(readFileSync(ntPath, 'utf8'));
    for (const r of nt) {
      const key = r.contact || r.company;
      if (!key || seen.has(key)) continue;
      seen.add(key);
      targets.push({ company: r.company, email: r.contact, pain: r.pain, solution: r.solution || 'AI Automation', deal: r.deal_value, market: '' });
    }
  }

  return targets;
}

export async function generateAllDemoPages({ supabase, queueEmail = false } = {}) {
  const targets = loadAllTargets();
  console.log(`\n=== DEMO BUILDER — Generating ${targets.length} pages ===\n`);

  let built = 0;
  for (const t of targets) {
    const page = buildDemoPage({
      company: t.company || 'Your Business',
      email: t.email || '',
      pain: t.pain || 'Manual processes slowing growth',
      solution: t.solution || 'AI Email Automation',
      dealValue: t.deal || '$4,000-6,000',
    });

    const filename = `${slug(t.company || 'prospect')}.html`;
    const filepath = join(OUTPUT_DIR, filename);
    writeFileSync(filepath, page, 'utf8');
    built++;

    if (queueEmail && supabase && t.email) {
      const demoUrl = `/demo-pages/${filename}`;
      await supabase.from('email_queue').insert({
        recipient_email: t.email,
        subject: `${t.company} — Your Personalized AI Demo is Ready`,
        body: `Hi,

I put together a personalized demo page for ${t.company} showing exactly how AI automation can help with ${t.pain || 'your operations'}.

View your demo: ${demoUrl}

It shows:
• Your specific challenge and our recommended solution
• Estimated ROI and time savings
• A walkthrough of how it works

First week free, 30-day guarantee, setup in 48 hours.

Worth a look?

Best,
Mohammed Abdelshafy
+201040404118`,
        status: 'qued',
      });
    }
  }

  console.log(`[demo-builder] Built ${built} demo pages in ${OUTPUT_DIR}`);
  return { built };
}

async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--batch')) {
    const queue = args.includes('--queue');
    let supabase = null;
    if (queue) {
      const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
      if (!key) throw new Error('SUPABASE_SERVICE_ROLE_KEY required');
      supabase = createClient(
        process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co',
        key,
      );
    }
    const result = await generateAllDemoPages({ supabase, queueEmail: queue });
    console.log(`\nResult: ${JSON.stringify(result)}`);
    return;
  }

  // Single company demo
  const companyIdx = args.indexOf('--company');
  const emailIdx = args.indexOf('--email');
  const painIdx = args.indexOf('--pain');
  const solutionIdx = args.indexOf('--solution');
  const dealIdx = args.indexOf('--deal');
  const nameIdx = args.indexOf('--name');

  const company = companyIdx >= 0 ? args[companyIdx + 1] : 'Demo Company';
  const email = emailIdx >= 0 ? args[emailIdx + 1] : 'client@example.com';
  const pain = painIdx >= 0 ? args[painIdx + 1] : '';
  const solution = solutionIdx >= 0 ? args[solutionIdx + 1] : 'AI Email Automation';
  const dealValue = dealIdx >= 0 ? args[dealIdx + 1] : '$4,000-6,000';
  const name = nameIdx >= 0 ? args[nameIdx + 1] : '';

  console.log(`\n=== DEMO BUILDER — ${company} ===\n`);

  const page = buildDemoPage({ company, name, pain, solution, email, dealValue });
  const filename = `${slug(company)}.html`;
  const filepath = join(OUTPUT_DIR, filename);
  writeFileSync(filepath, page, 'utf8');

  console.log(`✅ Demo page built: ${filepath}`);
  console.log(`📧 Send to: ${email}`);
  console.log(`\nView it: /demo-pages/${filename}`);

  // Optionally queue email
  if (args.includes('--send')) {
    const key = process.env.SUPABASE_SERVICE_ROLE_KEY;
    if (!key) throw new Error('SUPABASE_SERVICE_ROLE_KEY required');
    const supabase = createClient(
      process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co',
      key,
    );
    const { error } = await supabase.from('email_queue').insert({
      recipient_email: email,
      subject: `${company} — Your Personalized AI Demo is Ready`,
      body: `Hi${name ? ' ' + name : ''},

I put together a personalized demo page for ${company} showing exactly how AI automation can help.

View your demo: http://localhost:5173/demo-pages/${filename}

It shows:
• Your specific challenge and our recommended solution
• Estimated ROI and time savings
• A walkthrough of how it works

First week free, 30-day guarantee.

Worth a look?

Best,
Mohammed Abdelshafy
+201040404118`,
      status: 'qued',
    });
    if (error) console.error('Queue error:', error.message);
    else console.log('📨 Email queued for delivery');
  }
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
