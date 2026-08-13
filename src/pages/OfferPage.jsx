import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { CheckCircle, Zap, Calendar, Shield } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

const OFFERS = {
  'short-form-content': {
    title: 'AI Short-Form Content Engine',
    summary: 'Turn any long-form video into TikTok, YouTube Shorts & Instagram Reels automatically.',
    from: '$497',
    features: [
      '15 AI agents: hunt, acquire, transcribe, cut, edit, enhance, QC',
      'Multi-platform delivery (YouTube, TikTok, Instagram, LinkedIn)',
      'Captioning, color grade, denoise, upscale included',
      'Brand templates & priority queue',
      'from $26 per finished clip vs $500-$2,000 agency rate',
    ],
    roi: ['94-98% cost savings', '20-40 hrs/week saved', '78% of teams already use AI video'],
    plans: [
      { name: 'Starter', price: 497, note: '10 clips/mo · 2 platforms' },
      { name: 'Growth', price: 997, note: '30 clips/mo · 4 platforms', popular: true },
      { name: 'Pro', price: 1997, note: '75 clips/mo · all platforms' },
      { name: 'Enterprise', price: 3997, note: 'Unlimited · custom SLA' },
    ],
  },
  'ai-lead-generation': {
    title: 'AI Lead Generation Engine',
    summary: 'End-to-end lead discovery, scoring, qualification, enrichment, and CRM-ready exports.',
    from: '$497',
    features: [
      'Daily distressed seller & qualified buyer lists',
      'AI lead scoring + qualification + skip tracing',
      'Public records, PropStream, multi-market coverage',
      'CRM-ready CSV exports & API access',
      'from $0.50 per qualified lead vs $40-$198 agency rate',
    ],
    roi: ['99% savings on lead cost', 'Replace 3 SDRs for a fraction', '500-5000 leads/month'],
    plans: [
      { name: 'Starter', price: 497, note: '500 leads/mo · 1 market' },
      { name: 'Growth', price: 997, note: '2,000 leads/mo · 3 markets', popular: true },
      { name: 'Pro', price: 1997, note: '5,000 leads/mo · unlimited markets' },
      { name: 'Enterprise', price: 3997, note: 'Unlimited · custom filters + API' },
    ],
  },
  'email-followup-automation': {
    title: 'Email + Follow-up Automation',
    summary: 'Automated outreach, follow-up sequences, bounce handling, and pipeline tracking.',
    from: '$197',
    features: [
      'Multi-sequence email campaigns with AI personalization',
      'Auto follow-up scheduling & reply detection',
      'Bounce handling so dead addresses are never re-targeted',
      'CRM sync and pipeline reporting',
      'Sub-60 second AI response vs 3-5hr human average',
    ],
    roi: ['Never lose a lead to slow follow-up', '2% reply rate = 500 conversations', '$497 vs $2,500-$5,000 agency'],
    plans: [
      { name: 'Starter', price: 197, note: '5,000 emails/mo · 1 campaign' },
      { name: 'Growth', price: 497, note: '25,000 emails/mo · multi-sequence', popular: true },
      { name: 'Pro', price: 997, note: '100,000 emails/mo · CRM sync' },
      { name: 'Enterprise', price: 1997, note: 'Unlimited · dedicated infra' },
    ],
  },
};

const GUARANTEE = '30-day money-back guarantee. 7-day free pilot. Cancel anytime.';

export default function OfferPage() {
  const { offerId } = useParams();
  const offer = OFFERS[offerId];
  const [email, setEmail] = useState('');
  const [sent, setSent] = useState(false);

  if (!offer) {
    return (
      <div className="min-h-screen bg-[#0a0a1a] text-white flex flex-col items-center justify-center gap-4 p-8">
        <h1 className="text-2xl font-bold">Offer not found</h1>
        <Link to="/demo" className="text-purple-400 hover:text-purple-300">Back to Contech AI</Link>
      </div>
    );
  }

  async function requestQuote() {
    if (!email) return;
    try {
      const { supabase } = await import('@/api/supabaseClient');
      await supabase.from('email_queue').insert({
        recipient_email: email,
        subject: `LEAD: ${offer.title} quote request`,
        body: `Interested in ${offer.title}. Follow up to book a demo.`,
        status: 'qued',
      });
      setSent(true);
    } catch {
      setSent(true);
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a1a] text-white">
      <nav className="sticky top-0 z-50 bg-[#0a0a1a]/90 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="text-purple-400" size={18} />
            <span className="font-bold text-sm">Contech <span className="text-purple-400">AI</span></span>
          </div>
          <div className="flex items-center gap-6 text-xs text-gray-400">
            <Link to="/demo" className="hover:text-white transition-colors">Back to main</Link>
            <a href="https://calendly.com/dawrix/demo" target="_blank" rel="noreferrer" className="bg-purple-600 hover:bg-purple-500 text-white px-4 py-1.5 rounded-lg font-medium transition-colors">
              Book a Demo
            </a>
          </div>
        </div>
      </nav>

      <header className="max-w-4xl mx-auto px-4 pt-16 pb-8 text-center">
        <div className="inline-flex items-center gap-1.5 bg-purple-500/10 border border-purple-500/20 rounded-full px-3 py-1 mb-6">
          <span className="text-[10px] text-purple-300 font-medium">DONE</span>
        </div>
        <h1 className="text-3xl md:text-4xl font-bold mb-4">{offer.title}</h1>
        <p className="text-gray-400 max-w-2xl mx-auto mb-6 text-sm md:text-base">{offer.summary}</p>
        <div className="flex flex-wrap items-center justify-center gap-3 text-xs">
          <span className="bg-green-500/10 text-green-400 px-3 py-1 rounded-full">From {offer.from}/month</span>
          <span className="bg-blue-500/10 text-blue-400 px-3 py-1 rounded-full"><Shield size={11} className="inline mr-1" />30-Day Guarantee</span>
          <span className="bg-amber-500/10 text-amber-400 px-3 py-1 rounded-full"><Calendar size={11} className="inline mr-1" />Live in 48hr</span>
        </div>
      </header>

      <section className="max-w-4xl mx-auto px-4 py-8">
        <div className="grid md:grid-cols-3 gap-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-[#111125]/80 border border-white/5 rounded-2xl p-6"
          >
            <h3 className="text-sm font-bold text-white mb-4">What You Get</h3>
            <ul className="space-y-3">
              {offer.features.map((f, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-gray-400">
                  <CheckCircle size={14} className="text-green-400 mt-0.5 flex-shrink-0" />
                  <span>{f}</span>
                </li>
              ))}
            </ul>
          </motion.div>
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.08 }}
            className="bg-gradient-to-br from-purple-900/30 to-pink-900/20 border border-purple-500/20 rounded-2xl p-6"
          >
            <h3 className="font-bold text-white mb-4">The ROI Story</h3>
            <ul className="space-y-3">
              {(offer.roi || offer.savings).map((r, i) => (
                <li key={i} className="flex items-start gap-2 text-xs text-gray-300">
                  <span className="text-purple-400 mt-1">▸</span>
                  <span>{r}</span>
                </li>
              ))}
            </ul>
            <div className="mt-6 pt-5 border-t border-white/10">
              {!sent ? (
                <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); requestQuote(); }}>
                  <input
                    type="email" required placeholder="you@company.com" value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full bg-[#0a0a1a] border border-white/10 rounded-xl px-4 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-purple-500/50"
                  />
                  <button type="submit" className="w-full bg-purple-600 hover:bg-purple-500 text-white rounded-xl px-4 py-2.5 text-sm font-medium transition-colors">
                    Get Pricing & Demo
                  </button>
                </form>
              ) : (
                <p className="text-green-400 text-xs font-medium">Got it! We'll reach out within 24 hrs to set up your demo.</p>
              )}
            </div>
          </motion.div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-4 py-10">
        <h2 className="text-center text-xl md:text-2xl font-bold mb-8">Simple Plans</h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {(offer.plans || []).map((p) => (
            <div key={p.name} className={`relative bg-[#111125]/80 border rounded-2xl p-5 text-center ${p.popular ? 'border-purple-500/40' : 'border-white/5'}`}>
              {p.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-gradient-to-r from-purple-600 to-pink-600 text-white text-[10px] font-semibold px-3 py-0.5 rounded-full">
                  Most Popular
                </div>
              )}
              <h3 className="text-sm font-bold text-white mb-1">{p.name}</h3>
              <div className="text-2xl font-bold text-white mb-1">${p.price}</div>
              <p className="text-[10px] text-gray-500 mb-4">{p.note}</p>
              <Link to="/demo#pricing" className="block w-full py-2 rounded-xl text-xs font-medium bg-purple-600 hover:bg-purple-500 text-white transition-colors">
                Start Free Trial
              </Link>
            </div>
          ))}
        </div>
        <div className="text-center mt-8 flex items-center justify-center gap-2 text-sm">
          <Zap size={14} className="text-purple-400" />
          <Link to="/demo" className="text-purple-400 hover:text-purple-300 font-medium">See a working version of this →</Link>
        </div>
      </section>

      <footer className="border-t border-white/5 py-6">
        <div className="max-w-6xl mx-auto px-4 flex flex-col md:flex-row items-center justify-between gap-4">
          <span className="text-xs text-gray-500">Contech AI — Agentic Solutions</span>
          <a href="mailto:abdelshafyclapps@gmail.com" className="text-[10px] text-gray-600 hover:text-gray-400">abdelshafyclapps@gmail.com</a>
        </div>
      </footer>
    </div>
  );
}