import React, { useMemo, useState } from 'react';
import { Globe, Wrench, Search, ExternalLink, CheckCircle2 } from 'lucide-react';

const SAMPLE_LEADS = [
  { name: 'Martins Investment Group (MIG)', domain: 'martins-ig.com', location: 'United States', intent: 65, offer: '$49 Business Website', reason: 'Website design + replatform intent' },
  { name: 'HSN Improvements LLC', domain: 'hsn.com', location: 'Cleveland, Ohio', intent: 81, offer: '$99 Pro Website', reason: 'Website design + replatform + mobile app intent' },
  { name: 'Fastfortechnologies', domain: 'fastfortechnologies.com', location: 'Flushing, New York', intent: 65, offer: '$149 Mini App', reason: 'Responsive web + mobile app + ecommerce intent' },
  { name: 'Bijoux International, Inc.', domain: 'bijoux-inc.com', location: 'North Brunswick Township, New Jersey', intent: 81, offer: '$99 Pro Website', reason: 'Replatform + ecommerce + web development intent' },
  { name: 'ICTX WaveMedia', domain: 'ictxwavemedia.net', location: 'Houston, Texas', intent: 96, offer: '$49 Business Website', reason: 'Very strong website-design intent' },
];

const OFFERS = [
  { label: 'Quick Website', price: '$29', monthly: '$9/mo', detail: '1-page mobile site + call/WhatsApp CTA' },
  { label: 'Business Website', price: '$49', monthly: '$19/mo', detail: '3-5 pages + form + basic SEO' },
  { label: 'Pro Website', price: '$99', monthly: '$29/mo', detail: '5-8 pages + analytics + stronger conversion UX' },
  { label: 'Mini App', price: '$149', monthly: '$39/mo', detail: 'Bookings, catalog, forms or lead capture' },
  { label: 'Business App', price: '$249', monthly: '$49/mo', detail: 'Multi-screen app + simple workflow automation' },
];

export default function DigitalServicesLeads() {
  const [query, setQuery] = useState('');
  const [activeOffer, setActiveOffer] = useState('All');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return SAMPLE_LEADS.filter((lead) => {
      const matchesQuery = !q || `${lead.name} ${lead.domain} ${lead.location} ${lead.reason}`.toLowerCase().includes(q);
      const matchesOffer = activeOffer === 'All' || lead.offer === activeOffer;
      return matchesQuery && matchesOffer;
    });
  }, [query, activeOffer]);

  return (
    <div className="min-h-screen bg-[#0a0a1a] text-gray-100 px-4 py-6">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="flex flex-col gap-2">
          <div className="flex items-center gap-2 text-purple-300">
            <Globe size={20} />
            <span className="text-xs uppercase tracking-[0.2em]">MBM Digital Services</span>
          </div>
          <h1 className="text-2xl font-bold">Website & App Leads</h1>
          <p className="text-sm text-gray-400">U.S. businesses showing web, replatform, mobile, or ecommerce intent. Use this lane separately from real-estate calling.</p>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {OFFERS.map((offer) => (
            <button
              key={offer.label}
              onClick={() => setActiveOffer(activeOffer === offer.label ? 'All' : offer.label)}
              className={`text-left rounded-2xl border p-3 transition ${activeOffer === offer.label ? 'border-purple-400/60 bg-purple-500/10' : 'border-white/10 bg-white/[0.03] hover:bg-white/[0.05]'}`}
            >
              <div className="flex items-center gap-2"><Wrench size={14} className="text-purple-300" /><span className="text-xs font-semibold">{offer.label}</span></div>
              <div className="mt-2 text-xl font-bold">{offer.price}</div>
              <div className="text-[11px] text-green-300">{offer.monthly}</div>
              <div className="mt-2 text-[10px] leading-4 text-gray-500">{offer.detail}</div>
            </button>
          ))}
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
          <div className="flex flex-col md:flex-row gap-3 md:items-center md:justify-between">
            <div>
              <div className="text-sm font-semibold">Fresh U.S. intent sample</div>
              <div className="text-xs text-gray-500">50 requested, 99 companies matched. This screen shows a 5-company review sample until the full list is exported into the dialer.</div>
            </div>
            <div className="relative md:w-72">
              <Search size={15} className="absolute left-3 top-2.5 text-gray-500" />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search company or city" className="w-full rounded-xl border border-white/10 bg-black/20 pl-9 pr-3 py-2 text-xs outline-none focus:border-purple-400/50" />
            </div>
          </div>
        </div>

        <div className="grid gap-3">
          {filtered.map((lead) => (
            <div key={lead.domain} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4">
              <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <div className="font-semibold">{lead.name}</div>
                    <CheckCircle2 size={15} className="text-green-400" />
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{lead.domain} • {lead.location}</div>
                  <div className="text-xs text-gray-300 mt-3">{lead.reason}</div>
                </div>
                <div className="text-left md:text-right">
                  <div className="text-xs uppercase tracking-wider text-purple-300">Intent {lead.intent}</div>
                  <div className="mt-1 text-sm font-semibold">{lead.offer}</div>
                  <a href={`https://${lead.domain}`} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 mt-2 text-xs text-blue-300 hover:text-blue-200">
                    Visit website <ExternalLink size={12} />
                  </a>
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-4 text-xs text-amber-200/80">
          Contact details are intentionally not shown in this preview. The full U.S. lead list can be enriched/exported separately and then imported through the dialer’s canonical lead-sync path.
        </div>
      </div>
    </div>
  );
}
