import { createClient } from '@supabase/supabase-js';
import { config } from 'dotenv';
config({ path: '.env.local' });

const FEATURES = [
  { id: 'intro', t: 'Contech AI Agentic teamz', d: 'AI-powered waste collection operations' },
  { id: 'dealing-room', t: 'Dealing Room', d: 'Real-time deal pipeline management' },
  { id: 'subscriptions', t: 'Subscription Management', d: 'Automated billing & renewals' },
  { id: 'route-optimization', t: 'Smart Route Optimization', d: 'AI route planning for waste collection' },
  { id: 'commissions', t: 'Commission Tracking', d: 'Automated commission calculations' },
  { id: 'kpi-dashboard', t: 'KPI Dashboard', d: 'Real-time business intelligence' },
  { id: 'ai-clipping', t: 'AI Clipping Engine', d: 'Autonomous video clipping & publishing' },
  { id: 'outro', t: 'Get Started Today', d: 'First week free — see all features' },
];

const LEADS = [
  'info@dfwwholesaleproperties.com', 'info@allwholesaleproperties.com', 'sales@newwestern.com',
  'PipHousellc@gmail.com', 'investments@swifthomesolutions.com', 'diamondacquisitions@outlook.com',
  'info@turnerandpartners.com', 'robin@dfwrei.com', 'info@houstontowholesalehomes.com',
  'info@texashomebuyers.com', 'info@houstonpropertysolutions.com', 'info@bayoucityinvestments.com',
  'info@htxrealestateinvestors.com', 'info@austinwholesaledeal.com', 'info@atxhomebuyers.com',
  'info@lonestarpropertysolutions.com', 'info@austinrealestateinvestors.com', 'info@alamocityinvestments.com',
  'info@sanantoniowholesale.com', 'info@sahomebuyers.com', 'info@rivercityproperties.com',
  'info@dfwpropertymanagement.com', 'info@leapdfw.com', 'nathan@ambitionrealtygroup.com',
  'info@ellishomesource.com', 'info@cashdfw.com', 'office@mccawpm.com',
  'info@coxpremier.com', 'inquiries@classicpm.com', 'info@keyrenterdfw.com',
  'info@rfphomes.com', 'info@dfwhb.com', 'office@homewarddfw.com',
];

const s = createClient(process.env.VITE_SUPABASE_URL, process.env.SUPABASE_SERVICE_ROLE_KEY);
const h = new Date().getHours();
const f = FEATURES[h % FEATURES.length];
const base = process.env.APP_URL || 'http://localhost:5173';
const allVids = FEATURES.map(x => `${x.t} — ${base}/demos/demo_${x.id}.mp4`).join('\n');
const subject = `${f.t} — Contech AI Agentic teamz Demo`;
const body = `Contech AI Agentic teamz Demo — ${f.t}\n\n${f.d}\n\nWatch: ${base}/demos/demo_${f.id}.mp4\n\n---\nAll Features:\n${allVids}\n\n---\nFirst week free.`;

const emails = LEADS.map(e => ({ recipient_email: e, subject, body }));
const { data, error } = await s.from('email_queue').insert(emails).select('id');
if (error) { console.error('Error:', error.message); process.exit(1); }
console.log(`Queued ${data.length} demo promo emails for "${f.t}"`);
console.log(`Feature video: ${base}/demos/demo_${f.id}.mp4`);
