import React, { useEffect, useMemo, useState } from 'react';
import { Copy, ExternalLink, MapPin, Phone, Search, ShieldCheck, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';
import '@/styles/mobile-dialer.css';

const API = '/api';

function normalizePhone(value = '') {
  const digits = String(value).replace(/[^\d+]/g, '');
  if (!digits) return '';
  return digits.startsWith('+') ? digits : `+1${digits.replace(/^1/, '')}`;
}

function buildPhoundLinks(phone) {
  const normalized = normalizePhone(phone);
  const tel = normalized ? `tel:${normalized}` : '';
  const phound = normalized ? `https://web.phound.app/?phone=${encodeURIComponent(normalized)}` : '';
  return { normalized, tel, phound };
}

function buildScript(lead = {}) {
  const first = String(lead.prospect_name || 'there').trim().split(/\s+/)[0] || 'there';
  const address = lead.address || 'the property';
  const reason = lead.distress_or_criteria;
  const asking = lead.asking_price && lead.asking_price !== '$250,000' ? lead.asking_price : '';
  return [
    `Hi ${first}, this is Mohammed with MBM. I’m calling about ${address}. Did I catch you with a quick minute?`,
    `I wanted to understand what your plans are for ${address}. Are you holding it, considering selling, or still figuring that out?`,
    'What has you considering a sale, if anything?',
    'What is the current condition of the property?',
    'Is there a preferred timing or any deadline you are working around?',
    asking ? `I have ${asking} in the lead record, but I want to verify that with you before we discuss numbers.` : 'I do not have a verified asking price, so I will start by understanding the situation rather than guessing.',
    reason ? `The lead contains this signal: ${reason}. I want to hear your side of the story before drawing conclusions.` : 'I do not have a verified motivation, so I will learn that from the conversation.',
    'Based on what you’ve told me, would you be open to reviewing a written offer if the numbers make sense?',
    `Voicemail: Hi ${first}, this is Mohammed with MBM calling about ${address}. I had a quick question about the property. Call me back when you have a moment. Again, Mohammed with MBM.`,
  ].join('\n');
}

export default function MobileDialer() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    (async () => {
      try {
        let response = await fetch(`${API}/dialer/re-queue`);
        let data = await response.json();
        if (!data.prospects?.length) {
          response = await fetch(`${API}/dialer/top50`);
          data = await response.json();
        }
        setLeads(data.prospects || []);
      } catch {
        toast.error('Could not load leads');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return leads;
    return leads.filter((lead) => [lead.prospect_name, lead.address, lead.city, lead.formatted_phone]
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
      .includes(q));
  }, [leads, query]);

  async function copy(text, label) {
    try {
      await navigator.clipboard.writeText(text);
      toast.success(`${label} copied`);
    } catch {
      toast.error(`Couldn't copy ${label.toLowerCase()}`);
    }
  }

  function openPhound(phone) {
    const { phound } = buildPhoundLinks(phone);
    if (!phound) return toast.error('No phone number available');
    window.location.href = phound;
  }

  return (
    <div className="mobile-dialer-shell fixed inset-0 z-[60] flex w-full max-w-full flex-col overflow-hidden bg-slate-950 text-white md:static md:min-h-screen md:overflow-visible">
      <header className="md-header shrink-0 border-b border-white/10 bg-slate-950/95 backdrop-blur-xl px-2 pt-[env(safe-area-inset-top)] sm:px-3">
        <div className="md-header-inner mx-auto w-full max-w-sm px-1 py-2.5 sm:max-w-md sm:py-3">
          <div className="flex items-center justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5"><Phone className="h-4 w-4 shrink-0 text-emerald-300 sm:h-5 sm:w-5" /><h1 className="md-header-title truncate text-sm font-bold sm:text-base">MBM Mobile Dialer</h1></div>
              <p className="md-header-subtitle mt-0.5 truncate text-[9px] text-slate-500 sm:mt-1 sm:text-[11px]">Copy number → Phound → return for script</p>
            </div>
            <ShieldCheck className="h-4 w-4 shrink-0 text-emerald-300 sm:h-5 sm:w-5" />
          </div>
          <div className="relative mt-2 sm:mt-3"><Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, city, address..." className="md-search h-9 w-full rounded-lg border border-white/10 bg-white/[0.04] pl-8 pr-2 text-[11px] outline-none focus:ring-2 focus:ring-emerald-500/40 sm:h-11 sm:rounded-xl sm:pl-9 sm:text-sm" inputMode="search" /></div>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-2 pb-[calc(14px+env(safe-area-inset-bottom))] pt-2 sm:px-3 sm:pb-6 sm:pt-3">
        <div className="mx-auto w-full max-w-sm sm:max-w-md">
          <div className="md-info mb-2 rounded-xl border border-emerald-400/15 bg-emerald-400/[0.04] p-2 sm:mb-3 sm:rounded-2xl sm:p-3"><div className="flex items-start gap-2"><Sparkles className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-300 sm:h-4 sm:w-4" /><div className="min-w-0"><div className="text-[10px] font-semibold sm:text-xs">Phound handoff</div><p className="mt-0.5 text-[9px] leading-3.5 text-slate-400 sm:text-[11px] sm:leading-4">Phound handles the American number and call. MBM keeps the lead context and scripts beside it.</p></div></div></div>

          {loading ? <div className="py-12 text-center text-xs text-slate-500 sm:py-16 sm:text-sm">Loading calling queue…</div> : filtered.length === 0 ? <div className="py-12 text-center text-xs text-slate-500 sm:py-16 sm:text-sm">No leads match that search.</div> : (
            <div className="md-leads space-y-2 sm:space-y-3">
              {filtered.map((lead) => {
                const { normalized, tel } = buildPhoundLinks(lead.phone_number || lead.formatted_phone);
                const expanded = expandedId === lead.id;
                const script = buildScript(lead);
                return (
                  <article key={lead.id} className="md-card w-full overflow-hidden rounded-xl border border-white/10 bg-white/[0.03] p-2.5 shadow-md shadow-black/10 sm:rounded-2xl sm:p-3.5">
                    <div className="flex min-w-0 items-start justify-between gap-2"><div className="min-w-0 flex-1"><h2 className="truncate text-xs font-semibold sm:text-sm">{lead.prospect_name || 'Prospect'}</h2><div className="mt-0.5 flex min-w-0 items-center gap-1 text-[9px] text-slate-400 sm:mt-1 sm:gap-1.5 sm:text-[11px]"><MapPin className="h-3 w-3 shrink-0 sm:h-3.5 sm:w-3.5" /><span className="truncate">{lead.address || lead.city || 'Address unavailable'}</span></div></div><span className="shrink-0 rounded-full bg-white/5 px-1.5 py-0.5 text-[8px] text-slate-500 sm:px-2 sm:py-1 sm:text-[10px]">{lead.distress_score || '—'}</span></div>
                    <div className="md-phone mt-2 rounded-lg border border-white/5 bg-slate-950/80 p-2 sm:mt-3 sm:rounded-xl sm:p-3"><div className="text-[7px] uppercase tracking-[0.16em] text-slate-500 sm:text-[9px] sm:tracking-[0.18em]">Phone</div><div className="mt-0.5 break-all font-mono text-[11px] sm:mt-1 sm:text-sm">{lead.formatted_phone || lead.phone_number || 'No phone'}</div></div>
                    <div className="md-actions mt-1.5 grid grid-cols-2 gap-1.5 sm:mt-2.5 sm:gap-2"><button disabled={!normalized} onClick={() => copy(normalized, 'Phone number')} className="md-primary-action inline-flex min-h-9 items-center justify-center gap-1 rounded-lg border border-white/10 bg-white/[0.04] px-1.5 text-[9px] font-semibold disabled:opacity-40 sm:min-h-11 sm:gap-2 sm:rounded-xl sm:px-2 sm:text-xs"><Copy className="h-3 w-3 sm:h-4 sm:w-4" />Copy</button><button disabled={!normalized} onClick={() => openPhound(normalized)} className="md-primary-action inline-flex min-h-9 items-center justify-center gap-1 rounded-lg bg-emerald-600 px-1.5 text-[9px] font-bold hover:bg-emerald-500 disabled:opacity-40 sm:min-h-11 sm:gap-2 sm:rounded-xl sm:px-2 sm:text-xs"><ExternalLink className="h-3 w-3 sm:h-4 sm:w-4" />Open Phound</button></div>
                    <div className="md-actions mt-1.5 grid grid-cols-2 gap-1.5 sm:mt-2 sm:gap-2"><a href={tel || '#'} className="md-secondary-action inline-flex min-h-8 items-center justify-center gap-1 rounded-lg border border-white/10 px-1.5 text-[9px] text-slate-300 sm:min-h-10 sm:gap-2 sm:rounded-xl sm:px-2 sm:text-[11px]"><Phone className="h-3 w-3 sm:h-3.5 sm:w-3.5" />Phone</a><button onClick={() => setExpandedId(expanded ? null : lead.id)} className="md-secondary-action inline-flex min-h-8 items-center justify-center gap-1 rounded-lg border border-emerald-400/20 bg-emerald-400/[0.05] px-1.5 text-[9px] font-semibold text-emerald-200 sm:min-h-10 sm:gap-2 sm:rounded-xl sm:px-2 sm:text-[11px]">{expanded ? <ChevronUp className="h-3 w-3 sm:h-3.5 sm:w-3.5" /> : <ChevronDown className="h-3 w-3 sm:h-3.5 sm:w-3.5" />}{expanded ? 'Hide' : 'Script'}</button></div>
                    {expanded && <div className="md-card mt-2 overflow-hidden rounded-xl border border-white/10 bg-slate-950/90 sm:mt-3 sm:rounded-2xl"><div className="flex items-center justify-between border-b border-white/10 px-2.5 py-2 sm:px-3 sm:py-2.5"><div className="text-[8px] font-bold uppercase tracking-[0.14em] text-emerald-300 sm:text-[10px] sm:tracking-[0.16em]">Call script</div><button onClick={() => copy(script, 'Script')} className="inline-flex min-h-7 items-center gap-1 rounded-md bg-white/[0.06] px-2 text-[9px] text-slate-200 sm:min-h-9 sm:gap-1.5 sm:rounded-lg sm:px-2.5 sm:text-[11px]"><Copy className="h-3 w-3 sm:h-3.5 sm:w-3.5" />Copy</button></div><pre className="md-script md-script-box overflow-y-auto whitespace-pre-wrap break-words px-2.5 py-2.5 text-[10px] leading-4 text-slate-200 font-sans sm:max-h-[55vh] sm:px-3 sm:py-3 sm:text-[12px] sm:leading-5">{script}</pre></div>}
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
