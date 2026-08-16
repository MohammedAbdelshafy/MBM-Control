import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Phone, PhoneOff, PhoneCall, User, MapPin, CheckCircle, XCircle,
  Building, ExternalLink, Zap, ChevronRight, CalendarClock,
  Search, Copy, Target, MessageSquare, ShieldCheck
} from 'lucide-react';
import { toast } from 'sonner';

const API = '/api';

const WHOLESALER_RESOURCES = [
  { name: 'Wholesaling Inc', url: 'https://www.wholesalinginc.com', phone: '(800) 594-4127', desc: 'Training, marketplace and deal resources' },
  { name: 'BiggerPockets', url: 'https://www.biggerpockets.com', phone: '(888) 446-2121', desc: 'Investor community and marketplace' },
  { name: 'REIPro', url: 'https://www.reipro.com', phone: '(800) 832-1120', desc: 'CRM and investor deal-management tools' },
];
const CASH_BUYERS = [
  { name: 'WeBuyHouses.com', url: 'https://www.webuyhouses.com', desc: 'National buyer network' },
  { name: 'HomeVestors', url: 'https://www.homevestors.com', desc: 'Investor franchise network' },
  { name: 'Offerpad', url: 'https://www.offerpad.com', desc: 'iBuyer platform' },
  { name: 'Opendoor', url: 'https://www.opendoor.com', desc: 'Digital home-buying platform' },
];
const WHOLESALE_WEBSITES = [
  { name: 'WholesalingRealEstate.com', url: 'https://www.wholesalingrealestate.com', desc: 'Education and buyer/seller resources' },
  { name: 'DealMachine', url: 'https://www.dealmachine.com', desc: 'Property sourcing and lead management' },
  { name: 'PropStream', url: 'https://www.propstream.com', desc: 'Real estate data and comps' },
  { name: 'FlipComp', url: 'https://www.flipcomp.com', desc: 'Comparable-sales research' },
];
const STATUS_META = {
  closed: { label: 'CLOSED', dot: 'bg-emerald-500', badge: 'bg-emerald-500/20 text-emerald-300' },
  callback: { label: 'CALLBACK', dot: 'bg-amber-500', badge: 'bg-amber-500/20 text-amber-300' },
  dead: { label: 'DEAD', dot: 'bg-red-500', badge: 'bg-red-500/20 text-red-300' },
};
const SCRIPT_TONE = {
  emerald: { box: 'border-emerald-500/20 bg-emerald-500/5', title: 'text-emerald-300' },
  sky: { box: 'border-sky-500/20 bg-sky-500/5', title: 'text-sky-300' },
  violet: { box: 'border-violet-500/20 bg-violet-500/5', title: 'text-violet-300' },
  amber: { box: 'border-amber-500/20 bg-amber-500/5', title: 'text-amber-300' },
};

const formatTime = (secs) => `${Math.floor(secs / 60).toString().padStart(2, '0')}:${(secs % 60).toString().padStart(2, '0')}`;
const firstName = (name = 'there') => String(name).trim().split(/\s+/)[0] || 'there';

function buildPlaybook(lead) {
  const name = firstName(lead?.prospect_name);
  const address = lead?.address || 'the property';
  const type = lead?.property_type || 'property';
  const asking = lead?.asking_price && lead.asking_price !== '$250,000' ? lead.asking_price : '';
  const criteria = lead?.distress_or_criteria || '';
  const score = lead?.distress_score || '';
  return {
    opener: `Hi ${name}, this is Mohammed with MBM. I’m reaching out about ${address}. Did I catch you with a quick minute?`,
    bridge: `I’m trying to understand whether ${address} is something you’re actively holding, selling, or simply open to discussing. What’s the situation with it right now?`,
    questions: [
      'What has you considering a sale, if anything?',
      `What is the current condition of the ${String(type).toLowerCase()}?`,
      'Is there any timing pressure or ideal closing window?',
      'Have you already received any offers, and what stood out about them?',
    ],
    transition: 'Based on what you’ve told me, the next step would be to look at the numbers rather than guess. If the deal makes sense for both sides, would you be open to reviewing a written offer?',
    close: 'What would need to happen for you to feel comfortable taking the next step?',
    voicemail: `Hi ${name}, this is Mohammed with MBM calling about ${address}. I had a quick question about the property and wanted to see whether a sale is something you’d consider. Call me back when you have a moment. Again, Mohammed with MBM.`,
    objection: 'Totally fair. I’m not calling to force a decision. I just want to understand your situation and see whether the numbers are worth a second conversation.',
    notes: [
      asking ? `Known asking price: ${asking}. Verify before discussing.` : 'No verified asking price in the feed. Do not invent one.',
      criteria ? `Lead signal: ${criteria}` : 'No explicit distress reason supplied. Discover the motivation live.',
      score ? `Lead score: ${score}. Use it for prioritization, not as a fact about the owner.` : 'No lead score supplied.',
    ],
  };
}

function ScriptCard({ title, text, accent = 'emerald' }) {
  const [copied, setCopied] = useState(false);
  const tone = SCRIPT_TONE[accent] || SCRIPT_TONE.emerald;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success('Script copied');
      setTimeout(() => setCopied(false), 1200);
    } catch {
      toast.error('Copy failed');
    }
  };
  return (
    <div className={`rounded-xl border ${tone.box} p-4`}>
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className={`text-xs uppercase tracking-wider font-bold ${tone.title}`}>{title}</div>
        <button onClick={copy} className="text-slate-400 hover:text-white" title="Copy"><Copy className="w-4 h-4" /></button>
      </div>
      <p className="text-sm leading-6 text-slate-200">{text}</p>
      {copied && <div className="text-[11px] text-emerald-300 mt-2">Copied</div>}
    </div>
  );
}

export default function AutoDialer() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentLead, setCurrentLead] = useState(null);
  const [callState, setCallState] = useState('idle');
  const [callTimer, setCallTimer] = useState(0);
  const [myPhone, setMyPhone] = useState('');
  const [query, setQuery] = useState('');
  const [marketFilter, setMarketFilter] = useState('all');
  const [showDisposition, setShowDisposition] = useState(false);
  const [showClosedResources, setShowClosedResources] = useState(false);
  const [dispositions, setDispositions] = useState({});
  const [notes, setNotes] = useState('');
  const [callbackTime, setCallbackTime] = useState('');
  const [activeScriptTab, setActiveScriptTab] = useState('core');
  const timerRef = useRef(null);
  // ── Owner Identity Verification (call-level) ────────────────────────
  const [identityName, setIdentityName] = useState('');
  const [identityRelationship, setIdentityRelationship] = useState('UNKNOWN');
  const [identityPropertyConfirmed, setIdentityPropertyConfirmed] = useState(false);
  const [identityNameConfirmed, setIdentityNameConfirmed] = useState(false);
  const [identityWrongNumber, setIdentityWrongNumber] = useState(false);
  const [identityDnc, setIdentityDnc] = useState(false);
  const [identitySaving, setIdentitySaving] = useState(false);

  useEffect(() => { fetchLeads(); loadDispositions(); }, []);
  useEffect(() => {
    if (callState === 'connected' || callState === 'ringing') timerRef.current = setInterval(() => setCallTimer((v) => v + 1), 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [callState]);

  async function fetchLeads() {
    try {
      let res = await fetch(`${API}/dialer/re-queue`);
      let data = await res.json();
      if (!data.prospects?.length) { res = await fetch(`${API}/dialer/top50`); data = await res.json(); }
      setLeads(data.prospects || []);
    } catch (err) {
      console.error(err);
      toast.error('Could not load the calling queue');
    } finally { setLoading(false); }
  }

  async function loadDispositions() {
    try {
      const res = await fetch(`${API}/dialer/dispositions`);
      const data = await res.json();
      const map = {};
      (data.dispositions || []).forEach((d) => { map[d.lead_id] = d.disposition; });
      setDispositions(map);
    } catch { /* queue remains usable */ }
  }

  const filteredLeads = useMemo(() => leads.filter((lead) => {
    if (dispositions[lead.id]) return false;
    const haystack = [lead.prospect_name, lead.address, lead.city, lead.property_type, lead.formatted_phone].filter(Boolean).join(' ').toLowerCase();
    if (query && !haystack.includes(query.toLowerCase())) return false;
    return marketFilter === 'all' || lead.city === marketFilter;
  }), [leads, dispositions, query, marketFilter]);
  const doneLeads = useMemo(() => leads.filter((l) => dispositions[l.id]), [leads, dispositions]);
  const markets = useMemo(() => [...new Set(leads.map((l) => l.city).filter(Boolean))].sort(), [leads]);
  const stats = useMemo(() => ({
    called: doneLeads.length,
    closed: doneLeads.filter((l) => dispositions[l.id] === 'closed').length,
    callback: doneLeads.filter((l) => dispositions[l.id] === 'callback').length,
    dead: doneLeads.filter((l) => dispositions[l.id] === 'dead').length,
    remaining: filteredLeads.length,
  }), [doneLeads, dispositions, filteredLeads.length]);
  const playbook = currentLead ? buildPlaybook(currentLead) : null;

  async function startCall(lead) {
    if (!myPhone.trim()) { toast.error('Enter your phone number first'); return; }
    setCurrentLead(lead); setCallState('ringing'); setCallTimer(0);
    try {
      const res = await fetch(`${API}/dialer/call-bridge`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ to_number: lead.phone_number, prospect_name: lead.prospect_name, my_phone: myPhone }) });
      const data = await res.json();
      if (['ringing_your_phone', 'bridged', 'connected'].includes(data.status)) { toast.success(`Bridge started for ${lead.prospect_name}`); setCallState('connected'); }
      else if (data.status === 'demo_mode') { toast.info('Demo mode: no live Twilio call was created'); setCallState('connected'); }
      else throw new Error(data.error || 'Call failed');
    } catch (err) { toast.error(err.message || 'Could not place call'); setCallState('idle'); setCurrentLead(null); }
  }

  function endCall() { if (timerRef.current) clearInterval(timerRef.current); setCallState('ended'); setNotes(''); setCallbackTime(''); setShowDisposition(true); }

  // Save the call-level identity result BEFORE disposition so the DB knows
  // who actually answered. Never promotes an unconfirmed person to owner.
  async function saveIdentity() {
    if (!currentLead) return false;
    setIdentitySaving(true);
    try {
      const res = await fetch(`${API}/dialer/identity`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lead_id: currentLead.id,
          caller_name: identityName,
          relationship: identityRelationship,
          property_confirmed: identityPropertyConfirmed,
          name_confirmed: identityNameConfirmed,
          wrong_number: identityWrongNumber,
          do_not_call: identityDnc,
          disposition: dispositions[currentLead.id] || '',
          notes,
        }),
      });
      if (!res.ok) throw new Error('Failed to save identity');
      return true;
    } catch (err) {
      toast.error(err.message);
      return false;
    } finally {
      setIdentitySaving(false);
    }
  }

  async function saveDisposition(disposition) {
    if (!currentLead) return;
    // Identity capture is the mandatory pre-qualification step. Skip save
    // if the caller explicitly reports a wrong number / DNC — those states
    // are recorded via the identity endpoint and the lead is suppressed.
    if (identityWrongNumber || identityDnc) {
      const saved = await saveIdentity();
      if (!saved) return;
      const id = currentLead.id;
      setDispositions((prev) => ({ ...prev, [id]: disposition }));
      toast.success(`${currentLead.prospect_name}: ${STATUS_META[disposition]?.label || disposition}`);
      setShowDisposition(false); setCallState('idle'); setCallTimer(0); setCurrentLead(null); setNotes(''); setCallbackTime('');
      resetIdentity();
      return;
    }
    try {
      const res = await fetch(`${API}/dialer/disposition`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ lead_id: currentLead.id, prospect_name: currentLead.prospect_name, disposition, notes, callback_time: disposition === 'callback' ? callbackTime || null : null }) });
      if (!res.ok) throw new Error('Failed to save disposition');
    } catch (err) { toast.error(err.message); return; }
    await saveIdentity();
    const id = currentLead.id;
    setDispositions((prev) => ({ ...prev, [id]: disposition }));
    if (disposition === 'closed') setShowClosedResources(true);
    toast.success(`${currentLead.prospect_name}: ${STATUS_META[disposition]?.label || disposition}`);
    setShowDisposition(false); setCallState('idle'); setCallTimer(0); setCurrentLead(null); setNotes(''); setCallbackTime('');
    resetIdentity();
  }

  function resetIdentity() {
    setIdentityName(''); setIdentityRelationship('UNKNOWN');
    setIdentityPropertyConfirmed(false); setIdentityNameConfirmed(false);
    setIdentityWrongNumber(false); setIdentityDnc(false);
  }

  function nextLead() { setShowDisposition(false); setShowClosedResources(false); setCallState('idle'); setCallTimer(0); setCurrentLead(null); setNotes(''); setCallbackTime(''); resetIdentity(); }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      <header className="sticky top-0 z-40 bg-slate-950/90 backdrop-blur-xl border-b border-white/10 px-4 md:px-6 py-4">
        <div className="max-w-7xl mx-auto flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="flex items-center gap-3"><div className="w-11 h-11 rounded-2xl bg-emerald-500/15 border border-emerald-400/20 flex items-center justify-center"><PhoneCall className="w-5 h-5 text-emerald-300" /></div><div><div className="flex items-center gap-2"><h1 className="text-xl font-bold">MBM Dialer</h1><span className="text-[10px] px-2 py-1 rounded-full bg-white/5 text-slate-400">v2</span></div><p className="text-xs text-slate-400">Lead-aware calling · grounded scripts · faster follow-up</p></div></div>
          <div className="grid grid-cols-5 gap-2 md:gap-5 text-center">{[['Called', stats.called, 'text-white'], ['Closed', stats.closed, 'text-emerald-300'], ['Callback', stats.callback, 'text-amber-300'], ['Dead', stats.dead, 'text-red-300'], ['Queue', stats.remaining, 'text-sky-300']].map(([label, value, cls]) => <div key={label}><div className={`text-lg md:text-2xl font-bold ${cls}`}>{value}</div><div className="text-[10px] text-slate-500">{label}</div></div>)}</div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 md:px-6 py-6 space-y-6">
        <section className="grid lg:grid-cols-[1.5fr_1fr] gap-4">
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5"><div className="flex items-center gap-2 mb-3"><Zap className="w-4 h-4 text-emerald-300" /><h2 className="font-semibold">Bridge setup</h2></div><div className="flex flex-col md:flex-row gap-3"><input type="tel" value={myPhone} onChange={(e) => setMyPhone(e.target.value)} placeholder="Your phone: +1 555 123 4567" className="flex-1 bg-slate-950/80 border border-white/10 rounded-xl px-4 py-3 outline-none focus:ring-2 focus:ring-emerald-500/50" /><div className="flex items-center text-xs text-slate-400 px-2"><ShieldCheck className="w-4 h-4 text-emerald-300 mr-2" />Twilio bridge mode</div></div></div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.03] p-5"><div className="flex items-center gap-2 mb-3"><Target className="w-4 h-4 text-sky-300" /><h2 className="font-semibold">Queue controls</h2></div><div className="flex gap-2"><div className="relative flex-1"><Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search name, city, address..." className="w-full bg-slate-950/80 border border-white/10 rounded-xl pl-9 pr-3 py-3 text-sm outline-none" /></div><select value={marketFilter} onChange={(e) => setMarketFilter(e.target.value)} className="bg-slate-950 border border-white/10 rounded-xl px-3 py-3 text-sm"><option value="all">All markets</option>{markets.map((market) => <option key={market} value={market}>{market}</option>)}</select></div></div>
        </section>

        <AnimatePresence>{currentLead && (callState === 'ringing' || callState === 'connected') && playbook && <motion.section initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -16 }} className="rounded-3xl border border-emerald-400/20 bg-gradient-to-br from-emerald-500/10 via-slate-900 to-slate-900 p-5 md:p-6 shadow-2xl">
          <div className="flex flex-col xl:flex-row gap-5">
            <div className="xl:w-[32%]"><div className="flex items-center gap-3 mb-4"><div className="relative w-14 h-14 rounded-2xl bg-emerald-500/15 flex items-center justify-center"><User className="w-7 h-7 text-emerald-200" />{callState === 'ringing' && <span className="absolute inset-0 rounded-2xl border-2 border-emerald-300/70 animate-ping" />}</div><div><h2 className="text-2xl font-bold">{currentLead.prospect_name}</h2><p className="text-sm text-slate-400">{currentLead.address || 'Address unavailable'}</p></div></div><div className="grid grid-cols-2 gap-2 mb-4"><div className="rounded-xl bg-black/20 p-3"><div className="text-xs text-slate-500">Asking</div><div className="font-semibold">{currentLead.asking_price || 'Unverified'}</div></div><div className="rounded-xl bg-black/20 p-3"><div className="text-xs text-slate-500">Lead score</div><div className="font-semibold text-emerald-300">{currentLead.distress_score || '—'}</div></div></div><div className="rounded-xl bg-black/20 p-4"><div className="flex items-center justify-between"><span className="text-xs uppercase tracking-wider text-slate-500">Call timer</span><span className="font-mono text-xl">{formatTime(callTimer)}</span></div><div className="text-xs text-slate-400 mt-2">{callState === 'ringing' ? 'Bridge is being established' : 'Live call'}</div></div></div>
            <div className="flex-1"><div className="flex flex-wrap gap-2 mb-3">{[['core', 'Open'], ['questions', 'Discover'], ['objections', 'Objections'], ['voicemail', 'Voicemail']].map(([id, label]) => <button key={id} onClick={() => setActiveScriptTab(id)} className={`px-3 py-2 rounded-lg text-xs font-semibold ${activeScriptTab === id ? 'bg-emerald-500/20 text-emerald-200 border border-emerald-400/20' : 'bg-white/5 text-slate-400'}`}>{label}</button>)}</div>
              {activeScriptTab === 'core' && <div className="space-y-3"><ScriptCard title="Opener" text={playbook.opener} /><ScriptCard title="Bridge" text={playbook.bridge} accent="sky" /><ScriptCard title="Transition" text={playbook.transition} accent="violet" /><ScriptCard title="Close" text={playbook.close} accent="amber" /></div>}
              {activeScriptTab === 'questions' && <div className="grid md:grid-cols-2 gap-3">{playbook.questions.map((q) => <ScriptCard key={q} title="Discovery question" text={q} accent="sky" />)}</div>}
              {activeScriptTab === 'objections' && <div className="space-y-3"><ScriptCard title="Pressure-free response" text={playbook.objection} accent="amber" /><div className="rounded-xl bg-white/[0.03] border border-white/10 p-4"><div className="flex items-center gap-2 text-xs uppercase tracking-wider text-slate-500 mb-2"><MessageSquare className="w-4 h-4" />Guardrails</div>{playbook.notes.map((n) => <div key={n} className="text-sm text-slate-300 py-1.5">• {n}</div>)}</div></div>}
              {activeScriptTab === 'voicemail' && <ScriptCard title="Voicemail" text={playbook.voicemail} accent="violet" />}
            </div>
          </div>
          <div className="flex flex-col sm:flex-row gap-3 mt-5"><button onClick={endCall} className="flex-1 flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 px-5 py-3 rounded-xl font-semibold"><PhoneOff className="w-5 h-5" />End & Disposition</button><button onClick={nextLead} className="sm:w-40 flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 px-5 py-3 rounded-xl font-semibold"><ChevronRight className="w-5 h-5" />Skip</button></div>
        </motion.section>}</AnimatePresence>

        <section><div className="flex items-center justify-between mb-3"><div><h2 className="text-lg font-semibold">Ready to call</h2><p className="text-xs text-slate-500">{filteredLeads.length} leads match the current queue filters</p></div></div>{loading ? <div className="py-20 text-center text-slate-500">Loading calling queue...</div> : filteredLeads.length === 0 ? <div className="rounded-2xl border border-dashed border-white/10 p-10 text-center text-slate-500">No leads match these filters.</div> : <div className="space-y-2">{filteredLeads.map((lead, i) => <motion.div key={lead.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} className="rounded-2xl border border-white/10 bg-white/[0.025] hover:bg-white/[0.05] p-4 flex flex-col lg:flex-row lg:items-center gap-4"><div className="flex items-center gap-3 flex-1 min-w-0"><div className="w-9 h-9 rounded-xl bg-slate-800 flex items-center justify-center text-xs font-bold text-slate-400">{i + 1}</div><div className="min-w-0"><div className="font-semibold truncate">{lead.prospect_name}</div><div className="text-xs text-slate-500 truncate flex items-center gap-1"><MapPin className="w-3 h-3" />{lead.address || 'No address'}</div><div className="text-[11px] text-slate-600 mt-0.5">{lead.property_type || 'Property'} · {lead.city || 'Unknown market'}</div><div className="flex items-center gap-1.5 mt-1">{lead.caller_identity_verified ? <span className="text-[9px] px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300">PERSON CONFIRMED</span> : <span className="text-[9px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400">PERSON UNCONFIRMED</span>}{lead.database_ownership_verified && <span className="text-[9px] px-2 py-0.5 rounded-full bg-sky-500/15 text-sky-300">DB OWNER</span>}{lead.identity_state && <span className="text-[9px] px-2 py-0.5 rounded-full bg-white/5 text-slate-400">{lead.identity_state}</span>}</div></div></div><div className="grid grid-cols-3 lg:flex gap-4 text-right"><div><div className="text-[11px] text-slate-500">Price</div><div className="text-sm font-semibold">{lead.asking_price || '—'}</div></div><div><div className="text-[11px] text-slate-500">Score</div><div className="text-sm font-semibold text-emerald-300">{lead.distress_score || '—'}</div></div><div><div className="text-[11px] text-slate-500">Phone</div><div className="text-xs font-mono text-slate-300">{lead.formatted_phone || lead.phone_number}</div></div></div><button onClick={() => startCall(lead)} disabled={callState !== 'idle'} className="w-full lg:w-auto flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 px-5 py-2.5 rounded-xl font-semibold"><Phone className="w-4 h-4" />Call</button></motion.div>)}</div>}</section>

        {doneLeads.length > 0 && <section><h2 className="text-lg font-semibold mb-3">Completed</h2><div className="space-y-2">{doneLeads.map((lead) => { const meta = STATUS_META[dispositions[lead.id]] || STATUS_META.dead; return <div key={lead.id} className="rounded-xl border border-white/5 bg-white/[0.02] p-3 flex items-center justify-between"><div className="flex items-center gap-3 min-w-0"><span className={`w-2 h-2 rounded-full ${meta.dot}`} /><span className="text-sm text-slate-400 truncate">{lead.prospect_name}</span><span className="text-xs text-slate-600 truncate hidden md:block">{lead.address}</span></div><span className={`text-[10px] px-2 py-1 rounded-full ${meta.badge}`}>{meta.label}</span></div>; })}</div></section>}
      </main>

      <AnimatePresence>{showDisposition && currentLead && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 bg-black/75 flex items-center justify-center p-4"><motion.div initial={{ scale: 0.96, y: 12 }} animate={{ scale: 1, y: 0 }} className="w-full max-w-xl rounded-3xl bg-slate-900 border border-white/10 p-6"><h2 className="text-2xl font-bold">What happened?</h2><p className="text-sm text-slate-500 mt-1">{currentLead.prospect_name} · {formatTime(callTimer)}</p><div className="grid md:grid-cols-3 gap-3 mt-5"><button onClick={() => saveDisposition('closed')} className="rounded-2xl border border-emerald-400/20 bg-emerald-500/10 p-4 text-left hover:bg-emerald-500/15"><CheckCircle className="w-6 h-6 text-emerald-300 mb-2" /><div className="font-semibold">Closed / Qualified</div><div className="text-xs text-slate-500 mt-1">Move to deal follow-up.</div></button><button onClick={() => saveDisposition('callback')} className="rounded-2xl border border-amber-400/20 bg-amber-500/10 p-4 text-left hover:bg-amber-500/15"><CalendarClock className="w-6 h-6 text-amber-300 mb-2" /><div className="font-semibold">Callback</div><div className="text-xs text-slate-500 mt-1">Keep the conversation alive.</div></button><button onClick={() => saveDisposition('dead')} className="rounded-2xl border border-red-400/20 bg-red-500/10 p-4 text-left hover:bg-red-500/15"><XCircle className="w-6 h-6 text-red-300 mb-2" /><div className="font-semibold">Not a Fit</div><div className="text-xs text-slate-500 mt-1">Archive from active queue.</div></button></div>

          <div className="mt-5 rounded-2xl border border-sky-400/20 bg-sky-500/5 p-4">
            <div className="flex items-center justify-between gap-3 mb-3">
              <div className="text-xs uppercase tracking-wider font-bold text-sky-300">Who am I speaking with?</div>
              <div className="flex items-center gap-1 text-[10px] text-slate-400"><ShieldCheck className="w-3 h-3 text-sky-300" />Call-level identity</div>
            </div>
            <div className="grid grid-cols-2 gap-2 mb-3 text-[11px]">
              <div className="rounded-lg bg-black/20 px-3 py-2">
                <div className="text-slate-500">PROPERTY OWNER</div>
                <div className="flex items-center gap-1 font-semibold text-emerald-300">{currentLead.database_ownership_verified ? 'Database verified' : 'Not DB-verified'} <CheckCircle className="w-3 h-3" /></div>
              </div>
              <div className="rounded-lg bg-black/20 px-3 py-2">
                <div className="text-slate-500">PERSON ON PHONE</div>
                {currentLead.caller_identity_verified ? <div className="flex items-center gap-1 font-semibold text-emerald-300">Confirmed <CheckCircle className="w-3 h-3" /></div> : <div className="flex items-center gap-1 font-semibold text-amber-300">Not yet confirmed <span>⚠</span></div>}
              </div>
            </div>
            <input value={identityName} onChange={(e) => setIdentityName(e.target.value)} placeholder="Name (as they identified):" className="w-full bg-slate-950/80 border border-white/10 rounded-xl px-3 py-2.5 text-sm outline-none mb-2" />
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 mb-2">
              {[['OWNER', 'Owner'], ['AUTHORIZED_DECISION_MAKER', 'Authorized Decision Maker'], ['TENANT', 'Tenant'], ['RELATIVE_OR_ASSOCIATE', 'Relative / Associate'], ['UNKNOWN', 'Unknown'], ['WRONG_PERSON', 'Wrong Person']].map(([val, label]) => (
                <button key={val} type="button" onClick={() => { setIdentityRelationship(val); if (val === 'WRONG_PERSON') setIdentityNameConfirmed(false); if (val === 'OWNER') setIdentityNameConfirmed(true); }} className={`text-[11px] px-2 py-2 rounded-lg border text-left ${identityRelationship === val ? 'border-sky-400/40 bg-sky-500/15 text-sky-200' : 'border-white/10 bg-white/5 text-slate-300'}`}>{label}</button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-3 text-xs">
              <label className="flex items-center gap-2"><input type="checkbox" checked={identityPropertyConfirmed} onChange={(e) => setIdentityPropertyConfirmed(e.target.checked)} className="accent-sky-400" /> Property confirmed</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={identityNameConfirmed} onChange={(e) => setIdentityNameConfirmed(e.target.checked)} className="accent-sky-400" /> Name confirmed</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={identityWrongNumber} onChange={(e) => { setIdentityWrongNumber(e.target.checked); if (e.target.checked) setIdentityDnc(false); }} className="accent-red-400" /> Wrong number</label>
              <label className="flex items-center gap-2"><input type="checkbox" checked={identityDnc} onChange={(e) => { setIdentityDnc(e.target.checked); if (e.target.checked) setIdentityWrongNumber(false); }} className="accent-red-400" /> Do not call</label>
            </div>
            <div className="text-[10px] text-slate-500 mt-2">No sensitive info requested. Identity confidence comes only from the live call — never from the DB record alone.</div>
          </div>

          <div className="mt-4 grid md:grid-cols-2 gap-3"><textarea value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Call notes, motivation, objection, price talk..." className="min-h-24 bg-slate-950 border border-white/10 rounded-xl p-3 text-sm outline-none" /><div className="space-y-3"><input value={callbackTime} onChange={(e) => setCallbackTime(e.target.value)} placeholder="Callback time (optional)" className="w-full bg-slate-950 border border-white/10 rounded-xl px-3 py-3 text-sm" /><div className="rounded-xl bg-white/[0.03] border border-white/10 p-3 text-xs text-slate-500">Save the reason, next step, and any verified number discussed.</div></div></div><button onClick={() => { setShowDisposition(false); setCallState('idle'); setCurrentLead(null); }} className="mt-4 w-full py-3 rounded-xl bg-white/5 hover:bg-white/10 text-slate-300">Cancel</button></motion.div></motion.div>}</AnimatePresence>

      <AnimatePresence>{showClosedResources && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="fixed inset-0 z-50 bg-black/80 overflow-y-auto p-4"><div className="max-w-4xl mx-auto my-8 rounded-3xl bg-slate-900 border border-emerald-400/20 p-6"><div className="text-center mb-7"><div className="w-16 h-16 mx-auto rounded-2xl bg-emerald-500/15 flex items-center justify-center mb-3"><CheckCircle className="w-8 h-8 text-emerald-300" /></div><h2 className="text-3xl font-bold">Deal Follow-up Hub</h2><p className="text-slate-500 mt-1">Move from “closed” to a concrete next action.</p></div><div className="grid md:grid-cols-2 gap-3 mb-6">{WHOLESALE_WEBSITES.map((site) => <a key={site.name} href={site.url} target="_blank" rel="noopener noreferrer" className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 hover:bg-white/[0.06]"><div className="flex items-center justify-between"><div className="font-semibold">{site.name}</div><ExternalLink className="w-4 h-4 text-slate-500" /></div><div className="text-xs text-slate-500 mt-1">{site.desc}</div></a>)}</div><div className="space-y-2 mb-6">{CASH_BUYERS.map((buyer) => <div key={buyer.name} className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 flex items-center justify-between"><div><div className="font-semibold">{buyer.name}</div><div className="text-xs text-slate-500">{buyer.desc}</div></div><a href={buyer.url} target="_blank" rel="noopener noreferrer" className="text-xs text-sky-300 hover:text-sky-200">Open</a></div>)}</div><div className="rounded-2xl border border-white/10 bg-white/[0.03] p-4 mb-6"><div className="flex items-center gap-2 text-xs uppercase tracking-wider text-slate-500 mb-2"><Building className="w-4 h-4" /> Wholesaler resources</div>{WHOLESALER_RESOURCES.map((r) => <div key={r.name} className="flex items-center justify-between py-2 border-t border-white/5 first:border-t-0"><div><div className="text-sm font-medium">{r.name}</div><div className="text-xs text-slate-500">{r.desc}</div></div>{r.phone && <div className="text-xs font-mono text-slate-400">{r.phone}</div>}</div>)}</div><button onClick={nextLead} className="w-full bg-emerald-600 hover:bg-emerald-700 py-3 rounded-xl font-semibold">Continue to Next Lead</button></div></motion.div>}</AnimatePresence>
    </div>
  );
}
