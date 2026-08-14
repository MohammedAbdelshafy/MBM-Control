import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { supabase } from '@/api/supabaseClient';
import {
  Zap, Mail, Bot, BarChart3, Users, Play, CheckCircle,
  ChevronRight, Menu, X, Loader2, Smartphone,
  TrendingUp, Star, ArrowRight, Shield, Rocket, Calendar, ExternalLink
} from 'lucide-react';
import { Link } from 'react-router-dom';

const CONTACT = {
  email: 'abdelshafyclapps@gmail.com',
  phone: '+201040404118',
  calendly: 'https://calendly.com/dawrix/demo',
};

// Allowed plan ids must match client_orders CHECK constraint in
// supabase/migrations/00003_client_orders.sql
//   ('lead_pack_daily','lead_pack_monthly','ai_email','ai_full_stack','ai_enterprise','custom')
const PRICING_PLANS = [
  {
    id: 'lead_pack_daily',
    name: 'Lead Pack',
    price: 18,
    unit: '/day',
    desc: 'Daily distressed seller & wholesaler leads',
    features: [
      '300-600 seller leads/day',
      '50-100 buyer leads/day',
      'Delivered by 9 AM CT',
      'CSV + JSON format',
      'Confidence scores included',
    ],
    popular: false,
    paymentMethod: 'neteller',
    color: 'from-blue-600 to-blue-800',
    icon: Users,
  },
  {
    id: 'lead_pack_monthly',
    name: 'Daily Leads',
    price: 497,
    unit: '/month',
    desc: 'Daily lead packs, billed monthly',
    features: [
      '300-600 seller leads/day',
      'Delivered by 9 AM CT daily',
      'CSV + JSON format',
      'Confidence scores included',
      'Priority support',
    ],
    popular: false,
    paymentMethod: 'neteller',
    color: 'from-cyan-600 to-blue-600',
    icon: Users,
  },
  {
    id: 'ai_email',
    name: 'AI Email Automation',
    price: 297,
    unit: '/month',
    desc: 'Full email outreach automation suite',
    features: [
      'Unlimited email sequences',
      'AI copywriting & personalization',
      'Auto follow-up scheduling',
      'Reply detection & routing',
      'Analytics dashboard',
      'Priority support',
    ],
    popular: true,
    paymentMethod: 'neteller',
    color: 'from-purple-600 to-pink-600',
    icon: Mail,
  },
  {
    id: 'ai_full_stack',
    name: 'Full Stack AI',
    price: 497,
    unit: '/month',
    desc: 'Everything: leads, email, CRM, chatbot',
    features: [
      'Daily lead packs (seller + buyer)',
      'AI email automation suite',
      'Smart CRM pipeline',
      'AI customer support chatbot',
      'AI deal analysis tools',
      'Content factory (videos)',
      'Dedicated account manager',
      'White-label option',
    ],
    popular: false,
    paymentMethod: 'neteller',
    color: 'from-emerald-600 to-teal-600',
    icon: Rocket,
  },
  {
    id: 'ai_enterprise',
    name: 'Enterprise',
    price: 997,
    unit: '/month',
    desc: 'Custom AI solution for your business',
    features: [
      'Everything in Full Stack',
      'Custom AI agent development',
      'API access & integrations',
      'Multi-market coverage',
      'Unlimited users/seats',
      'SLA guarantee',
      'Priority 24/7 support',
      'Monthly strategy call',
    ],
    popular: false,
    paymentMethod: 'neteller',
    color: 'from-amber-600 to-orange-600',
    icon: Shield,
  },
];

// demo: real screen-recording files that exist in /public/demos
// liveDemo: public dashboard route deep-linked so prospects can try it
const PRODUCTS = [
  {
    id: 'email-automation',
    title: 'AI Email Automation',
    tagline: 'Draft, schedule & send â€” on autopilot',
    description: 'Personalized sequences that nurture leads, follow up automatically, and close while you sleep.',
    icon: Mail,
    savings: '20+ hrs/week',
    roi: '3x faster response',
    color: 'from-blue-600 to-cyan-500',
    demo: '/demos/demo_subscriptions.mp4',
    liveDemo: '/mbm',
  },
  {
    id: 'lead-gen',
    title: 'AI Lead Generation',
    tagline: 'Fresh leads every morning',
    description: 'Daily distressed seller & qualified buyer lists from public records, delivered by 9 AM.',
    icon: Users,
    savings: '15+ hrs/week',
    roi: '300-600 leads/day',
    color: 'from-purple-600 to-pink-500',
    demo: '/demos/demo_kpi-dashboard.mp4',
    liveDemo: '/hunt',
  },
  {
    id: 'crm-automation',
    title: 'Smart CRM Pipeline',
    tagline: 'Never drop a deal again',
    description: 'Automated deal matching, pipeline tracking, predictive analytics. Sellers to buyers instantly.',
    icon: BarChart3,
    savings: '10+ hrs/week',
    roi: '25% more closed deals',
    color: 'from-emerald-600 to-teal-500',
    demo: '/demos/demo_dealing-room.mp4',
    liveDemo: '/dealing-room',
  },
  {
    id: 'chatbot',
    title: 'AI Customer Support Bot',
    tagline: '24/7 answering, zero overhead',
    description: 'Website chatbot that answers questions, books showings, screens tenants, qualifies leads.',
    icon: Bot,
    savings: '30+ hrs/week',
    roi: '40% lower costs',
    color: 'from-amber-600 to-orange-500',
    demo: '/demos/demo_subscriptions.mp4',
    liveDemo: '/voice-agents',
  },
  {
    id: 'content-factory',
    title: 'AI Content Factory',
    tagline: 'Viral videos, auto-published',
    description: 'Autonomous clipping engine. Finds viral moments, captions, publishes everywhere.',
    icon: Smartphone,
    savings: '25+ hrs/week',
    roi: '10x content output',
    color: 'from-rose-600 to-red-500',
    demo: '/demos/demo_ai-clipping.mp4',
    liveDemo: '/mbm',
  },
  {
    id: 'deal-analysis',
    title: 'AI Deal Analysis',
    tagline: 'Underwrite in seconds, not hours',
    description: 'Automated underwriting with ARV, repair costs, ROI projection. Faster offers.',
    icon: TrendingUp,
    savings: '8+ hrs/week',
    roi: '2x deal velocity',
    color: 'from-indigo-600 to-violet-500',
    demo: '/demos/demo_route-optimization.mp4',
    liveDemo: '/kpis',
  },
];

const WORKFLOW = [
  { step: '01', title: 'Book a quick call', desc: '15 minutes. We map your exact process and pain points.' },
  { step: '02', title: 'We build your demo', desc: 'A live, working instance of your AI system â€” not slideware. Ready in 48 hours.' },
  { step: '03', title: '7-day free pilot', desc: 'Run it on real work for a week. No card, no long-term contract.' },
  { step: '04', title: 'You keep what works', desc: 'Go monthly or enterprise. Cancel anytime. 30-day money-back guarantee.' },
];

const FAQS = [
  { q: 'How fast can I get started?', a: 'Most clients are up and running within 48 hours. We handle the setup, integration, and training to your business.' },
  { q: 'Do I need technical skills?', a: 'Zero coding required. We build, deploy, and manage everything. You just use the results.' },
  { q: 'Do you offer a trial?', a: 'Yes. Every plan starts with a 7-day free pilot on live work, then a 30-day money-back guarantee. No risk.' },
  { q: 'Can I pay monthly?', a: 'Yes â€” all plans are monthly. No long-term contracts. Cancel anytime. Pay securely via 1-click Neteller checkout.' },
  { q: 'How do I pay?', a: 'Payments are processed through your Neteller wallet with a 1-click checkout link. Bank transfer available on Enterprise.' },
  { q: 'Can you work with my existing tools?', a: 'We integrate with virtually any CRM, email provider, and platform you already use.' },
];

const HERO_DEMO = '/demos/demo_intro.mp4';

function DemoVideo({ src, title }) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  return (
    <div className="relative aspect-video bg-gray-900 rounded-xl overflow-hidden border border-white/10">
      {!loaded && !error && (
        <div className="absolute inset-0 flex items-center justify-center bg-gray-900">
          <Loader2 size={26} className="text-purple-400 animate-spin" />
        </div>
      )}
      {error ? (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-900 text-gray-500 gap-2">
          <Play size={32} className="opacity-30" />
          <span className="text-xs">{title}</span>
        </div>
      ) : (
        <video
          key={src}
          src={src}
          className={`w-full h-full object-cover ${loaded ? '' : 'opacity-0'}`}
          onLoadedData={() => setLoaded(true)}
          onError={() => { setError(true); setLoaded(true); }}
          controls
          playsInline
          preload="metadata"
        />
      )}
    </div>
  );
}

function ProductCard({ product, index }) {
  const Icon = product.icon;
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: index * 0.08 }}
      className="group bg-[#111125]/80 border border-white/5 rounded-2xl p-5 hover:border-purple-500/30 transition-all duration-300"
    >
      <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${product.color} p-2 mb-3`}>
        <Icon className="w-full h-full text-white" />
      </div>
      <h3 className="text-sm font-bold text-white mb-1">{product.title}</h3>
      <p className="text-xs text-purple-300 mb-2">{product.tagline}</p>
      <p className="text-xs text-gray-400 leading-relaxed mb-3">{product.description}</p>
      <div className="flex gap-2 text-[10px] mb-4">
        <span className="bg-green-500/10 text-green-400 px-2 py-0.5 rounded-full">{product.savings}</span>
        <span className="bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full">{product.roi}</span>
      </div>
      <div className="flex gap-2">
        <button
          onClick={() => { document.getElementById('demo')?.scrollIntoView({ behavior: 'smooth' }); }}
          className="flex-1 inline-flex items-center justify-center gap-1.5 bg-white/5 hover:bg-white/10 border border-white/10 text-white px-3 py-2 rounded-lg text-[11px] font-medium transition-colors"
        >
          <Play size={12} /> Watch
        </button>
        <button
          onClick={() => { document.getElementById('pricing')?.scrollIntoView({ behavior: 'smooth' }); }}
          className="flex-1 inline-flex items-center justify-center gap-1.5 bg-purple-600 hover:bg-purple-500 text-white px-3 py-2 rounded-lg text-[11px] font-medium transition-colors"
        >
          Quote <ExternalLink size={12} />
        </button>
      </div>
    </motion.div>
  );
}

export default function DemoLandingPage() {
  const [email, setEmail] = useState('');
  const [company, setCompany] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [subscribed, setSubscribed] = useState(false);
  const [error, setError] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const [buying, setBuying] = useState(null);
  const [paidPlan, setPaidPlan] = useState(null);

  useEffect(() => {
    window.scrollTo(0, 0);
    const params = new URLSearchParams(window.location.search);
    if (params.get('paid')) setPaidPlan(params.get('paid'));
  }, []);

  function bookCall() {
    window.open(CONTACT.calendly, '_blank');
  }

  function bookCallMobile() {
    setMenuOpen(false);
    bookCall();
  }

  async function recordOrder(plan) {
    const order = { inserted: false };
    try {
      const { error } = await supabase.from('client_orders').insert({
        customer_name: name || 'Walk-in demo',
        customer_email: email || 'walkin@demo.com',
        customer_phone: '',
        company: company || '',
        plan: plan.id,
        amount: plan.price,
        currency: 'USD',
        status: 'pending',
        payment_method: plan.paymentMethod || 'neteller',
        notes: `Order from demo page - ${plan.name}`,
      });
      if (!error) order.inserted = true;
      else order.insertError = error;
    } catch (err) {
      order.insertError = err;
    }
    // The client_orders table may not exist on remote yet â€” never block a buyer.
    // Record the prospect as a lead so no request is ever lost.
    if (!order.inserted) {
      try {
        await supabase.from('email_queue').insert({
          recipient_email: email || 'walkin@demo.com',
          subject: `PAID INTENT: ${plan.name} ($${plan.price}${plan.unit})`,
          body: `Prospect ${company ? ' for ' + company : ''} requested ${plan.name} via the demo page. Follow up to collect payment.\n\nEmail: ${email || 'walkin@demo.com'}`,
          status: 'qued',
        });
      } catch (e) {
        console.error('Fallback lead capture failed:', e);
      }
    }
    return order;
  }

  async function handleBuy(plan) {
    setBuying(plan.id);
    await recordOrder(plan);
    // Try Neteller checkout first; fall back to book-a-call + email if not configured.
    try {
      const res = await fetch('/api/checkout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan: plan.id,
          email: email || undefined,
          name: name || undefined,
          company: company || undefined,
        }),
      });
      const data = await res.json();
      if (res.ok && data.url) {
        window.open(data.url, '_blank', 'noopener,noreferrer');
        setBuying(null);
        return;
      }
    } catch (e) {
      console.error('Checkout error:', e);
    }
    // Fallback path (no checkout): capture intent + open email + book a call.
    const subject = encodeURIComponent(`I want ${plan.name} - $${plan.price}${plan.unit}`);
    const body = encodeURIComponent(`Hi Mohammed,\n\nI want to sign up for ${plan.name} at $${plan.price}${plan.unit}.\n\nPlease send me the payment instructions, or I'll book a call.\n\nThanks,\n${company || '[Your Company]'}`);
    window.open(`mailto:${CONTACT.email}?subject=${subject}&body=${body}`, '_blank');
    setBuying(null);
    bookCall();
  }

  async function handleSubscribe(e) {
    e.preventDefault();
    setError('');
    if (!email) { setError('Email is required'); return; }
    setLoading(true);
    const emailBody = `Hi${name ? ' ' + name : ' there'},

Thanks for your interest in Contech AI Automation${company ? ', ' + company : ''}!

Here's what you get:
- Personalized demo walkthrough video
- Custom ROI analysis for your business
- Free 30-day trial of your chosen AI solution

Book your onboarding call:
${CONTACT.calendly}

Best,
Mohammed Abdelshafy
${CONTACT.phone}
${CONTACT.email}`;
    let failed = false;
    try {
      const { error: queueError } = await supabase.functions.invoke('add-to-email-queue', {
        body: { recipient_email: email, subject: `Welcome to Contech AI â€” Your demo is ready`, body: emailBody },
      });
      if (queueError) failed = Boolean(queueError);
    } catch (err) {
      failed = true;
    }
    // Edge Function may not be deployed â€” fall back to direct insert.
    if (failed) {
      try {
        await supabase.from('email_queue').insert({
          recipient_email: email,
          subject: `Welcome to Contech AI â€” Your demo is ready`,
          body: emailBody,
          status: 'qued',
        });
      } catch (err) {
        setError((err && err.message) || 'Something went wrong. Try again.');
        setLoading(false);
        return;
      }
    }
    setLoading(false);
    setSubscribed(true);
  }

  return (
    <div className="min-h-screen bg-[#0a0a1a] text-white">
      {/* Success banner after Neteller checkout */}
      <AnimatePresence>
        {paidPlan && (
          <motion.div
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-green-600/20 border-b border-green-500/30 text-center px-4 py-3"
          >
            <p className="text-sm text-green-300 font-medium">
              <CheckCircle size={14} className="inline mr-1" /> Payment received for {paidPlan.replace(/_/g, ' ')}! We'll onboard you now â€”
              <a href={CONTACT.calendly} target="_blank" rel="noreferrer" className="underline ml-1">book your onboarding call</a>.
            </p>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Nav */}
      <nav className="sticky top-0 z-50 bg-[#0a0a1a]/90 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="text-purple-400" size={18} />
            <span className="font-bold text-sm">Contech <span className="text-purple-400">AI</span></span>
          </div>
          <div className="hidden md:flex items-center gap-6 text-xs text-gray-400">
            <a href="#products" className="hover:text-white transition-colors">Products</a>
            <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
            <a href="#demo" className="hover:text-white transition-colors">Demo</a>
            <a href="#how" className="hover:text-white transition-colors">How it works</a>
            <a href="#faq" className="hover:text-white transition-colors">FAQ</a>
            <button onClick={bookCall} className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-1.5 rounded-lg text-xs font-medium transition-colors whitespace-nowrap">
              Book a Call
            </button>
          </div>
          <button className="md:hidden text-gray-400" onClick={() => setMenuOpen(!menuOpen)}>
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
        <AnimatePresence>
          {menuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden border-t border-white/5 overflow-hidden"
            >
              <div className="px-4 py-3 space-y-3">
                <a href="#products" onClick={() => setMenuOpen(false)} className="block text-xs text-gray-300 hover:text-white">Products</a>
                <a href="#pricing" onClick={() => setMenuOpen(false)} className="block text-xs text-gray-300 hover:text-white">Pricing</a>
                <a href="#demo" onClick={() => setMenuOpen(false)} className="block text-xs text-gray-300 hover:text-white">Demo</a>
                <a href="#how" onClick={() => setMenuOpen(false)} className="block text-xs text-gray-300 hover:text-white">How it works</a>
                <button onClick={bookCallMobile} className="block w-full text-center bg-purple-600 text-white px-4 py-2 rounded-lg text-xs font-medium">
                  Book a Call
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </nav>

      {/* Hero */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-b from-purple-900/20 via-transparent to-transparent pointer-events-none" />
        <div className="max-w-5xl mx-auto px-4 pt-20 pb-16 md:pt-28 md:pb-24">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="grid md:grid-cols-2 gap-10 items-center"
          >
            <div className="text-center md:text-left">
              <div className="inline-flex items-center gap-1.5 bg-purple-500/10 border border-purple-500/20 rounded-full px-3 py-1 mb-6">
                <Star size={10} className="text-purple-400" />
                <span className="text-[10px] text-purple-300 font-medium">Agentic AI Automation for Real Estate &amp; Ops</span>
              </div>
              <h1 className="text-3xl md:text-4xl font-bold leading-tight mb-4">
                Your operations,
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-purple-400 to-pink-400"> on autopilot</span>
              </h1>
              <p className="text-sm md:text-base text-gray-400 max-w-md mx-auto mb-6 leading-relaxed">
                Stop burning hours on manual data entry, follow-ups, and lead qualification.
                We build you a working AI system â€” email, leads, CRM, chatbot, content.
                Live demo in 48 hours. First week free.
              </p>
              <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
                <button
                  onClick={bookCall}
                  className="bg-purple-600 hover:bg-purple-500 text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-all inline-flex items-center gap-2"
                >
                  <Play size={14} /> See the Demo <ChevronRight size={16} />
                </button>
                <a href="#how" className="border border-white/10 hover:border-white/20 text-gray-300 px-6 py-2.5 rounded-xl text-sm font-medium transition-all">
                  How it works
                </a>
              </div>
              <div className="flex items-center justify-center gap-6 mt-8 text-xs text-gray-500">
                <span className="flex items-center gap-1"><CheckCircle size={12} className="text-green-400" /> 48hr Setup</span>
                <span className="flex items-center gap-1"><CheckCircle size={12} className="text-green-400" /> 7-Day Free Pilot</span>
                <span className="flex items-center gap-1"><CheckCircle size={12} className="text-green-400" /> 30-Day Guarantee</span>
              </div>
            </div>
            <div className="space-y-2">
              <DemoVideo src={HERO_DEMO} title="Platform overview" />
              <p className="text-center text-[10px] text-gray-600">2-minute overview of the platform in action</p>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Trust stats */}
      <section className="border-y border-white/5 bg-[#111125]/50">
        <div className="max-w-5xl mx-auto px-4 py-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            {[
              { value: '50+', label: 'Markets Scanned', color: 'text-green-400' },
              { value: '3x', label: 'Lead Response', color: 'text-blue-400' },
              { value: '40%', label: 'More Closed Deals', color: 'text-purple-400' },
              { value: '48hr', label: 'Live Demo Turnaround', color: 'text-amber-400' },
            ].map((stat, i) => (
              <div key={i}>
                <p className={`text-xl md:text-2xl font-bold ${stat.color}`}>{stat.value}</p>
                <p className="text-[10px] text-gray-500 mt-0.5">{stat.label}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Products */}
      <section id="products" className="max-w-5xl mx-auto px-4 py-16">
        <motion.div initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="text-center mb-10">
          <h2 className="text-xl md:text-3xl font-bold mb-3">Everything You Need to Scale</h2>
          <p className="text-sm text-gray-400 max-w-xl mx-auto">
            Six integrated AI systems that work together to automate your entire operations.
          </p>
        </motion.div>
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {PRODUCTS.map((product, i) => (
            <ProductCard key={product.id} product={product} index={i} />
          ))}
        </div>
      </section>

      {/* Demo Videos */}
      <section id="demo" className="bg-[#111125]/50 border-y border-white/5 py-16">
        <div className="max-w-5xl mx-auto px-4">
          <motion.div initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="text-center mb-8">
            <h2 className="text-xl md:text-3xl font-bold mb-3">See It in Action</h2>
            <p className="text-sm text-gray-400">Real screen recordings of each AI system</p>
          </motion.div>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
            {PRODUCTS.map((product) => (
              <div key={product.id} className="space-y-2">
                <DemoVideo src={product.demo} title={product.title} />
                <p className="text-xs text-gray-400 font-medium flex items-center justify-between">
                  {product.title}
                  <Link to={product.liveDemo} className="text-purple-400 hover:text-purple-300 text-[10px] underline">
                    Open live â†’
                  </Link>
                </p>
              </div>
            ))}
          </div>
          <div className="text-center mt-8">
            <button onClick={bookCall} className="inline-flex items-center gap-2 text-purple-400 hover:text-purple-300 text-sm font-medium">
              <Calendar size={14} /> Want this custom-built for your business? Book a live demo
            </button>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="max-w-5xl mx-auto px-4 py-16">
        <motion.div initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="text-center mb-10">
          <h2 className="text-xl md:text-3xl font-bold mb-3">From Call to Live in 48 Hours</h2>
          <p className="text-sm text-gray-400 max-w-xl mx-auto">We build and you pilot â€” no slideware.</p>
        </motion.div>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {WORKFLOW.map((w, i) => (
            <motion.div key={w.step} initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.08 }} className="bg-[#111125]/80 border border-white/5 rounded-2xl p-5">
              <div className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-br from-purple-400 to-pink-400 mb-2">{w.step}</div>
              <h3 className="text-sm font-bold text-white mb-1">{w.title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">{w.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="max-w-6xl mx-auto px-4 py-16">
        <motion.div initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="text-center mb-10">
          <h2 className="text-xl md:text-3xl font-bold mb-3">Simple, Transparent Pricing</h2>
          <p className="text-sm text-gray-400 max-w-xl mx-auto">
            Start with a 7-day free pilot. Upgrade when ready. No long-term contracts.
          </p>
        </motion.div>

        <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5 gap-4">
          {PRICING_PLANS.map((plan, i) => {
            const Icon = plan.icon;
            return (
              <motion.div
                key={plan.id}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className={`relative bg-[#111125]/80 border rounded-2xl p-5 flex flex-col ${
                  plan.popular ? 'border-purple-500/40 ring-1 ring-purple-500/20' : 'border-white/5'
                }`}
              >
                {plan.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-purple-600 to-pink-600 text-white text-[10px] font-semibold px-3 py-0.5 rounded-full whitespace-nowrap">
                    Most Popular
                  </div>
                )}
                <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${plan.color} p-2 mb-3`}>
                  <Icon className="w-full h-full text-white" />
                </div>
                <h3 className="text-sm font-bold text-white mb-1">{plan.name}</h3>
                <p className="text-xs text-gray-400 mb-3 h-8">{plan.desc}</p>
                <div className="mb-4">
                  <span className="text-2xl font-bold text-white">${plan.price}</span>
                  <span className="text-xs text-gray-500 ml-1">{plan.unit}</span>
                </div>
                <ul className="space-y-2 mb-6 flex-1">
                  {plan.features.map((f, j) => (
                    <li key={j} className="flex items-start gap-2 text-[11px] text-gray-400">
                      <CheckCircle size={12} className="text-green-400 mt-0.5 flex-shrink-0" />
                      <span>{f}</span>
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => handleBuy(plan)}
                  disabled={buying === plan.id}
                  className={`w-full py-2 rounded-xl text-xs font-medium transition-all ${
                    plan.popular
                      ? 'bg-purple-600 hover:bg-purple-500 text-white'
                      : 'border border-white/10 hover:border-white/20 text-gray-300'
                  } disabled:opacity-50`}
                >
                  {buying === plan.id ? 'Processing...' : plan.id === 'ai_enterprise' ? 'Request Enterprise' : 'Start Free Trial'}
                </button>
              </motion.div>
            );
          })}
        </div>

        <div className="text-center mt-6">
          <p className="text-[10px] text-gray-600">
            7-day free pilot Â· 30-day money-back guarantee Â· Cancel anytime Â· Secure Neteller checkout
          </p>
          <p className="text-[10px] text-gray-600 mt-1">
            Need a custom plan?
            <a href={`mailto:${CONTACT.email}`} className="text-purple-400 hover:text-purple-300"> Contact us</a>
            or
            <button onClick={bookCall} className="text-purple-400 hover:text-purple-300"> book a call</button>
          </p>
        </div>
      </section>

      {/* FAQ */}
      <section id="faq" className="bg-[#111125]/50 border-y border-white/5 py-16">
        <div className="max-w-3xl mx-auto px-4">
          <motion.div initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="text-center mb-8">
            <h2 className="text-xl md:text-3xl font-bold mb-3">Frequently Asked</h2>
          </motion.div>
          <div className="space-y-3">
            {FAQS.map((faq, i) => (
              <details key={i} className="bg-[#0a0a1a] border border-white/5 rounded-xl overflow-hidden group">
                <summary className="px-4 py-3 text-sm font-medium text-gray-300 cursor-pointer hover:text-white transition-colors flex items-center justify-between list-none">
                  {faq.q}
                  <ChevronRight size={14} className="text-gray-600 group-open:rotate-90 transition-transform" />
                </summary>
                <div className="px-4 pb-3 text-xs text-gray-500 leading-relaxed">{faq.a}</div>
              </details>
            ))}
          </div>
        </div>
      </section>

      {/* CTA â€” Email Capture */}
      <section id="get-started" className="max-w-3xl mx-auto px-4 py-16">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          className="bg-gradient-to-br from-purple-900/30 to-pink-900/20 border border-purple-500/20 rounded-2xl p-6 md:p-8 text-center"
        >
          {subscribed ? (
            <div>
              <CheckCircle size={40} className="text-green-400 mx-auto mb-3" />
              <h3 className="text-lg font-bold mb-2">You're In!</h3>
              <p className="text-sm text-gray-400 mb-4">
                Check your inbox for your personalized demo link and ROI analysis.
                We'll be in touch within 24 hours.
              </p>
              <button onClick={bookCall} className="inline-flex items-center gap-1.5 text-purple-400 text-sm hover:text-purple-300">
                Book a call now <ArrowRight size={14} />
              </button>
            </div>
          ) : (
            <>
              <h2 className="text-xl md:text-2xl font-bold mb-2">See a Working Version Built For You</h2>
              <p className="text-sm text-gray-400 mb-6 max-w-md mx-auto">
                We hand-tailor this to your exact business. Free, no obligation. Live in 48 hours.
              </p>
              <form onSubmit={handleSubscribe} className="max-w-sm mx-auto space-y-3">
                <input
                  type="text" placeholder="Your Name" value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-[#0a0a1a] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500/50 transition-colors"
                />
                <input
                  type="text" placeholder="Company Name" value={company}
                  onChange={(e) => setCompany(e.target.value)}
                  className="w-full bg-[#0a0a1a] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500/50 transition-colors"
                />
                <input
                  type="email" placeholder="you@company.com" value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-[#0a0a1a] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500/50 transition-colors"
                  required
                />
                {error && <p className="text-xs text-red-400">{error}</p>}
                <button
                  type="submit" disabled={loading}
                  className="w-full bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white rounded-xl px-4 py-2.5 text-sm font-medium transition-all inline-flex items-center justify-center gap-2"
                >
                  {loading ? <Loader2 size={14} className="animate-spin" /> : null}
                  Get My Free Demo
                </button>
                <p className="text-[10px] text-gray-600">No spam. Unsubscribe anytime. First week free.</p>
              </form>
            </>
          )}
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-6">
        <div className="max-w-5xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <Zap size={14} className="text-purple-400" />
            <span className="text-xs text-gray-500">Contech AI â€” Agentic Solutions</span>
          </div>
          <div className="flex items-center gap-4 text-[10px] text-gray-600">
            <a href={`mailto:${CONTACT.email}`} className="hover:text-gray-400">{CONTACT.email}</a>
            <a href={CONTACT.phone} className="hover:text-gray-400">{CONTACT.phone}</a>
          </div>
        </div>
      </footer>
    </div>
  );
}