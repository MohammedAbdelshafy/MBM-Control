/**
 * Demo Campaign System — generates app promo demo videos and sends them hourly via email.
 *
 * Creates short promo clips showcasing app features using FFmpeg image-to-video,
 * queues them as email campaigns, and sends via the optimized email queue.
 *
 * Usage:
 *   node server/demoCampaign.js --generate    # Generate all demo videos
 *   node server/demoCampaign.js --campaign    # Queue a promo email campaign
 *   node server/demoCampaign.js --once        # Generate + queue one cycle
 *   node server/demoCampaign.js --daemon      # Run hourly loop
 */
import dotenv from 'dotenv';
dotenv.config({ path: '.env.local' });
dotenv.config({ path: join(dirname(fileURLToPath(import.meta.url)), '..', 'MBM-Social', '.env') });
import { createClient } from '@supabase/supabase-js';
import { spawnSync, spawn } from 'child_process';
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'fs';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');

// ── App promo content ──────────────────────────────────────
const FEATURES = [
  {
    id: 'dealing-room',
    title: 'Dealing Room',
    subtitle: 'Marketplace للمواد القابلة لإعادة التدوير',
    description: 'Buy & sell recyclable materials — plastic, metal, paper, glass, cooking oil. Real-time pricing, direct deals.',
    screenshot: 'posters.png', // fallback image
  },
  {
    id: 'subscriptions',
    title: 'Subscription Management',
    subtitle: 'إدارة الاشتراكات',
    description: 'Trial → paid plans at 100 EGP/month. Track MRR, churn, and conversion in real-time.',
    screenshot: 'posters.png',
  },
  {
    id: 'route-optimization',
    title: 'Smart Route Optimization',
    subtitle: 'تحسين المسارات الذكي',
    description: 'GPS-tracked pickup routes. Assign drivers, track collections live on the map.',
    screenshot: 'posters.png',
  },
  {
    id: 'commissions',
    title: 'Commission Tracking',
    subtitle: 'تتبع العمولات',
    description: 'Track sales rep commissions, split deals, and payouts. Full audit trail.',
    screenshot: 'posters.png',
  },
  {
    id: 'kpi-dashboard',
    title: 'KPI Dashboard',
    subtitle: 'لوحة مؤشرات الأداء',
    description: 'MRR, churn rate, conversion funnel, revenue forecasts — all in one dashboard.',
    screenshot: 'posters.png',
  },
  {
    id: 'ai-clipping',
    title: 'AI Clipping Engine',
    subtitle: 'محرك القص بالذكاء الاصطناعي',
    description: 'Autonomous video clipping. AI finds viral moments, adds captions, publishes everywhere.',
    screenshot: 'posters.png',
  },
];

const INTRO = {
    id: 'intro',
  title: 'Contech AI Agentic teamz',
  subtitle: 'AI-Powered Operations Platform',
  description: 'Waste collection management. Dealing room. AI clipping. One platform.',
  screenshot: 'A0 poster finall.jpeg',
};

const OUTRO = {
  id: 'outro',
  title: 'Get Started Today',
  subtitle: 'ابدأ اليوم',
  description: 'First week free. Contech AI Agentic teamz — Transform your operations with AI.',
  screenshot: 'A0 poster..jpeg',
};

// ── Helpers ────────────────────────────────────────────────

function ffmpegPath() {
  const candidates = [
    'C:\\Users\\omare\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg.Essentials_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-8.1.1-essentials_build\\bin\\ffmpeg.exe',
    'C:\\Users\\omare\\AppData\\Local\\Microsoft\\WinGet\\Packages\\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\\ffmpeg-8.1.1-essentials_build\\bin\\ffmpeg.exe',
    'ffmpeg',
  ];
  for (const f of candidates) {
    try { spawnSync(f, ['-version'], { stdio: 'pipe', timeout: 5000 }); return f; } catch {}
  }
  return 'ffmpeg';
}

function findBestImage() {
  const candidates = [
    join(ROOT, 'A0 poster finall.jpeg'),
    join(ROOT, 'A0 poster..jpeg'),
    join(ROOT, 'posters.png'),
  ];
  for (const f of candidates) {
    if (existsSync(f)) return f;
  }
  return null;
}

function slug(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

// ── Generate AI-powered demo clip via Runware ──────────────
const RUNWARE_PYTHON = join(ROOT, 'ComfyUI', 'venv', 'Scripts', 'python.exe');
const RUNWARE_SCRIPT = join(ROOT, 'scripts', 'runware_generate.py');

function findPython() {
  for (const p of [RUNWARE_PYTHON, join(ROOT, '.venv', 'Scripts', 'python.exe'), 'python', 'python3']) {
    try { spawnSync(p, ['--version'], { stdio: 'pipe', timeout: 5000 }); return p; } catch {}
  }
  return null;
}

async function generateAIDemoClip(feature, outputDir) {
  const outputFile = join(outputDir, `demo_${feature.id}.mp4`);
  if (existsSync(outputFile)) {
    console.log(`  [EXISTS] ${feature.title}: ${outputFile}`);
    return outputFile;
  }

  const python = findPython();
  if (!python) {
    console.log(`  [SKIP-AI] ${feature.title}: no Python found, using image mode`);
    return generateDemoClip(feature, outputDir);
  }

  // Generate a high-quality background image via Runware
  const tempImage = join(outputDir, `demo_${feature.id}_bg.png`);
  const prompt = `App interface screenshot, ${feature.title} screen: ${feature.description}. Clean modern UI dashboard, professional, bright colors, ${feature.subtitle}, high quality, 4k`;

  console.log(`  [AI-IMG] ${feature.title}: generating background via Runware...`);
  const result = spawnSync(python, [
    RUNWARE_SCRIPT,
    '--type', 'image',
    '--prompt', prompt,
    '--model', 'runware:101@1',
    '--width', '1080',
    '--height', '1920',
    '--output', tempImage,
  ], { stdio: 'pipe', timeout: 120000 });

  if (result.error || result.status !== 0 || !existsSync(tempImage)) {
    const err = result.stderr?.toString() || result.error?.message || 'unknown error';
    console.log(`  [FALLBACK] ${feature.title}: Runware failed (${err.slice(0, 100)}), using image mode`);
    return generateDemoClip(feature, outputDir);
  }

  // Overlay text on the generated image using FFmpeg
  console.log(`  [AI-VID] ${feature.title}: overlaying text...`);
  const ff = ffmpegPath();
  const textFilters = [
    `drawtext=text='${feature.title.replace(/'/g, "\\'")}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=h/2-80:box=1:boxcolor=black@0.6:boxborderw=20`,
    `drawtext=text='${feature.subtitle.replace(/'/g, "\\'")}':fontsize=28:fontcolor=#00D4AA:x=(w-text_w)/2:y=h/2+10:box=1:boxcolor=black@0.5:boxborderw=15:enable='gte(t,1)'`,
    `drawtext=text='${feature.description.replace(/'/g, "\\'")}':fontsize=20:fontcolor=white:x=(w-text_w)/2:y=h/2+80:box=1:boxcolor=black@0.4:boxborderw=10:enable='gte(t,3)'`,
  ].join(',');

  const args = ['-y', '-loop', '1', '-i', tempImage, '-vf', textFilters, '-c:v', 'libx264', '-t', '10', '-pix_fmt', 'yuv420p', '-preset', 'ultrafast', outputFile];

  try {
    const encode = spawnSync(ff, args, { stdio: 'pipe', timeout: 30000 });
    if (encode.error || encode.status !== 0) throw new Error(encode.stderr?.toString().slice(0, 200));
    const stat = await import('fs').then(f => f.promises.stat(outputFile).catch(() => null));
    if (stat?.size > 0) {
      console.log(`  [OK] ${feature.title}: ${outputFile} (${(stat.size / 1e6).toFixed(1)}MB)`);
      try { spawnSync('rm', ['-f', tempImage], { stdio: 'pipe' }); } catch { /* ignore cleanup */ }
      return outputFile;
    }
    throw new Error('Empty output');
  } catch (err) {
    console.log(`  [FAIL] ${feature.title}: ${err.message.slice(0, 200)}`);
    return null;
  }
}

// ── Generate a single demo clip from an image + text ───────
async function generateDemoClip(feature, outputDir) {
  const img = feature.screenshot ? join(ROOT, feature.screenshot) : findBestImage();
  if (!img || !existsSync(img)) {
    console.log(`  [SKIP] ${feature.title}: no image found`);
    return null;
  }

  const outputFile = join(outputDir, `demo_${feature.id}.mp4`);
  if (existsSync(outputFile)) {
    console.log(`  [EXISTS] ${feature.title}: ${outputFile}`);
    return outputFile;
  }

  const ff = ffmpegPath();
  // Create a 10-second promo clip: image with text overlay
  // Use filter_complex with drawtext for better text handling
  const textFilters = [
    `drawtext=text='${feature.title.replace(/'/g, "\\'")}':fontsize=48:fontcolor=white:x=(w-text_w)/2:y=h/2-80:box=1:boxcolor=black@0.6:boxborderw=20`,
    `drawtext=text='${feature.subtitle.replace(/'/g, "\\'")}':fontsize=28:fontcolor=#00D4AA:x=(w-text_w)/2:y=h/2+10:box=1:boxcolor=black@0.5:boxborderw=15:enable='gte(t,1)'`,
    `drawtext=text='${feature.description.replace(/'/g, "\\'")}':fontsize=20:fontcolor=white:x=(w-text_w)/2:y=h/2+80:box=1:boxcolor=black@0.4:boxborderw=10:enable='gte(t,3)'`,
  ].join(',');

  const args = [
    '-y',
    '-loop', '1',
    '-i', img,
    '-vf', textFilters,
    '-c:v', 'libx264',
    '-t', '10',
    '-pix_fmt', 'yuv420p',
    '-preset', 'ultrafast',
    outputFile,
  ];

  try {
    const result = spawnSync(ff, args, { stdio: 'pipe', timeout: 30000 });
    if (result.error) throw result.error;
    if (result.status !== 0) {
      const errMsg = result.stderr.toString();
      throw new Error(errMsg.slice(errMsg.indexOf('['), 300) || `exit ${result.status}`);
    }
    const stat = await import('fs').then(fs => fs.promises.stat(outputFile).catch(() => null));
    const size = stat?.size || 0;
    if (size > 0) {
      console.log(`  [OK] ${feature.title}: ${outputFile} (${(size / 1e6).toFixed(1)}MB)`);
      return outputFile;
    }
    console.log(`  [FAIL] ${feature.title}: output file empty (0 bytes)`);
    return null;
  } catch (err) {
    console.log(`  [FAIL] ${feature.title}: ${err.message.slice(0, 200)}`);
    return null;
  }
}

// ── Generate all demo clips ────────────────────────────────
export async function generateAllDemos({ useAI = false } = {}) {
  console.log('\n=== GENERATING DEMO VIDEOS ===\n');
  const outputDir = join(ROOT, 'public', 'demos');
  mkdirSync(outputDir, { recursive: true });

  const generator = (process.env.USE_AI_DEMOS === 'true' || useAI) ? generateAIDemoClip : generateDemoClip;
  const results = [];

  // Intro
  const introFile = await generator(INTRO, outputDir);
  if (introFile) results.push(INTRO.id);

  // Features
  for (const feat of FEATURES) {
    const file = await generator(feat, outputDir);
    if (file) results.push(feat.id);
  }

  // Outro
  const outroFile = await generator(OUTRO, outputDir);
  if (outroFile) results.push(OUTRO.id);

  console.log(`\nGenerated ${results.length}/${FEATURES.length + 2} demo clips\n`);
  return results;
}

// ── Queue a promo email campaign ───────────────────────────
export async function queuePromoCampaign({ supabase, targetEmails = null } = {}) {
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabase) {
    if (!serviceRoleKey) throw new Error('SUPABASE_SERVICE_ROLE_KEY required');
    supabase = createClient(
      process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co',
      serviceRoleKey,
    );
  }

  // Get target emails: either passed in or query from profiles
  if (!targetEmails) {
    // Try common tables for emails
    for (const table of ['profiles', 'users', 'customers', 'subscribers']) {
      try {
        const { data } = await supabase
          .from(table)
          .select('email')
          .not('email', 'is', null)
          .limit(500);
        if (data && data.length > 0) {
          targetEmails = data.map(p => p.email).filter(Boolean);
          break;
        }
      } catch {}
    }
  }

  if (!targetEmails || !targetEmails.length) {
    console.log('[campaign] No target emails found in any table. Use --emails flag or add users.');
    return { queued: 0, warning: 'No email targets found' };
  }

  // Build promo email content with embedded demo video links
  const baseUrl = process.env.APP_URL || 'http://localhost:5173';
  const demoLinks = FEATURES.map(f =>
    `• ${f.title} — ${f.description}\n  Watch: ${baseUrl}/demos/demo_${f.id}.mp4`
  ).join('\n\n');

  // Pick a feature to highlight this hour (rotate through them)
  const hour = new Date().getHours();
  const feature = FEATURES[hour % FEATURES.length];
  const featureVideo = `${baseUrl}/demos/demo_${feature.id}.mp4`;

  const subject = `${feature.title} — Contech AI Agentic teamz Demo`;
  const body = `Contech AI Agentic teamz Demo — ${feature.title}
  
${feature.description}

Watch the demo: ${featureVideo}

---
All Features:
${demoLinks}

---
Contech AI Agentic teamz — Waste Collection Operations
First week free.`;

  const emails = targetEmails.map(email => ({
    recipient_email: email,
    subject,
    body,
  }));

  const { data, error } = await supabase
    .from('email_queue')
    .insert(emails)
    .select('id');

  if (error) throw error;
  console.log(`[campaign] Queued ${data.length} promo emails for "${feature.title}"`);
  return { queued: data.length, feature: feature.title };
}

// ── Daemon: run hourly ─────────────────────────────────────
async function runDaemon() {
  console.log('[demo-daemon] Starting hourly demo campaign daemon...');

  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!serviceRoleKey) {
    console.error('[demo-daemon] SUPABASE_SERVICE_ROLE_KEY not set');
    process.exit(1);
  }
  const supabase = createClient(
    process.env.VITE_SUPABASE_URL || 'https://prgmwljhbjtcjmwnjaao.supabase.co',
    serviceRoleKey,
  );

  // Initial generation
  await generateAllDemos();

  while (true) {
    const now = new Date();
    console.log(`\n[demo-daemon] ${now.toISOString()} — Starting campaign cycle`);

    try {
      // 1. Generate/refresh demos
      await generateAllDemos();

      // 2. Queue promo emails
      const campaign = await queuePromoCampaign({ supabase });
      console.log(`[demo-daemon] Campaign: ${JSON.stringify(campaign)}`);

      // 3. Trigger email sending (continuous mode)
      const { sendEmailQueue: sender } = await import('./emailSender.js');
      const result = await sender({
        supabase,
        batchSize: 5000,
        continuous: false,
      });
      console.log(`[demo-daemon] Email send: ${JSON.stringify(result)}`);

    } catch (err) {
      console.error(`[demo-daemon] Error: ${err.message}`);
    }

    // Wait until next hour
    const next = new Date();
    next.setHours(next.getHours() + 1, 0, 0, 0);
    const waitMs = next.getTime() - Date.now();
    console.log(`[demo-daemon] Next cycle at ${next.toISOString()} (in ${Math.round(waitMs / 60000)} min)`);
    await new Promise(r => setTimeout(r, waitMs));
  }
}

// ── CLI ────────────────────────────────────────────────────
async function main() {
  const args = process.argv.slice(2);

  if (args.includes('--daemon')) {
    await runDaemon();
  } else if (args.includes('--generate')) {
    await generateAllDemos();
  } else if (args.includes('--campaign')) {
    const result = await queuePromoCampaign();
    console.log(JSON.stringify(result));
  } else if (args.includes('--once')) {
    await generateAllDemos();
    const result = await queuePromoCampaign();
    console.log('Campaign:', JSON.stringify(result));
    if (result.queued > 0) {
      const { sendEmailQueue } = await import('./emailSender.js');
      const sendResult = await sendEmailQueue({ batchSize: 5000, continuous: false });
      console.log('Sent:', JSON.stringify(sendResult));
    }
  } else {
    console.log(`
Usage:
  node server/demoCampaign.js --generate    Generate all demo videos
  node server/demoCampaign.js --campaign    Queue hourly promo email campaign
  node server/demoCampaign.js --once        Generate + queue + send one cycle
  node server/demoCampaign.js --daemon      Run hourly daemon (generate → queue → send)
    `);
  }
}

main().catch(err => {
  console.error('FATAL:', err);
  process.exit(1);
});
