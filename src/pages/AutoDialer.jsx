import React, { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Phone, PhoneOff, PhoneCall, User, MapPin, DollarSign,
  CheckCircle, XCircle,
  Home, Building, ExternalLink, RotateCcw, Timer, Zap, ChevronRight,
  CalendarClock, FileText
} from 'lucide-react';
import { toast } from 'sonner';

const API = 'http://localhost:3002';

const WHOLESALER_RESOURCES = [
  {
    name: 'Wholesaling Inc',
    url: 'https://www.wholesalinginc.com',
    phone: '(800) 594-4127',
    desc: 'Top wholesaling coaching & deal marketplace',
  },
  {
    name: 'BiggerPockets',
    url: 'https://www.biggerpockets.com',
    phone: '(888) 446-2121',
    desc: '#1 real estate investor community & marketplace',
  },
  {
    name: 'REIPro',
    url: 'https://www.reipro.com',
    phone: '(800) 832-1120',
    desc: 'Wholesaling CRM & deal management software',
  },
];

const CASH_BUYERS = [
  {
    name: 'WeBuyHouses.com',
    url: 'https://www.webuyhouses.com',
    phone: '(800) 447-8960',
    desc: 'National cash buyer network',
  },
  {
    name: 'HomeVestors',
    url: 'https://www.homevestors.com',
    phone: '(800) 444-1616',
    desc: 'We Buy Ugly Houses franchise buyers',
  },
  {
    name: 'Offerpad',
    url: 'https://www.offerpad.com',
    phone: '(888) 890-1618',
    desc: 'iBuyer — instant cash offers',
  },
  {
    name: 'OpenDoor',
    url: 'https://www.opendoor.com',
    phone: '(888) 554-4433',
    desc: 'iBuyer — quick cash sales',
  },
  {
    name: 'MyHouseDeals Cash Buyers List',
    url: 'https://www.myhousedeals.com/cash-buyers/recent.asp',
    phone: '',
    desc: 'Free list of active cash buyers',
  },
];

const WHOLESALE_WEBSITES = [
  {
    name: 'WholesalingRealEstate.com',
    url: 'https://www.wholesalingrealestate.com',
    desc: 'Education, deals, and buyer/seller matching',
  },
  {
    name: 'DealMachine',
    url: 'https://www.dealmachine.com',
    desc: 'Find distressed properties & skip trace leads',
  },
  {
    name: 'PropStream',
    url: 'https://www.propstream.com',
    desc: 'Real estate data & cash buyer lists',
  },
  {
    name: 'FlipComp',
    url: 'https://www.flipcomp.com',
    desc: 'Real estate comps for wholesalers',
  },
];

export default function AutoDialer() {
  const [leads, setLeads] = useState([]);
  const [loading, setLoading] = useState(true);
  const [currentLead, setCurrentLead] = useState(null);
  const [callState, setCallState] = useState('idle'); // idle | ringing | connected | ended
  const [callTimer, setCallTimer] = useState(0);
  const [callStartTime, setCallStartTime] = useState(null);
  const [myPhone, setMyPhone] = useState('');
  const [showDisposition, setShowDisposition] = useState(false);
  const [showClosedResources, setShowClosedResources] = useState(false);
  const [dispositions, setDispositions] = useState({});
  const [callQueue, setCallQueue] = useState([]);
  const [completedCount, setCompletedCount] = useState(0);
  const [closedCount, setClosedCount] = useState(0);
  const [callBackCount, setCallBackCount] = useState(0);
  const [deadCount, setDeadCount] = useState(0);
  const timerRef = useRef(null);

  // Load leads
  useEffect(() => {
    fetchLeads();
    loadDispositions();
  }, []);

  // Call timer
  useEffect(() => {
    if (callState === 'connected' || callState === 'ringing') {
      timerRef.current = setInterval(() => {
        setCallTimer(prev => prev + 1);
      }, 1000);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [callState]);

  const fetchLeads = async () => {
    try {
      let res = await fetch(`${API}/api/dialer/re-queue`);
      let data = await res.json();
      if (!data.prospects || !data.prospects.length) {
        res = await fetch(`${API}/api/dialer/top50`);
        data = await res.json();
      }
      if (data.prospects) {
        setLeads(data.prospects);
      }
    } catch (err) {
      console.error('Failed to load leads:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadDispositions = async () => {
    try {
      const res = await fetch(`${API}/api/dialer/dispositions`);
      const data = await res.json();
      if (data.dispositions) {
        const map = {};
        data.dispositions.forEach(d => {
          map[d.lead_id] = d.disposition;
        });
        setDispositions(map);
      }
    } catch (err) {}
  };

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60).toString().padStart(2, '0');
    const s = (secs % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const startCall = async (lead) => {
    if (!myPhone.trim()) {
      toast.error('Enter your phone number first — Twilio will ring you, then connect to the lead');
      return;
    }

    setCurrentLead(lead);
    setCallState('ringing');
    setCallTimer(0);
    setCallStartTime(null);

    try {
      const res = await fetch(`${API}/api/dialer/call-bridge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          to_number: lead.phone_number,
          prospect_name: lead.prospect_name,
          my_phone: myPhone,
        }),
      });
      const data = await res.json();

      if (data.status === 'ringing_your_phone') {
        toast.success(`Your phone is ringing! Answer to connect to ${lead.prospect_name}`);
        // Simulate connected after a few seconds
        setTimeout(() => {
          setCallState('connected');
          setCallStartTime(Date.now());
        }, 5000);
      } else if (data.status === 'demo_mode') {
        toast.info('Demo mode — Twilio not configured. Simulating call...');
        setTimeout(() => {
          setCallState('connected');
          setCallStartTime(Date.now());
        }, 3000);
      } else {
        toast.error(data.error || 'Failed to place call');
        setCallState('idle');
      }
    } catch (err) {
      toast.error('Could not connect to dialer server');
      setCallState('idle');
    }
  };

  const endCall = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setCallState('ended');
    setShowDisposition(true);
  };

  const saveDisposition = async (disposition, notes = '', callbackTime = null) => {
    if (!currentLead) return;

    try {
      await fetch(`${API}/api/dialer/disposition`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lead_id: currentLead.id,
          prospect_name: currentLead.prospect_name,
          disposition,
          notes,
          callback_time: callbackTime,
        }),
      });
    } catch (err) {}

    setDispositions(prev => ({ ...prev, [currentLead.id]: disposition }));
    setShowDisposition(false);

    if (disposition === 'closed') {
      setClosedCount(prev => prev + 1);
      setShowClosedResources(true);
    } else if (disposition === 'callback') {
      setCallBackCount(prev => prev + 1);
      toast.success(`${currentLead.prospect_name} marked for CALLBACK`);
    } else if (disposition === 'dead') {
      setDeadCount(prev => prev + 1);
      toast.info(`${currentLead.prospect_name} marked as DEAD LEAD`);
    }

    setCompletedCount(prev => prev + 1);
    setCallState('idle');
    setCallTimer(0);
    setCurrentLead(null);
  };

  const nextLead = () => {
    setShowDisposition(false);
    setShowClosedResources(false);
    setCallState('idle');
    setCallTimer(0);
    setCurrentLead(null);
  };

  const getLeadStatus = (lead) => {
    const d = dispositions[lead.id];
    if (d === 'closed') return { color: 'bg-emerald-500', icon: CheckCircle, text: 'CLOSED' };
    if (d === 'callback') return { color: 'bg-amber-500', icon: RotateCcw, text: 'CALLBACK' };
    if (d === 'dead') return { color: 'bg-red-500', icon: XCircle, text: 'DEAD' };
    return null;
  };

  const activeLeads = leads.filter(l => !dispositions[l.id]);
  const doneLeads = leads.filter(l => dispositions[l.id]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 text-white">
      {/* Header */}
      <div className="sticky top-0 z-50 bg-slate-900/95 backdrop-blur border-b border-slate-700/50 px-6 py-4">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-10 h-10 bg-emerald-500/20 rounded-xl flex items-center justify-center">
              <PhoneCall className="w-5 h-5 text-emerald-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold">Auto-Dialer</h1>
              <p className="text-sm text-slate-400">Real Estate Dialer — US Prospect Queue</p>
            </div>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-6">
            <div className="text-center">
              <div className="text-2xl font-bold text-white">{completedCount}</div>
              <div className="text-xs text-slate-400">Called</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-emerald-400">{closedCount}</div>
              <div className="text-xs text-slate-400">Closed</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-amber-400">{callBackCount}</div>
              <div className="text-xs text-slate-400">Callback</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-400">{deadCount}</div>
              <div className="text-xs text-slate-400">Dead</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-slate-300">{activeLeads.length}</div>
              <div className="text-xs text-slate-400">Remaining</div>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6 py-6">
        {/* Phone Input */}
        {!callStartTime && (
          <div className="bg-slate-800/50 rounded-xl border border-slate-700/50 p-4 mb-6">
            <label className="block text-sm font-medium text-slate-300 mb-2">
              Your Phone Number (Twilio will ring you first, then connect to prospect)
            </label>
            <div className="flex gap-3">
              <input
                type="tel"
                value={myPhone}
                onChange={(e) => setMyPhone(e.target.value)}
                placeholder="+1 (555) 123-4567"
                className="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-emerald-500"
              />
              <div className="flex items-center gap-2 text-sm text-slate-400">
                <Zap className="w-4 h-4 text-emerald-400" />
                Bridge Mode — Your number must be verified in Twilio
              </div>
            </div>
          </div>
        )}

        {/* Active Call Banner */}
        <AnimatePresence>
          {(callState === 'ringing' || callState === 'connected') && currentLead && (
            <motion.div
              initial={{ opacity: 0, y: -20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              className="bg-gradient-to-r from-emerald-600 to-emerald-700 rounded-2xl p-6 mb-6 border border-emerald-500/30"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-4">
                  <div className="relative">
                    <div className="w-16 h-16 bg-emerald-500/30 rounded-full flex items-center justify-center">
                      <User className="w-8 h-8 text-white" />
                    </div>
                    {callState === 'ringing' && (
                      <div className="absolute inset-0 rounded-full border-2 border-emerald-300 animate-ping" />
                    )}
                  </div>
                  <div>
                    <h2 className="text-2xl font-bold">{currentLead.prospect_name}</h2>
                    <p className="text-emerald-100">{currentLead.address}</p>
                    <p className="text-sm text-emerald-200 mt-1">{currentLead.property_type}</p>
                  </div>
                </div>

                <div className="text-right">
                  <div className="flex items-center gap-2 mb-2">
                    <Timer className="w-5 h-5 text-emerald-200" />
                    <span className="text-4xl font-mono font-bold text-white">{formatTime(callTimer)}</span>
                  </div>
                  <div className="text-sm text-emerald-200">
                    {callState === 'ringing' ? 'Ringing...' : 'Connected — You are live!'}
                  </div>
                  <div className="text-lg font-bold text-emerald-100 mt-1">
                    Asking Price: {currentLead.asking_price} | Est. Commission: {currentLead.est_commission}
                  </div>
                </div>
              </div>

              {/* Calling Script */}
              <div className="mt-4 bg-emerald-800/50 rounded-lg p-3">
                <div className="flex items-center gap-2 mb-1">
                  <FileText className="w-4 h-4 text-emerald-300" />
                  <span className="text-xs font-medium text-emerald-300">CALLING SCRIPT</span>
                </div>
                <p className="text-sm text-emerald-100">{currentLead.cold_calling_script}</p>
              </div>

              <div className="mt-4 flex gap-3">
                <button
                  onClick={endCall}
                  className="flex items-center gap-2 bg-red-600 hover:bg-red-700 px-8 py-3 rounded-xl font-semibold transition-colors"
                >
                  <PhoneOff className="w-5 h-5" />
                  End Call & Disposition
                </button>
                <button
                  onClick={nextLead}
                  className="flex items-center gap-2 bg-emerald-800 hover:bg-emerald-900 px-6 py-3 rounded-xl font-medium transition-colors"
                >
                  Skip to Next
                </button>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Disposition Modal */}
        <AnimatePresence>
          {showDisposition && currentLead && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4"
            >
              <motion.div
                initial={{ scale: 0.9, y: 20 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.9, y: 20 }}
                className="bg-slate-800 rounded-2xl border border-slate-600 p-8 max-w-lg w-full"
              >
                <h2 className="text-2xl font-bold mb-2">Call Disposition</h2>
                <p className="text-slate-400 mb-6">
                  {currentLead.prospect_name} — {formatTime(callTimer)} call
                </p>

                <div className="space-y-3">
                  {/* CLOSED */}
                  <button
                    onClick={() => saveDisposition('closed')}
                    className="w-full flex items-center gap-4 bg-emerald-600/20 hover:bg-emerald-600/40 border border-emerald-500/30 rounded-xl p-5 text-left transition-colors group"
                  >
                    <div className="w-14 h-14 bg-emerald-500 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
                      <CheckCircle className="w-7 h-7 text-white" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-bold text-emerald-400">Lead Closed</h3>
                      <p className="text-sm text-slate-400">
                        Deal secured — view wholesaling resources & cash buyers
                      </p>
                    </div>
                    <ChevronRight className="w-5 h-5 text-emerald-400" />
                  </button>

                  {/* CALL BACK */}
                  <button
                    onClick={() => saveDisposition('callback')}
                    className="w-full flex items-center gap-4 bg-amber-600/20 hover:bg-amber-600/40 border border-amber-500/30 rounded-xl p-5 text-left transition-colors group"
                  >
                    <div className="w-14 h-14 bg-amber-500 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
                      <CalendarClock className="w-7 h-7 text-white" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-bold text-amber-400">Call Back</h3>
                      <p className="text-sm text-slate-400">
                        Interested but not ready — schedule follow-up
                      </p>
                    </div>
                    <ChevronRight className="w-5 h-5 text-amber-400" />
                  </button>

                  {/* DEAD LEAD */}
                  <button
                    onClick={() => saveDisposition('dead')}
                    className="w-full flex items-center gap-4 bg-red-600/20 hover:bg-red-600/40 border border-red-500/30 rounded-xl p-5 text-left transition-colors group"
                  >
                    <div className="w-14 h-14 bg-red-500 rounded-xl flex items-center justify-center group-hover:scale-110 transition-transform">
                      <XCircle className="w-7 h-7 text-white" />
                    </div>
                    <div className="flex-1">
                      <h3 className="text-lg font-bold text-red-400">Dead Lead</h3>
                      <p className="text-sm text-slate-400">
                        Not interested — mark as dead and move on
                      </p>
                    </div>
                    <ChevronRight className="w-5 h-5 text-red-400" />
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Closed Resources Modal */}
        <AnimatePresence>
          {showClosedResources && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center p-4 overflow-y-auto"
            >
              <motion.div
                initial={{ scale: 0.9, y: 20 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.9, y: 20 }}
                className="bg-slate-800 rounded-2xl border border-emerald-500/30 p-8 max-w-3xl w-full my-8"
              >
                <div className="text-center mb-8">
                  <div className="w-20 h-20 bg-emerald-500 rounded-full flex items-center justify-center mx-auto mb-4">
                    <CheckCircle className="w-10 h-10 text-white" />
                  </div>
                  <h2 className="text-3xl font-bold text-emerald-400">Deal Closed!</h2>
                  <p className="text-slate-400 mt-2">
                    Here are your wholesaling resources and cash buyer contacts
                  </p>
                </div>

                {/* Wholesaler Websites */}
                <div className="mb-8">
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <Home className="w-5 h-5 text-emerald-400" />
                    Wholesaling Platforms
                  </h3>
                  <div className="grid grid-cols-2 gap-3">
                    {WHOLESALE_WEBSITES.map((site, i) => (
                      <a
                        key={i}
                        href={site.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-3 bg-slate-700/50 rounded-lg p-3 hover:bg-slate-700 transition-colors group"
                      >
                        <ExternalLink className="w-4 h-4 text-emerald-400 flex-shrink-0" />
                        <div>
                          <div className="font-medium text-white group-hover:text-emerald-400">{site.name}</div>
                          <div className="text-xs text-slate-400">{site.desc}</div>
                        </div>
                      </a>
                    ))}
                  </div>
                </div>

                {/* 3 Wholesalers */}
                <div className="mb-8">
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <Building className="w-5 h-5 text-amber-400" />
                    Top Wholesalers
                  </h3>
                  <div className="space-y-3">
                    {WHOLESALER_RESOURCES.map((ws, i) => (
                      <div key={i} className="bg-slate-700/50 rounded-lg p-4 flex items-center justify-between">
                        <div>
                          <div className="font-bold text-white">{ws.name}</div>
                          <div className="text-sm text-slate-400">{ws.desc}</div>
                        </div>
                        <div className="text-right">
                          {ws.phone && <div className="text-emerald-400 font-mono">{ws.phone}</div>}
                          <a
                            href={ws.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-400 hover:text-blue-300"
                          >
                            Visit Website
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Cash Buyers */}
                <div className="mb-8">
                  <h3 className="text-lg font-bold text-white mb-4 flex items-center gap-2">
                    <DollarSign className="w-5 h-5 text-emerald-400" />
                    Cash Buyers Network
                  </h3>
                  <div className="space-y-3">
                    {CASH_BUYERS.map((cb, i) => (
                      <div key={i} className="bg-slate-700/50 rounded-lg p-4 flex items-center justify-between">
                        <div>
                          <div className="font-bold text-white">{cb.name}</div>
                          <div className="text-sm text-slate-400">{cb.desc}</div>
                        </div>
                        <div className="text-right">
                          {cb.phone && <div className="text-emerald-400 font-mono">{cb.phone}</div>}
                          <a
                            href={cb.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-blue-400 hover:text-blue-300"
                          >
                            Visit Website
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Instagram reference */}
                <div className="bg-slate-700/30 rounded-lg p-4 mb-6 border border-slate-600">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-purple-500 to-pink-500 rounded-lg flex items-center justify-center text-white font-bold text-sm">
                      IG
                    </div>
                    <div>
                      <a
                        href="https://www.instagram.com/wholesalingrealestate"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-bold text-white hover:text-pink-400"
                      >
                        @wholesalingrealestate
                      </a>
                      <div className="text-sm text-slate-400">Follow for deals, tips & buyer connections</div>
                    </div>
                  </div>
                </div>

                <button
                  onClick={nextLead}
                  className="w-full bg-emerald-600 hover:bg-emerald-700 py-3 rounded-xl font-semibold text-white transition-colors"
                >
                  Continue to Next Lead
                </button>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Lead List */}
        {loading ? (
          <div className="text-center py-20">
            <div className="w-8 h-8 border-4 border-emerald-500/20 border-t-emerald-500 rounded-full animate-spin mx-auto mb-3" />
            <p className="text-slate-400">Loading prospects...</p>
          </div>
        ) : (
          <div className="space-y-2">
            {activeLeads.length > 0 && (
              <div className="mb-4">
                <h3 className="text-sm font-medium text-slate-400 mb-3">
                  Ready to Call ({activeLeads.length} remaining)
                </h3>
                {activeLeads.map((lead, i) => (
                  <motion.div
                    key={lead.id}
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.03 }}
                    className="bg-slate-800/60 hover:bg-slate-800 rounded-xl border border-slate-700/30 p-4 mb-2 flex items-center justify-between transition-all"
                  >
                    <div className="flex items-center gap-4">
                      <div className="w-10 h-10 bg-slate-700 rounded-full flex items-center justify-center text-sm font-bold text-slate-300">
                        {i + 1}
                      </div>
                      <div>
                        <div className="font-semibold text-white">{lead.prospect_name}</div>
                        <div className="text-sm text-slate-400 flex items-center gap-2">
                          <MapPin className="w-3 h-3" />
                          {lead.address}
                        </div>
                        <div className="text-xs text-slate-500 mt-0.5">{lead.property_type}</div>
                      </div>
                    </div>

                    <div className="flex items-center gap-6">
                      <div className="text-right">
                        <div className="text-sm text-slate-300">{lead.asking_price}</div>
                        <div className="text-xs text-emerald-400 font-semibold">
                          Est: {lead.est_commission}
                        </div>
                        <div className="text-xs text-slate-500">
                          Distress: {lead.distress_score}
                        </div>
                      </div>

                      <div className="text-right">
                        <div className="text-sm font-mono text-slate-300">
                          {lead.formatted_phone}
                        </div>
                      </div>

                      <button
                        onClick={() => startCall(lead)}
                        disabled={callState !== 'idle'}
                        className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed px-5 py-2.5 rounded-lg font-semibold text-sm transition-colors"
                      >
                        <Phone className="w-4 h-4" />
                        Call
                      </button>
                    </div>
                  </motion.div>
                ))}
              </div>
            )}

            {doneLeads.length > 0 && (
              <div className="mt-8">
                <h3 className="text-sm font-medium text-slate-400 mb-3">
                  Completed ({doneLeads.length})
                </h3>
                {doneLeads.map((lead, i) => {
                  const status = getLeadStatus(lead);
                  const StatusIcon = status?.icon;
                  return (
                    <div
                      key={lead.id}
                      className="bg-slate-800/30 rounded-xl border border-slate-700/20 p-3 mb-2 flex items-center justify-between opacity-60"
                    >
                      <div className="flex items-center gap-3">
                        <div className={`w-2 h-2 rounded-full ${status?.color || 'bg-slate-500'}`} />
                        <span className="text-sm text-slate-400">{lead.prospect_name}</span>
                        <span className="text-xs text-slate-500">{lead.address}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {StatusIcon && (
                          <span className={`text-xs font-medium px-2 py-1 rounded ${
                            status.text === 'CLOSED' ? 'bg-emerald-500/20 text-emerald-400' :
                            status.text === 'CALLBACK' ? 'bg-amber-500/20 text-amber-400' :
                            'bg-red-500/20 text-red-400'
                          }`}>
                            {status.text}
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
