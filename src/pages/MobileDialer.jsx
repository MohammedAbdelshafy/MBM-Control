import React, { useEffect, useMemo, useState } from 'react';
import { Copy, ExternalLink, MapPin, Phone, Search, ShieldCheck, Sparkles, ChevronDown, ChevronUp } from 'lucide-react';
import { toast } from 'sonner';

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
    <div className="min-h-[100dvh] w-full overflow-x-hidden bg-slate-950 text-white">
      <header className="sticky top-0 z-30 border-b border-white/10 bg-slate-950/95 backdrop-blur-xl px-3 pt-[env(safe-area-inset-top)]">
        <div className="mx-auto w-full max-w-md px-1 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Phone className="h-5 w-5 shrink-0 text-emerald-300" />
                <h1 className="truncate text-base font-bold">MBM Mobile Dialer</h1>
              </div>
              <p className="mt-1 text-[11px] text-slate-500">Copy number → Phound → come back here for script + follow-up</p>
            </div>
            <ShieldCheck className="h-5 w-5 shrink-0 text-emerald-300" />
          </div>

          <div className="relative mt-3">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search name, city, address..."
              className="h-11 w-full rounded-xl border border-white/10 bg-white/[0.04] pl-9 pr-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500/40"
              inputMode="search"
            />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-md px-3 pb-[calc(24px+env(safe-area-inset-bottom))] pt-3">
        <div className="mb-3 rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.04] p-3">
          <div className="flex items-start gap-2.5">
            <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-emerald-300" />
            <div className="min-w-0">
              <div className="text-xs font-semibold">Phound handoff</div>
              <p className="mt-1 text-[11px] leading-4 text-slate-400">Phound handles the American number and call. MBM keeps the lead context and scripts beside it.</p>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="py-16 text-center text-sm text-slate-500">Loading calling queue…</div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center text-sm text-slate-500">No leads match that search.</div>
        ) : (
          <div className="space-y-3">
            {filtered.map((lead) => {
              const { normalized, tel } = buildPhoundLinks(lead.phone_number || lead.formatted_phone);
              const expanded = expandedId === lead.id;
              const script = buildScript(lead);

              return (
                <article key={lead.id} className="w-full overflow-hidden rounded-2xl border border-white/10 bg-white/[0.03] p-3.5 shadow-lg shadow-black/10">
                  <div className="flex min-w-0 items-start justify-between gap-2.5">
                    <div className="min-w-0 flex-1">
                      <h2 className="truncate text-sm font-semibold">{lead.prospect_name || 'Prospect'}</h2>
                      <div className="mt-1 flex min-w-0 items-center gap-1.5 text-[11px] text-slate-400">
                        <MapPin className="h-3.5 w-3.5 shrink-0" />
                        <span className="truncate">{lead.address || lead.city || 'Address unavailable'}</span>
                      </div>
                    </div>
                    <span className="shrink-0 rounded-full bg-white/5 px-2 py-1 text-[10px] text-slate-500">{lead.distress_score || '—'}</span>
                  </div>

                  <div className="mt-3 rounded-xl border border-white/5 bg-slate-950/80 p-3">
                    <div className="text-[9px] uppercase tracking-[0.18em] text-slate-500">Phone</div>
                    <div className="mt-1 break-all font-mono text-sm">{lead.formatted_phone || lead.phone_number || 'No phone'}</div>
                  </div>

                  <div className="mt-2.5 grid grid-cols-2 gap-2">
                    <button disabled={!normalized} onClick={() => copy(normalized, 'Phone number')} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] px-2 text-xs font-semibold disabled:opacity-40"><Copy className="h-4 w-4" />Copy number</button>
                    <button disabled={!normalized} onClick={() => openPhound(normalized)} className="inline-flex min-h-11 items-center justify-center gap-2 rounded-xl bg-emerald-600 px-2 text-xs font-bold hover:bg-emerald-500 disabled:opacity-40"><ExternalLink className="h-4 w-4" />Open Phound</button>
                  </div>

                  <div className="mt-2 grid grid-cols-2 gap-2">
                    <a href={tel || '#'} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-white/10 px-2 text-[11px] text-slate-300"><Phone className="h-3.5 w-3.5" />Phone</a>
                    <button onClick={() => setExpandedId(expanded ? null : lead.id)} className="inline-flex min-h-10 items-center justify-center gap-2 rounded-xl border border-emerald-400/20 bg-emerald-400/[0.05] px-2 text-[11px] font-semibold text-emerald-200">{expanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />} {expanded ? 'Hide script' : 'Show script'}</button>
                  </div>

                  {expanded && (
                    <div className="mt-3 overflow-hidden rounded-2xl border border-white/10 bg-slate-950/90">
                      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2.5">
                        <div className="text-[10px] font-bold uppercase tracking-[0.16em] text-emerald-300">Call script</div>
                        <button onClick={() => copy(script, 'Script')} className="inline-flex min-h-9 items-center gap-1.5 rounded-lg bg-white/[0.06] px-2.5 text-[11px] text-slate-200"><Copy className="h-3.5 w-3.5" />Copy all</button>
                      </div>
                      <pre className="max-h-[55vh] overflow-y-auto whitespace-pre-wrap break-words px-3 py-3 text-[12px] leading-5 text-slate-200 font-sans">{script}</pre>
                    </div>
                  )}
                </article>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
