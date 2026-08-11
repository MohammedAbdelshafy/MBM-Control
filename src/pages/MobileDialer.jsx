import React, { useEffect, useMemo, useState } from 'react';
import { Copy, ExternalLink, MapPin, Phone, Search, ShieldCheck, Sparkles } from 'lucide-react';
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

export default function MobileDialer() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState('');

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
    <div className="min-h-screen bg-slate-950 text-white">
      <div className="sticky top-0 z-20 border-b border-white/10 bg-slate-950/95 backdrop-blur-xl px-4 py-4">
        <div className="max-w-xl mx-auto space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <Phone className="w-5 h-5 text-emerald-300" />
                <h1 className="text-lg font-bold">MBM Mobile Dialer</h1>
              </div>
              <p className="text-xs text-slate-500">Pick lead → copy number → open Phound → call</p>
            </div>
            <ShieldCheck className="w-5 h-5 text-emerald-300" />
          </div>
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search name, city, address..."
              className="w-full rounded-xl border border-white/10 bg-white/[0.04] pl-9 pr-3 py-3 text-sm outline-none focus:ring-2 focus:ring-emerald-500/40"
            />
          </div>
        </div>
      </div>

      <main className="max-w-xl mx-auto px-4 py-4 space-y-3">
        <div className="rounded-2xl border border-emerald-400/15 bg-emerald-400/[0.04] p-4">
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-emerald-300 mt-0.5" />
            <div>
              <div className="font-semibold text-sm">Phound handoff</div>
              <p className="text-xs text-slate-400 mt-1">MBM handles the lead and script. Phound handles your American number and the actual call.</p>
            </div>
          </div>
        </div>

        {loading ? (
          <div className="py-16 text-center text-slate-500">Loading calling queue…</div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center text-slate-500">No leads match that search.</div>
        ) : (
          filtered.map((lead) => {
            const { normalized, tel } = buildPhoundLinks(lead.phone_number || lead.formatted_phone);
            return (
              <article key={lead.id} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 shadow-xl shadow-black/10">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="font-semibold truncate">{lead.prospect_name || 'Prospect'}</h2>
                    <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-1">
                      <MapPin className="w-3.5 h-3.5 shrink-0" />
                      <span className="truncate">{lead.address || lead.city || 'Address unavailable'}</span>
                    </div>
                  </div>
                  <span className="text-[10px] rounded-full bg-white/5 px-2 py-1 text-slate-500">{lead.distress_score || '—'}</span>
                </div>

                <div className="mt-3 rounded-xl border border-white/5 bg-slate-950/70 p-3">
                  <div className="text-[10px] uppercase tracking-wider text-slate-500 mb-1">Phone</div>
                  <div className="font-mono text-base">{lead.formatted_phone || lead.phone_number || 'No phone'}</div>
                </div>

                <div className="grid grid-cols-2 gap-2 mt-3">
                  <button
                    disabled={!normalized}
                    onClick={() => copy(normalized, 'Phone number')}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] py-3 text-sm font-medium disabled:opacity-40"
                  >
                    <Copy className="w-4 h-4" /> Copy
                  </button>
                  <button
                    disabled={!normalized}
                    onClick={() => openPhound(normalized)}
                    className="inline-flex items-center justify-center gap-2 rounded-xl bg-emerald-600 py-3 text-sm font-semibold hover:bg-emerald-500 disabled:opacity-40"
                  >
                    <ExternalLink className="w-4 h-4" /> Open Phound
                  </button>
                </div>

                <div className="grid grid-cols-2 gap-2 mt-2">
                  <a
                    href={tel || '#'}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 py-2.5 text-xs text-slate-300"
                  >
                    <Phone className="w-3.5 h-3.5" /> Phone link
                  </a>
                  <button
                    onClick={() => copy(lead.cold_calling_script || '', 'Script')}
                    className="inline-flex items-center justify-center gap-2 rounded-xl border border-white/10 py-2.5 text-xs text-slate-300"
                  >
                    <Copy className="w-3.5 h-3.5" /> Copy script
                  </button>
                </div>
              </article>
            );
          })
        )}
      </main>
    </div>
  );
}
